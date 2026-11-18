"""Copy KwachaStay data from SQLite to PostgreSQL without modifying SQLite.

Dry run first (prints row counts only):
  python scripts/migrate_sqlite_to_postgres.py --database-url "$DATABASE_URL"

Apply only after reviewing the summary:
  python scripts/migrate_sqlite_to_postgres.py --database-url "$DATABASE_URL" --apply

Print the PostgreSQL DDL for the Supabase SQL editor:
  python scripts/migrate_sqlite_to_postgres.py --print-schema
"""
import argparse
import os
import sqlite3
from pathlib import Path

try:
    from postgres_schema import ROOT, build_schema_sql
except ImportError:  # imported as a package from the project root
    from scripts.postgres_schema import ROOT, build_schema_sql

SQLITE_DATABASE = ROOT / 'kwachastay.db'
TABLE_ORDER = [
    'users', 'properties', 'property_images', 'reviews', 'review_photos', 'bookings',
    'payment_attempts', 'wishlists', 'messages', 'availability', 'payout_methods',
    'saved_searches', 'property_reports', 'support_requests', 'notifications',
    'trip_plans', 'trip_plan_items', 'calendar_feeds', 'calendar_imports',
    'calendar_import_events', 'seasonal_pricing', 'payout_ledger', 'email_messages',
    'email_webhook_events', 'email_rate_limits',
]
TEXT_DATA_TYPES = {'text', 'character varying', 'character', 'json', 'jsonb', 'uuid'}


def existing_tables(connection):
    return {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }


def target_column_types(target, table):
    with target.cursor() as cursor:
        cursor.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s",
            (table,),
        )
        return dict(cursor.fetchall())


def convert_row(row, columns, column_types):
    """Coerce SQLite values into shapes PostgreSQL accepts for the target column."""
    values = []
    for column, value in zip(columns, row):
        data_type = column_types.get(column, 'text')
        if isinstance(value, str) and value == '' and data_type not in TEXT_DATA_TYPES:
            value = None
        elif data_type == 'boolean' and isinstance(value, int):
            value = bool(value)
        values.append(value)
    return values


def copy_table(source, target, table, sql):
    rows = source.execute(f'SELECT * FROM "{table}"').fetchall()
    if not rows:
        return 0
    columns = [item[1] for item in source.execute(f'PRAGMA table_info("{table}")').fetchall()]
    column_types = target_column_types(target, table)
    statement = sql.SQL('INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING').format(
        sql.Identifier(table), sql.SQL(', ').join(map(sql.Identifier, columns)),
        sql.SQL(', ').join(sql.Placeholder() for _ in columns),
    )
    with target.cursor() as cursor:
        cursor.executemany(
            statement,
            [convert_row(row, columns, column_types) for row in rows],
        )
    return len(rows)


def synchronize_sequences(source, target):
    with target.cursor() as cursor:
        for table in TABLE_ORDER:
            columns = [item[1] for item in source.execute(f'PRAGMA table_info("{table}")').fetchall()]
            if 'id' not in columns:
                continue
            cursor.execute(f'SELECT MAX(id) FROM "{table}"')
            max_id = cursor.fetchone()[0]
            if max_id is None:
                continue
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence(%s, 'id'), %s, true)",
                (table, max_id),
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-url', default=os.getenv('DATABASE_URL'), help='Target PostgreSQL URL')
    parser.add_argument('--sqlite-path', type=Path, default=SQLITE_DATABASE,
                        help='Source SQLite database path')
    parser.add_argument('--apply', action='store_true', help='Actually write to PostgreSQL')
    parser.add_argument('--print-schema', action='store_true',
                        help='Print PostgreSQL DDL generated from schema.sql and exit')
    args = parser.parse_args()

    if args.print_schema:
        print(build_schema_sql())
        return
    if not args.database_url:
        parser.error('DATABASE_URL or --database-url is required.')
    if not args.sqlite_path.is_file():
        parser.error(f'SQLite database not found: {args.sqlite_path}')

    try:
        import psycopg
        from psycopg import sql
    except ImportError as error:
        raise SystemExit('Install requirements.txt before running the PostgreSQL migration.') from error

    with sqlite3.connect(args.sqlite_path) as source:
        tables = existing_tables(source)
        counts = {table: source.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                  for table in TABLE_ORDER if table in tables}
    print('Source SQLite is read-only for this migration.')
    for table, count in counts.items():
        print(f'{table}: {count}')
    if not args.apply:
        print('Dry run complete. Re-run with --apply after reviewing this summary.')
        return

    with sqlite3.connect(args.sqlite_path) as source, psycopg.connect(args.database_url) as target:
        with target.cursor() as cursor:
            cursor.execute(build_schema_sql())
        for table in TABLE_ORDER:
            if table in tables:
                copied = copy_table(source, target, table, sql)
                print(f'Copied {copied} rows from {table}.')
        synchronize_sequences(source, target)
        target.commit()
    print('Migration completed. Verify counts and application behavior before switching DATABASE_URL in production.')


if __name__ == '__main__':
    main()
