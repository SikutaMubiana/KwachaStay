import sqlite3

DATABASE = 'kwachastay.db'

def migrate_v4():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    print("Migrating Database v4...")

    # Create Wishlists Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS wishlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            property_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (property_id) REFERENCES properties (id),
            UNIQUE(user_id, property_id)
        )
    ''')
    print("Created wishlists table.")

    # Create Messages Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            property_id INTEGER, -- Optional: context about which property
            content TEXT NOT NULL,
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id),
            FOREIGN KEY (property_id) REFERENCES properties (id)
        )
    ''')
    print("Created messages table.")

    conn.commit()
    conn.close()
    print("Migration v4 complete.")

if __name__ == '__main__':
    migrate_v4()
