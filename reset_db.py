"""
reset_db.py — Wipes ALL data from the KwachaStay database.
Run: python reset_db.py
This deletes all users, properties, bookings, reviews, etc.
and re-creates a fresh schema. Use only in development.
"""
import sqlite3
import os

DATABASE = 'kwachastay.db'

def reset():
    print("WARNING: This will DELETE all data in the database.")
    confirm = input("Type 'yes' to confirm: ").strip().lower()
    if confirm != 'yes':
        print("Aborted.")
        return

    # Delete the database file entirely and recreate from schema
    if os.path.exists(DATABASE):
        os.remove(DATABASE)
        print(f"  Deleted {DATABASE}")

    conn = sqlite3.connect(DATABASE)
    with open('schema.sql', 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

    print("SUCCESS: Database reset complete! Clean slate - no users, properties or bookings.")

if __name__ == '__main__':
    reset()
