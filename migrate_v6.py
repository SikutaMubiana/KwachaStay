import sqlite3

DATABASE = 'kwachastay.db'

def migrate_v6():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    print("Migrating Database v6...")

    # 1. Create Availability Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            date DATE NOT NULL,
            status TEXT DEFAULT 'blocked', -- 'blocked' or 'booked'
            FOREIGN KEY (property_id) REFERENCES properties (id),
            UNIQUE(property_id, date)
        )
    ''')
    print("Created availability table.")

    # 2. Add is_admin to users
    try:
        c.execute('ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0')
        print("Added is_admin column to users table.")
    except sqlite3.OperationalError:
        print("Column is_admin already exists.")

    conn.commit()
    conn.close()
    print("Migration v6 complete.")

if __name__ == '__main__':
    migrate_v6()
