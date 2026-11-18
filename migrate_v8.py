import sqlite3

DATABASE = 'kwachastay.db'

def migrate():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # --- Add missing columns ---
    
    # Add is_admin to users
    try:
        c.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0")
        print("  Added 'is_admin' column to users.")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("  'is_admin' column already exists in users.")
        else:
            raise
    
    # Add is_active to properties
    try:
        c.execute("ALTER TABLE properties ADD COLUMN is_active BOOLEAN DEFAULT 1")
        print("  Added 'is_active' column to properties.")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("  'is_active' column already exists in properties.")
        else:
            raise
    
    # --- Create missing tables ---
    
    print("Creating wishlists table...")
    c.execute('''
        CREATE TABLE IF NOT EXISTS wishlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            property_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, property_id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (property_id) REFERENCES properties (id)
        )
    ''')
    
    print("Creating messages table...")
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            property_id INTEGER,
            content TEXT NOT NULL,
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id),
            FOREIGN KEY (property_id) REFERENCES properties (id)
        )
    ''')
    
    print("Creating availability table...")
    c.execute('''
        CREATE TABLE IF NOT EXISTS availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            date DATE NOT NULL,
            status TEXT DEFAULT 'blocked',
            UNIQUE(property_id, date),
            FOREIGN KEY (property_id) REFERENCES properties (id)
        )
    ''')
    
    # Set all existing properties to active
    c.execute("UPDATE properties SET is_active = 1 WHERE is_active IS NULL")
    
    conn.commit()
    conn.close()
    print("\nMigration v8 completed successfully!")
    print("  - Added missing columns: is_admin (users), is_active (properties)")
    print("  - Created tables: wishlists, messages, availability")

if __name__ == '__main__':
    migrate()
