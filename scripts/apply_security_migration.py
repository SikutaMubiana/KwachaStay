"""Apply additive security schema migrations to Supabase PostgreSQL or SQLite.

Idempotent: creates tables/indexes and adds columns only if they do not exist,
preserving all existing records.

Usage:
    python scripts/apply_security_migration.py
    python scripts/apply_security_migration.py --check
"""
import argparse
import os
from pathlib import Path
import sqlite3

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

POSTGRES_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS admin_audit_logs (
        id BIGSERIAL PRIMARY KEY,
        admin_id INTEGER,
        admin_email TEXT,
        action TEXT NOT NULL,
        target_type TEXT,
        target_id TEXT,
        details TEXT,
        ip_address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (admin_id) REFERENCES users (id) ON DELETE SET NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_created_at
    ON admin_audit_logs(created_at DESC)
    """,
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS session_version INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled INTEGER NOT NULL DEFAULT 0",
]


def migrate_postgres(database_url, check_only=False):
    import psycopg

    with psycopg.connect(database_url, connect_timeout=15, application_name='kwachastay-security-migration') as conn:
        with conn.cursor() as cur:
            if not check_only:
                for stmt in POSTGRES_STATEMENTS:
                    cur.execute(stmt)
                conn.commit()
                print('Applied security schema migration to PostgreSQL (Supabase).')

            cur.execute("SELECT to_regclass('public.admin_audit_logs')")
            audit_table = cur.fetchone()[0]
            cur.execute(
                """SELECT column_name FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'users'
                     AND column_name IN ('session_version', 'totp_secret', 'totp_enabled')
                   ORDER BY column_name"""
            )
            user_cols = [row[0] for row in cur.fetchall()]
            print(f'PostgreSQL verification -> admin_audit_logs: {audit_table}, users security columns: {user_cols}')
            if audit_table is None or set(user_cols) != {'session_version', 'totp_secret', 'totp_enabled'}:
                raise SystemExit('PostgreSQL security migration verification failed.')


def migrate_sqlite(db_path, check_only=False):
    with sqlite3.connect(db_path) as conn:
        if not check_only:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS admin_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER,
                    admin_email TEXT,
                    action TEXT NOT NULL,
                    target_type TEXT,
                    target_id TEXT,
                    details TEXT,
                    ip_address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (admin_id) REFERENCES users (id) ON DELETE SET NULL
                )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_created_at ON admin_audit_logs(created_at DESC)"
            )
            cols = {row[1] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
            for name, ddl in {
                'session_version': 'INTEGER NOT NULL DEFAULT 1',
                'totp_secret': 'TEXT',
                'totp_enabled': 'BOOLEAN NOT NULL DEFAULT 0',
            }.items():
                if name not in cols:
                    conn.execute(f'ALTER TABLE users ADD COLUMN {name} {ddl}')
            conn.commit()
            print(f'Applied security schema migration to SQLite ({db_path}).')

        has_audit = bool(
            conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='admin_audit_logs'").fetchone()
        )
        cols = sorted(
            row[1]
            for row in conn.execute('PRAGMA table_info(users)').fetchall()
            if row[1] in {'session_version', 'totp_secret', 'totp_enabled'}
        )
        print(f'SQLite verification -> admin_audit_logs: {has_audit}, users security columns: {cols}')


def main():
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser(description='Apply KwachaStay security schema migrations.')
    parser.add_argument('--check', action='store_true', help='Verify schema without modifying.')
    parser.add_argument('--sqlite-only', action='store_true', help='Target local kwachastay.db only.')
    args = parser.parse_args()

    sqlite_path = ROOT / 'kwachastay.db'
    if sqlite_path.is_file():
        migrate_sqlite(sqlite_path, check_only=args.check)

    db_url = '' if args.sqlite_only else os.getenv('DATABASE_URL', '').strip()
    if db_url:
        migrate_postgres(db_url, check_only=args.check)
    elif not args.sqlite_only:
        print('DATABASE_URL is not set; skipped PostgreSQL migration.')


if __name__ == '__main__':
    main()
