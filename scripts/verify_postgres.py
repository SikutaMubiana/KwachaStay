"""Read-only PostgreSQL connectivity and required-table check."""
import argparse
import os

REQUIRED_TABLES = {'users', 'properties', 'bookings', 'property_images', 'email_messages'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database-url', default=os.getenv('DATABASE_URL'))
    args = parser.parse_args()
    if not args.database_url:
        parser.error('DATABASE_URL or --database-url is required.')
    try:
        import psycopg
    except ImportError as error:
        raise SystemExit('Install requirements.txt before running the PostgreSQL verification.') from error
    with psycopg.connect(args.database_url) as connection, connection.cursor() as cursor:
        cursor.execute('SELECT current_database(), current_user, version()')
        database, user, version = cursor.fetchone()
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        tables = {row[0] for row in cursor.fetchall()}
    missing = REQUIRED_TABLES - tables
    if missing:
        raise SystemExit(f'Missing required tables: {", ".join(sorted(missing))}')
    print(f'Connected to {database} as {user}. PostgreSQL: {version.split()[1]}.')
    print('Required KwachaStay tables are present.')


if __name__ == '__main__':
    main()
