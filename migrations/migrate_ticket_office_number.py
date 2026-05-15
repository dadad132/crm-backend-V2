"""
Migration script to add guest_office_number column to tickets table
"""
import sqlite3
from pathlib import Path

def migrate():
    db_path = Path(__file__).parent / "data.db"
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(ticket)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'guest_office_number' in columns:
            print("✅ Column 'guest_office_number' already exists in tickets table")
            return
        
        # Add the column
        print("Adding guest_office_number column to tickets table...")
        cursor.execute("ALTER TABLE ticket ADD COLUMN guest_office_number TEXT")
        conn.commit()
        
        print("✅ Successfully added guest_office_number column to tickets table")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
