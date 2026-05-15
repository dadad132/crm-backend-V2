"""
Add task archiving fields to Task table
"""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('data.db')
cursor = conn.cursor()

print("Adding task archiving fields to Task table...")

try:
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(task)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'is_archived' not in columns:
        print("  Adding 'is_archived' column...")
        cursor.execute("ALTER TABLE task ADD COLUMN is_archived BOOLEAN DEFAULT 0")
        print("  ✓ is_archived column added")
    else:
        print("  ✓ is_archived column already exists")
    
    if 'archived_at' not in columns:
        print("  Adding 'archived_at' column...")
        cursor.execute("ALTER TABLE task ADD COLUMN archived_at DATETIME DEFAULT NULL")
        print("  ✓ archived_at column added")
    else:
        print("  ✓ archived_at column already exists")
    
    conn.commit()
    
    # Create index on is_archived for faster queries
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_task_is_archived ON task (is_archived)")
        print("  ✓ Index created on is_archived")
    except Exception as e:
        print(f"  Note: Index might already exist: {e}")
    
    conn.commit()
    
    # Verify the changes
    cursor.execute("PRAGMA table_info(task)")
    columns = cursor.fetchall()
    print("\nTask table columns (last 5):")
    for col in columns[-5:]:
        print(f"  - {col[1]} ({col[2]})")
    
    # Count tasks
    cursor.execute("SELECT COUNT(*) FROM task WHERE is_archived = 0")
    active_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM task WHERE is_archived = 1")
    archived_count = cursor.fetchone()[0]
    
    print(f"\nTask status:")
    print(f"  Active tasks: {active_count}")
    print(f"  Archived tasks: {archived_count}")
    
    print("\n✓ Migration completed successfully!")

except Exception as e:
    print(f"\nError during migration: {e}")
    conn.rollback()
    raise

finally:
    conn.close()
