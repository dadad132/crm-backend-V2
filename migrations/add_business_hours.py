"""
Migration: Add business hours settings to workspace table
Run this after deploying the updated code.
"""
import sqlite3
from pathlib import Path


def migrate():
    db_path = Path("data.db")
    if not db_path.exists():
        print("❌ Database not found at data.db")
        return False
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    print("Migration: Add business hours to workspace table")
    print("=" * 50)
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(workspace)")
    columns = [col[1] for col in cursor.fetchall()]
    
    changes_made = False
    
    # Add business_hours_start
    if 'business_hours_start' not in columns:
        print("📝 Adding business_hours_start column...")
        cursor.execute("ALTER TABLE workspace ADD COLUMN business_hours_start TEXT DEFAULT '07:30'")
        changes_made = True
    else:
        print("✓ business_hours_start column already exists")
    
    # Add business_hours_end
    if 'business_hours_end' not in columns:
        print("📝 Adding business_hours_end column...")
        cursor.execute("ALTER TABLE workspace ADD COLUMN business_hours_end TEXT DEFAULT '16:00'")
        changes_made = True
    else:
        print("✓ business_hours_end column already exists")
    
    # Add business_hours_exclude_weekends
    if 'business_hours_exclude_weekends' not in columns:
        print("📝 Adding business_hours_exclude_weekends column...")
        cursor.execute("ALTER TABLE workspace ADD COLUMN business_hours_exclude_weekends INTEGER DEFAULT 1")
        changes_made = True
    else:
        print("✓ business_hours_exclude_weekends column already exists")
    
    if changes_made:
        conn.commit()
        print("\n✅ Migration completed successfully!")
        print("ℹ️  Default business hours set to 07:30 - 16:00, excluding weekends")
    else:
        print("\n✓ No changes needed - all columns already exist")
    
    conn.close()
    return True


if __name__ == "__main__":
    migrate()
