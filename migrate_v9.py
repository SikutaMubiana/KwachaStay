import sqlite3
import os

DATABASE = 'kwachastay.db'

def migrate():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    print("Running migration v9...")

    # Add booking_status to bookings (host approval: pending/confirmed/declined/completed)
    try:
        c.execute("ALTER TABLE bookings ADD COLUMN booking_status TEXT DEFAULT 'pending'")
        print("  Added 'booking_status' column to bookings.")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("  'booking_status' column already exists in bookings.")
        else:
            raise

    # Set all existing bookings to 'pending' if null
    c.execute("UPDATE bookings SET booking_status = 'pending' WHERE booking_status IS NULL")

    # Create uploads directory for file uploads
    uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    print(f"  Ensured uploads directory exists at: {uploads_dir}")

    conn.commit()
    conn.close()
    print("\nMigration v9 completed successfully!")
    print("  - Added: booking_status column to bookings")
    print("  - Created: static/uploads/ directory for image uploads")

if __name__ == '__main__':
    migrate()
