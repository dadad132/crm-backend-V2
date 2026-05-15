"""
Migration to ensure comment table has author_id column
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
        # Check if comment table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comment'")
        if not cursor.fetchone():
            print("✅ comment table doesn't exist yet, no migration needed")
            return
        
        # Check current columns
        cursor.execute("PRAGMA table_info(comment)")
        columns = {row[1] for row in cursor.fetchall()}
        print(f"Current comment table columns: {columns}")
        
        if 'author_id' in columns:
            print("✅ author_id column already exists in comment table")
            return
        
        print("Adding author_id column to comment table...")
        
        # Add author_id column if it doesn't exist
        cursor.execute("""
            ALTER TABLE comment 
            ADD COLUMN author_id INTEGER REFERENCES user(id)
        """)
        
        conn.commit()
        print("✅ Successfully added author_id column to comment table")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
