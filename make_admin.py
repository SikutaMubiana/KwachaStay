import sqlite3
import sys

DATABASE = 'kwachastay.db'

def make_admin(email):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Check if user exists
    user = c.execute('SELECT id, full_name FROM users WHERE email = ?', (email,)).fetchone()
    
    if not user:
        print(f"Error: User with email '{email}' not found.")
        return

    # Update to admin
    c.execute('UPDATE users SET is_admin = 1 WHERE email = ?', (email,))
    conn.commit()
    conn.close()
    print(f"Success! User '{user[1]}' ({email}) is now an Admin.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python make_admin.py <email>")
        print("Example: python make_admin.py user@example.com")
    else:
        make_admin(sys.argv[1])
