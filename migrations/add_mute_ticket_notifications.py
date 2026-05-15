"""
Add mute_ticket_notifications column to user table
"""
import sqlite3
from pathlib import Path

def migrate():
    """Add mute_ticket_notifications column to user table"""
    db_path = Path(__file__).parent.parent / 'data.db'
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'mute_ticket_notifications' not in columns:
            print("Adding mute_ticket_notifications column to user table...")
            cursor.execute("""
                ALTER TABLE user 
                ADD COLUMN mute_ticket_notifications INTEGER DEFAULT 0
            """)
            conn.commit()
            print("✓ Column added successfully")
        else:
            print("✓ Column already exists")
        
    except Exception as e:
        print(f"✗ Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
