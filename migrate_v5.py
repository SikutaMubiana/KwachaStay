import sqlite3

DATABASE = 'kwachastay.db'

def migrate_v5():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    print("Migrating Database v5...")

    try:
        # Add is_active column to properties
        c.execute('ALTER TABLE properties ADD COLUMN is_active BOOLEAN DEFAULT 1')
        print("Added is_active column to properties table.")
    except sqlite3.OperationalError:
        print("Column is_active already exists.")

    conn.commit()
    conn.close()
    print("Migration v5 complete.")

if __name__ == '__main__':
    migrate_v5()
