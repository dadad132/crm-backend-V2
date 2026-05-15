"""
Migration: Add support_email field to project table
This allows each project to have a dedicated support email address
for auto-creating tickets via email
"""

import sqlite3
from pathlib import Path

def migrate():
    db_path = Path("data.db")
    
    if not db_path.exists():
        print("❌ Database file not found!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(project)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'support_email' in columns:
            print("✅ Column 'support_email' already exists in project table")
            return
        
        # Add the new column
        print("📝 Adding support_email column to project table...")
        cursor.execute("""
            ALTER TABLE project
            ADD COLUMN support_email TEXT
        """)
        
        conn.commit()
        print("✅ Migration completed successfully!")
        print("   - Added 'support_email' column to project table")
        print("   - Projects can now have dedicated support email addresses")
        print("   - Emails sent to these addresses will auto-create tickets in the project")
        
    except sqlite3.Error as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("  Project Support Email Migration")
    print("=" * 60)
    migrate()
