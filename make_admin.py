"""Promote, revoke, or list KwachaStay administrator accounts.

Automatically uses Supabase PostgreSQL when DATABASE_URL is set in .env or the
environment, and falls back to local kwachastay.db (SQLite) otherwise.

Examples:
    python make_admin.py admin@example.com
    python make_admin.py --revoke admin@example.com
    python make_admin.py --list
    python make_admin.py --sqlite admin@example.com
"""
import argparse
import os
import sqlite3

from dotenv import load_dotenv

import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_PATH = os.path.join(BASE_DIR, 'kwachastay.db')


def open_db(force_sqlite=False):
    load_dotenv()
    db_url = '' if force_sqlite else os.getenv('DATABASE_URL', '').strip()
    if db_url:
        return database.connect(db_url), 'PostgreSQL (DATABASE_URL)'
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn, f'SQLite ({SQLITE_PATH})'


def list_admins(conn, backend_label):
    rows = conn.execute(
        'SELECT id, full_name, email, role FROM users WHERE is_admin = 1 ORDER BY id'
    ).fetchall()
    print(f'Database: {backend_label}')
    if not rows:
        print('No admin users found.')
        return
    print(f'Admin users ({len(rows)}):')
    for row in rows:
        print(f"  - #{row['id']} {row['full_name']} <{row['email']}> (role={row['role']})")


def set_admin(conn, backend_label, email, is_admin):
    normalized = email.strip().lower()
    user = conn.execute(
        'SELECT id, full_name, email, is_admin FROM users WHERE LOWER(email) = ?',
        (normalized,),
    ).fetchone()
    if not user:
        raise SystemExit(f"Error: User with email '{email}' not found in {backend_label}.")
    conn.execute('UPDATE users SET is_admin = ? WHERE id = ?', (1 if is_admin else 0, user['id']))
    conn.commit()
    action = 'granted admin access' if is_admin else 'revoked admin access'
    print(f"Success! {action} for '{user['full_name']}' ({user['email']}) in {backend_label}.")


def main():
    parser = argparse.ArgumentParser(description='Manage KwachaStay admin accounts.')
    parser.add_argument('email', nargs='?', help='User email address to promote or revoke.')
    parser.add_argument('--revoke', action='store_true', help='Remove admin access instead of granting it.')
    parser.add_argument('--list', action='store_true', help='List all current admin accounts.')
    parser.add_argument('--sqlite', action='store_true', help='Target local kwachastay.db even if DATABASE_URL is set.')
    args = parser.parse_args()

    conn, backend_label = open_db(force_sqlite=args.sqlite)
    try:
        if args.list:
            list_admins(conn, backend_label)
            return
        if not args.email:
            parser.print_help()
            return
        set_admin(conn, backend_label, args.email, is_admin=not args.revoke)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
