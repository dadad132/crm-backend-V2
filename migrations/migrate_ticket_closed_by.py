"""
Migration: Add closed_by_id to tickets
Tracks which user closed the ticket
"""

import sqlite3
from pathlib import Path

def migrate():
    """Add closed_by_id field to ticket table"""
    
    db_path = Path(__file__).parent.parent / "data.db"
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(ticket)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'closed_by_id' in columns:
            print("✅ Column 'closed_by_id' already exists in ticket table")
            return
        
        # Add closed_by_id column
        cursor.execute("""
            ALTER TABLE ticket 
            ADD COLUMN closed_by_id INTEGER REFERENCES user(id)
        """)
        
        conn.commit()
        print("✅ Successfully added 'closed_by_id' column to ticket table")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during migration: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
