"""
Add meeting cancellation fields to Meeting table
"""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('data.db')
cursor = conn.cursor()

print("Adding meeting cancellation fields to Meeting table...")

try:
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(meeting)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'is_cancelled' not in columns:
        print("  Adding 'is_cancelled' column...")
        cursor.execute("ALTER TABLE meeting ADD COLUMN is_cancelled BOOLEAN DEFAULT 0")
        print("  ✓ is_cancelled column added")
    else:
        print("  ✓ is_cancelled column already exists")
    
    if 'cancelled_at' not in columns:
        print("  Adding 'cancelled_at' column...")
        cursor.execute("ALTER TABLE meeting ADD COLUMN cancelled_at DATETIME DEFAULT NULL")
        print("  ✓ cancelled_at column added")
    else:
        print("  ✓ cancelled_at column already exists")
    
    if 'cancelled_by' not in columns:
        print("  Adding 'cancelled_by' column...")
        cursor.execute("ALTER TABLE meeting ADD COLUMN cancelled_by INTEGER DEFAULT NULL")
        print("  ✓ cancelled_by column added")
    else:
        print("  ✓ cancelled_by column already exists")
    
    conn.commit()
    
    # Create index on is_cancelled for faster queries
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_meeting_is_cancelled ON meeting (is_cancelled)")
        print("  ✓ Index created on is_cancelled")
    except Exception as e:
        print(f"  Note: Index might already exist: {e}")
    
    conn.commit()
    
    # Verify the changes
    cursor.execute("PRAGMA table_info(meeting)")
    columns = cursor.fetchall()
    print("\nMeeting table columns (last 5):")
    for col in columns[-5:]:
        print(f"  - {col[1]} ({col[2]})")
    
    # Count meetings
    cursor.execute("SELECT COUNT(*) FROM meeting WHERE is_cancelled = 0")
    active_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM meeting WHERE is_cancelled = 1")
    cancelled_count = cursor.fetchone()[0]
    
    print(f"\nMeeting status:")
    print(f"  Active meetings: {active_count}")
    print(f"  Cancelled meetings: {cancelled_count}")
    
    print("\n✓ Migration completed successfully!")

except Exception as e:
    print(f"\nError during migration: {e}")
    conn.rollback()
    raise

finally:
    conn.close()
