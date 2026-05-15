"""
Add branding columns to workspace table
"""
import sqlite3
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate():
    """Add branding columns to workspace table"""
    db_path = 'data.db'
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check existing columns
        cursor.execute("PRAGMA table_info(workspace)")
        columns = {row[1] for row in cursor.fetchall()}
        print(f"Existing workspace columns: {columns}")
        
        # Add site_title column
        if 'site_title' not in columns:
            print("Adding site_title column...")
            cursor.execute("ALTER TABLE workspace ADD COLUMN site_title TEXT")
            print("✓ Added site_title")
        else:
            print("✓ site_title already exists")
        
        # Add logo_url column
        if 'logo_url' not in columns:
            print("Adding logo_url column...")
            cursor.execute("ALTER TABLE workspace ADD COLUMN logo_url TEXT")
            print("✓ Added logo_url")
        else:
            print("✓ logo_url already exists")
        
        # Add favicon_url column
        if 'favicon_url' not in columns:
            print("Adding favicon_url column...")
            cursor.execute("ALTER TABLE workspace ADD COLUMN favicon_url TEXT")
            print("✓ Added favicon_url")
        else:
            print("✓ favicon_url already exists")
        
        # Add primary_color column
        if 'primary_color' not in columns:
            print("Adding primary_color column...")
            cursor.execute("ALTER TABLE workspace ADD COLUMN primary_color TEXT DEFAULT '#2563eb'")
            print("✓ Added primary_color")
        else:
            print("✓ primary_color already exists")
        
        conn.commit()
        print("\n✅ Workspace branding migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
