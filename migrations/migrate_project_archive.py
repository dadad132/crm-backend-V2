"""
Migration script to ensure is_archived field exists in project table.
This field allows archiving projects while preserving all data, comments, and attachments.
"""

import sqlite3

def migrate():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    print("Checking project table for archive support...")
    
    # Check if is_archived column exists
    cursor.execute("PRAGMA table_info(project)")
    columns = [row[1] for row in cursor.fetchall()]
    
    try:
        if 'is_archived' not in columns:
            print("Adding is_archived column...")
            cursor.execute("""
                ALTER TABLE project 
                ADD COLUMN is_archived BOOLEAN DEFAULT 0
            """)
            print("✓ Added is_archived column")
        else:
            print("✓ is_archived column already exists")
        
        # Ensure archived_at column exists for tracking
        if 'archived_at' not in columns:
            print("Adding archived_at column...")
            cursor.execute("""
                ALTER TABLE project 
                ADD COLUMN archived_at TIMESTAMP
            """)
            print("✓ Added archived_at column")
        else:
            print("✓ archived_at column already exists")
        
        conn.commit()
        print("\n✅ Project archive migration completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
