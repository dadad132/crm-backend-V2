"""
Migration script to add related_id and dismissed_at fields to notifications table
for interactive notification system with auto-dismiss and smart navigation.
"""

import sqlite3
from datetime import datetime

def migrate():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    print("Starting notification table migration...")
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(notification)")
    columns = [row[1] for row in cursor.fetchall()]
    
    try:
        # Add related_id column if it doesn't exist
        if 'related_id' not in columns:
            print("Adding related_id column...")
            cursor.execute("""
                ALTER TABLE notification 
                ADD COLUMN related_id INTEGER
            """)
            print("✓ Added related_id column")
        else:
            print("✓ related_id column already exists")
        
        # Add dismissed_at column if it doesn't exist
        if 'dismissed_at' not in columns:
            print("Adding dismissed_at column...")
            cursor.execute("""
                ALTER TABLE notification 
                ADD COLUMN dismissed_at TIMESTAMP
            """)
            print("✓ Added dismissed_at column")
        else:
            print("✓ dismissed_at column already exists")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
