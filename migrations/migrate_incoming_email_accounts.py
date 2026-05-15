"""
Migration to create incoming_email_accounts table for multiple email accounts per workspace.
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
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='incoming_email_account'
        """)
        if cursor.fetchone():
            print("Table 'incoming_email_account' already exists, skipping migration.")
            return True
        
        # Create the incoming_email_accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incoming_email_account (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL,
                name VARCHAR(100) NOT NULL,
                email_address VARCHAR(255) NOT NULL,
                project_id INTEGER,
                imap_host VARCHAR(255) NOT NULL,
                imap_port INTEGER DEFAULT 993,
                imap_username VARCHAR(255) NOT NULL,
                imap_password VARCHAR(255) NOT NULL,
                imap_use_ssl BOOLEAN DEFAULT 1,
                is_active BOOLEAN DEFAULT 1,
                auto_assign_to_user_id INTEGER,
                default_priority VARCHAR(20) DEFAULT 'medium',
                default_category VARCHAR(50) DEFAULT 'general',
                last_checked_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspace(id),
                FOREIGN KEY (project_id) REFERENCES project(id),
                FOREIGN KEY (auto_assign_to_user_id) REFERENCES user(id)
            )
        """)
        
        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_incoming_email_workspace 
            ON incoming_email_account(workspace_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_incoming_email_active 
            ON incoming_email_account(is_active)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_incoming_email_project 
            ON incoming_email_account(project_id)
        """)
        
        conn.commit()
        print("Migration completed: incoming_email_accounts table created successfully.")
        return True
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
