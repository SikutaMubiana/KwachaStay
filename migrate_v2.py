import sqlite3

DATABASE = 'kwachastay.db'

def migrate_v2():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    print("Migrating Database v2...")

    # 1. Update users table
    try:
        c.execute("ALTER TABLE users ADD COLUMN profile_pic TEXT")
        print("Added profile_pic to users.")
    except sqlite3.OperationalError:
        print("Skipping profile_pic (exists).")

    # 2. Update properties table
    columns = ['is_verified BOOLEAN DEFAULT 0', 'latitude REAL', 'longitude REAL']
    for col in columns:
        col_name = col.split()[0]
        try:
            c.execute(f"ALTER TABLE properties ADD COLUMN {col}")
            print(f"Added {col_name} to properties.")
        except sqlite3.OperationalError:
             print(f"Skipping {col_name} (exists).")

    # 3. Create new tables
    c.execute("""
    CREATE TABLE IF NOT EXISTS property_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER NOT NULL,
        image_url TEXT NOT NULL,
        FOREIGN KEY (property_id) REFERENCES properties (id)
    )
    """)
    print("Created property_images table.")

    c.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (property_id) REFERENCES properties (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)
    print("Created reviews table.")

    conn.commit()
    conn.close()
    print("Migration v2 complete.")

if __name__ == '__main__':
    migrate_v2()
