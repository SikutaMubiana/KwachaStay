import sqlite3

DATABASE = 'kwachastay.db'

def migrate_v3():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    print("Migrating Database v3...")

    # Add user_id to bookings to track who made the booking
    try:
        c.execute("ALTER TABLE bookings ADD COLUMN user_id INTEGER")
        print("Added user_id to bookings.")
    except sqlite3.OperationalError:
        print("Skipping user_id (exists).")

    conn.commit()
    conn.close()
    print("Migration v3 complete.")

if __name__ == '__main__':
    migrate_v3()
