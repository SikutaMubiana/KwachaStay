import sqlite3

DATABASE = 'kwachastay.db'

def migrate():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    print("Creating payout_methods table...")
    c.execute('''
        CREATE TABLE IF NOT EXISTS payout_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL, -- 'Bank Transfer', 'Mobile Money', 'Airtel Money', 'MTN Money'
            bank_name TEXT,
            account_name TEXT NOT NULL,
            account_number TEXT NOT NULL,
            branch_code TEXT,
            is_primary BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Migration v7 (Payout Methods) completed successfully.")

if __name__ == '__main__':
    migrate()
