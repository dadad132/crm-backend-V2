#!/usr/bin/env python3
"""
Migration: Add timezone column to workspace table
Date: 2025-01-04
"""
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

def migrate():
    """Add timezone column to workspace table"""
    db_path = Path(__file__).parent.parent / "data.db"
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return False
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if timezone column exists
        cursor.execute("PRAGMA table_info(workspace)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'timezone' in columns:
            print("✅ timezone column already exists in workspace table")
            return True
        
        # Add timezone column
        print("📝 Adding timezone column to workspace table...")
        cursor.execute("""
            ALTER TABLE workspace 
            ADD COLUMN timezone TEXT DEFAULT 'UTC'
        """)
        
        # Set default timezone to UTC for existing workspaces
        cursor.execute("""
            UPDATE workspace 
            SET timezone = 'UTC' 
            WHERE timezone IS NULL
        """)
        
        conn.commit()
        print("✅ Successfully added timezone column to workspace table")
        print("ℹ️  Default timezone set to UTC for all existing workspaces")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Migration: Add timezone to workspace table")
    print("=" * 60)
    success = migrate()
    sys.exit(0 if success else 1)
