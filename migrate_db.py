import sqlite3

DATABASE = 'kwachastay.db'

def migrate():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    try:
        print("Adding payment_method column...")
        c.execute("ALTER TABLE bookings ADD COLUMN payment_method TEXT")
    except sqlite3.OperationalError as e:
        print(f"Skipping payment_method (probably exists): {e}")

    try:
        print("Adding duration column...")
        c.execute("ALTER TABLE bookings ADD COLUMN duration INTEGER")
    except sqlite3.OperationalError as e:
        print(f"Skipping duration (probably exists): {e}")

    try:
        print("Adding duration_unit column...")
        c.execute("ALTER TABLE bookings ADD COLUMN duration_unit TEXT DEFAULT 'night'")
    except sqlite3.OperationalError as e:
        print(f"Skipping duration_unit (probably exists): {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == '__main__':
    migrate()
