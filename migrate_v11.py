"""
migrate_v11.py
--------------
Adds:
  - bookings.booking_status (was missing from schema but used in app)
  - properties.view_count
  - users.password_reset_token, password_reset_expires
  - notifications table
  - messages.is_read (already exists in schema but just in case)
"""
import sqlite3
DATABASE = 'kwachastay.db'

def column_exists(db, table, column):
    rows = db.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)

def table_exists(db, table):
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None

db = sqlite3.connect(DATABASE)

# 1. bookings.booking_status
if not column_exists(db, 'bookings', 'booking_status'):
    db.execute("ALTER TABLE bookings ADD COLUMN booking_status TEXT DEFAULT 'pending'")
    print("Added bookings.booking_status")

# 2. properties.view_count
if not column_exists(db, 'properties', 'view_count'):
    db.execute("ALTER TABLE properties ADD COLUMN view_count INTEGER DEFAULT 0")
    print("Added properties.view_count")

# 3. users.password_reset_token
if not column_exists(db, 'users', 'password_reset_token'):
    db.execute("ALTER TABLE users ADD COLUMN password_reset_token TEXT")
    print("Added users.password_reset_token")

# 4. users.password_reset_expires
if not column_exists(db, 'users', 'password_reset_expires'):
    db.execute("ALTER TABLE users ADD COLUMN password_reset_expires REAL")
    print("Added users.password_reset_expires")

# 5. notifications table
if not table_exists(db, 'notifications'):
    db.execute("""
        CREATE TABLE notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            link TEXT,
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    print("Created notifications table")

# 6. messages.parent_id for threading
if not column_exists(db, 'messages', 'parent_id'):
    db.execute("ALTER TABLE messages ADD COLUMN parent_id INTEGER REFERENCES messages(id)")
    print("Added messages.parent_id")

db.commit()
db.close()
print("Migration v11 complete.")
