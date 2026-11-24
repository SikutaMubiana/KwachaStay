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
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_city TEXT",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS room_sharing TEXT",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS upfront_months INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS hourly_rate DOUBLE PRECISION",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS city TEXT NOT NULL DEFAULT 'Lusaka'",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS furnishing_status TEXT DEFAULT 'unfurnished'",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS master_self_contained INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS zesco_meter_type TEXT DEFAULT ''",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS listing_source TEXT DEFAULT 'owner'",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS viewing_fee DOUBLE PRECISION NOT NULL DEFAULT 0",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS security_fence TEXT DEFAULT ''",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS nearby_university TEXT DEFAULT ''",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS campus_distance TEXT DEFAULT ''",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS boarding_gender TEXT DEFAULT ''",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS gate_curfew_policy TEXT DEFAULT ''",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS bed_spaces_left INTEGER",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS semester_rate DOUBLE PRECISION",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS has_study_desk INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS has_bed_mattress INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS has_stove_fridge INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS has_laundry_area INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS has_study_backup_power INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS yard_type TEXT DEFAULT ''",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS has_paved_yard INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS is_pet_friendly INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS is_family_friendly INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS has_private_entrance INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS has_smart_tv INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS couples_friendly INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS allows_small_gatherings INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS offers_airport_transfer INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS video_tour_url TEXT DEFAULT ''",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS availability_prompted_at TIMESTAMP",
    """
    CREATE TABLE IF NOT EXISTS property_viewings (
        id BIGSERIAL PRIMARY KEY,
        property_id INTEGER NOT NULL,
        tenant_id INTEGER NOT NULL,
        owner_id INTEGER NOT NULL,
        viewing_date TEXT NOT NULL,
        viewing_time TEXT NOT NULL,
        visitor_name TEXT NOT NULL,
        visitor_phone TEXT NOT NULL,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        owner_response_note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (property_id) REFERENCES properties (id) ON DELETE CASCADE,
        FOREIGN KEY (tenant_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (owner_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_property_viewings_owner ON property_viewings(owner_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_property_viewings_tenant ON property_viewings(tenant_id, created_at DESC)",
    """
    CREATE OR REPLACE FUNCTION julianday(ts timestamp without time zone, modifier text DEFAULT NULL)
    RETURNS double precision
    LANGUAGE sql STABLE
    AS $$
        SELECT julianday(ts::text, modifier)
    $$
    """,
    """
    CREATE OR REPLACE FUNCTION julianday(ts timestamp with time zone, modifier text DEFAULT NULL)
    RETURNS double precision
    LANGUAGE sql STABLE
    AS $$
        SELECT julianday((ts AT TIME ZONE 'UTC')::text, modifier)
    $$
    """,
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
                'preferred_city': 'TEXT',
            }.items():
                if name not in cols:
                    conn.execute(f'ALTER TABLE users ADD COLUMN {name} {ddl}')
            prop_cols = {row[1] for row in conn.execute('PRAGMA table_info(properties)').fetchall()}
            for name, ddl in {
                'room_sharing': 'TEXT',
                'upfront_months': 'INTEGER NOT NULL DEFAULT 1',
                'hourly_rate': 'REAL',
                'city': "TEXT NOT NULL DEFAULT 'Lusaka'",
                'furnishing_status': "TEXT DEFAULT 'unfurnished'",
                'master_self_contained': 'BOOLEAN NOT NULL DEFAULT 0',
                'zesco_meter_type': "TEXT DEFAULT ''",
                'listing_source': "TEXT DEFAULT 'owner'",
                'viewing_fee': 'REAL NOT NULL DEFAULT 0',
                'security_fence': "TEXT DEFAULT ''",
                'nearby_university': "TEXT DEFAULT ''",
                'campus_distance': "TEXT DEFAULT ''",
                'boarding_gender': "TEXT DEFAULT ''",
                'gate_curfew_policy': "TEXT DEFAULT ''",
                'bed_spaces_left': 'INTEGER',
                'semester_rate': 'REAL',
                'has_study_desk': 'BOOLEAN NOT NULL DEFAULT 0',
                'has_bed_mattress': 'BOOLEAN NOT NULL DEFAULT 0',
                'has_stove_fridge': 'BOOLEAN NOT NULL DEFAULT 0',
                'has_laundry_area': 'BOOLEAN NOT NULL DEFAULT 0',
                'has_study_backup_power': 'BOOLEAN NOT NULL DEFAULT 0',
                'yard_type': "TEXT DEFAULT ''",
                'has_paved_yard': 'BOOLEAN NOT NULL DEFAULT 0',
                'is_pet_friendly': 'BOOLEAN NOT NULL DEFAULT 0',
                'is_family_friendly': 'BOOLEAN NOT NULL DEFAULT 0',
                'has_private_entrance': 'BOOLEAN NOT NULL DEFAULT 0',
                'has_smart_tv': 'BOOLEAN NOT NULL DEFAULT 0',
                'couples_friendly': 'BOOLEAN NOT NULL DEFAULT 0',
                'allows_small_gatherings': 'BOOLEAN NOT NULL DEFAULT 0',
                'offers_airport_transfer': 'BOOLEAN NOT NULL DEFAULT 0',
                'video_tour_url': "TEXT DEFAULT ''",
                'availability_prompted_at': 'TIMESTAMP',
            }.items():
                if name not in prop_cols:
                    conn.execute(f'ALTER TABLE properties ADD COLUMN {name} {ddl}')
            conn.execute(
                """CREATE TABLE IF NOT EXISTS property_viewings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    property_id INTEGER NOT NULL,
                    tenant_id INTEGER NOT NULL,
                    owner_id INTEGER NOT NULL,
                    viewing_date TEXT NOT NULL,
                    viewing_time TEXT NOT NULL,
                    visitor_name TEXT NOT NULL,
                    visitor_phone TEXT NOT NULL,
                    notes TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    owner_response_note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (property_id) REFERENCES properties (id) ON DELETE CASCADE,
                    FOREIGN KEY (tenant_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (owner_id) REFERENCES users (id) ON DELETE CASCADE
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_property_viewings_owner ON property_viewings(owner_id, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_property_viewings_tenant ON property_viewings(tenant_id, created_at DESC)")
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
