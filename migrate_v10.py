import sqlite3
import os

DATABASE = 'kwachastay.db'

def migrate():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    print("Running migration v10...")

    # Add view_count to properties
    try:
        c.execute("ALTER TABLE properties ADD COLUMN view_count INTEGER DEFAULT 0")
        print("  Added 'view_count' column to properties.")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("  'view_count' column already exists.")
        else:
            raise

    # Init existing rows to 0
    c.execute("UPDATE properties SET view_count = 0 WHERE view_count IS NULL")

    conn.commit()
    conn.close()
    print("\nMigration v10 completed successfully!")
    print("  - Added: view_count column to properties")

if __name__ == '__main__':
    migrate()
