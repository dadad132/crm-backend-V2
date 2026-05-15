"""
Migration to add SMTP settings to incoming_email_account table.
This allows each email account to send replies using its own SMTP credentials
instead of relying on the workspace-level SMTP settings.
"""

import sqlite3
import os


def run_migration():
    db_path = "data.db"
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(incoming_email_account)")
        columns = [col[1] for col in cursor.fetchall()]
        
        new_columns = [
            ("smtp_host", "VARCHAR(255)"),
            ("smtp_port", "INTEGER DEFAULT 587"),
            ("smtp_username", "VARCHAR(255)"),
            ("smtp_password", "VARCHAR(255)"),
            ("smtp_use_tls", "BOOLEAN DEFAULT 1"),
            ("protocol", "VARCHAR(10) DEFAULT 'imap'"),
        ]
        
        for col_name, col_type in new_columns:
            if col_name not in columns:
                cursor.execute(f"ALTER TABLE incoming_email_account ADD COLUMN {col_name} {col_type}")
                print(f"Added column: {col_name}")
            else:
                print(f"Column '{col_name}' already exists, skipping.")
        
        conn.commit()
        print("Migration completed successfully: SMTP settings added to incoming_email_account")
        return True
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
