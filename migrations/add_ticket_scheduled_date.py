"""
Migration to add scheduled_date column to ticket table
"""
import sqlite3
import sys
from pathlib import Path

def migrate():
    # Determine database path
    db_path = Path(__file__).parent.parent / 'data.db'
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if ticket table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ticket'")
        if not cursor.fetchone():
            print("✅ ticket table doesn't exist yet, no migration needed")
            return
        
        # Check current columns
        cursor.execute("PRAGMA table_info(ticket)")
        columns = {row[1] for row in cursor.fetchall()}
        print(f"Current ticket table columns: {columns}")
        
        if 'scheduled_date' in columns:
            print("✅ scheduled_date column already exists in ticket table")
            return
        
        print("Adding scheduled_date column to ticket table...")
        
        # Add scheduled_date column
        cursor.execute("""
            ALTER TABLE ticket 
            ADD COLUMN scheduled_date DATETIME
        """)
        
        conn.commit()
        print("✅ Successfully added scheduled_date column to ticket table")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
