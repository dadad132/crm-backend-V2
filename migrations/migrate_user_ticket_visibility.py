"""
Migration: Add can_see_all_tickets to users
Allows admins to grant specific users permission to see all tickets
"""

import sqlite3
from pathlib import Path

def migrate():
    """Add can_see_all_tickets field to user table"""
    
    db_path = Path(__file__).parent.parent / "data.db"
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'can_see_all_tickets' in columns:
            print("✅ Column 'can_see_all_tickets' already exists in user table")
            return
        
        # Add can_see_all_tickets column (default False)
        cursor.execute("""
            ALTER TABLE user 
            ADD COLUMN can_see_all_tickets BOOLEAN DEFAULT 0
        """)
        
        # Set admins to see all tickets by default
        cursor.execute("""
            UPDATE user 
            SET can_see_all_tickets = 1 
            WHERE is_admin = 1
        """)
        
        conn.commit()
        print("✅ Successfully added 'can_see_all_tickets' column to user table")
        print("✅ Set all admin users to see all tickets by default")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during migration: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
