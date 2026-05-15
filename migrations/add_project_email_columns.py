"""
Migration: Add email-to-ticket columns to project table

Adds support_email and IMAP configuration columns to the project table
for the email-to-ticket integration system.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def migrate():
    """Add email columns to project table"""
    db_path = "data.db"
    
    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check which columns exist
        cursor.execute("PRAGMA table_info(project)")
        columns = {row[1] for row in cursor.fetchall()}
        print(f"Existing columns: {columns}")
        
        columns_to_add = {
            'support_email': 'ALTER TABLE project ADD COLUMN support_email TEXT',
            'imap_host': 'ALTER TABLE project ADD COLUMN imap_host TEXT',
            'imap_port': 'ALTER TABLE project ADD COLUMN imap_port INTEGER',
            'imap_username': 'ALTER TABLE project ADD COLUMN imap_username TEXT',
            'imap_password': 'ALTER TABLE project ADD COLUMN imap_password TEXT',
            'imap_use_ssl': 'ALTER TABLE project ADD COLUMN imap_use_ssl BOOLEAN DEFAULT 1'
        }
        
        for col_name, alter_sql in columns_to_add.items():
            if col_name not in columns:
                print(f"Adding column: {col_name}")
                cursor.execute(alter_sql)
                conn.commit()
                print(f"✓ Added {col_name}")
            else:
                print(f"✓ Column {col_name} already exists")
        
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
