"""
Add soft delete fields to User table
"""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('data.db')
cursor = conn.cursor()

print("Adding soft delete fields to User table...")

try:
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(user)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'deleted_at' not in columns:
        print("  Adding 'deleted_at' column...")
        cursor.execute("ALTER TABLE user ADD COLUMN deleted_at DATETIME DEFAULT NULL")
        print("  ✓ deleted_at column added")
    else:
        print("  ✓ deleted_at column already exists")
    
    if 'deleted_by' not in columns:
        print("  Adding 'deleted_by' column...")
        cursor.execute("ALTER TABLE user ADD COLUMN deleted_by INTEGER DEFAULT NULL")
        print("  ✓ deleted_by column added")
    else:
        print("  ✓ deleted_by column already exists")
    
    conn.commit()
    
    # Create index on deleted_at for faster queries
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_user_deleted_at ON user (deleted_at)")
        print("  ✓ Index created on deleted_at")
    except Exception as e:
        print(f"  Note: Index might already exist: {e}")
    
    conn.commit()
    
    # Verify the changes
    cursor.execute("PRAGMA table_info(user)")
    columns = cursor.fetchall()
    print("\nUser table columns:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    
    # Count users
    cursor.execute("SELECT COUNT(*) FROM user WHERE deleted_at IS NULL")
    active_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM user WHERE deleted_at IS NOT NULL")
    deleted_count = cursor.fetchone()[0]
    
    print(f"\nUser statistics:")
    print(f"  Active users: {active_count}")
    print(f"  Deleted users: {deleted_count}")
    
    print("\n✓ Migration complete!")
    
except Exception as e:
    print(f"\n✗ Error during migration: {e}")
    conn.rollback()
finally:
    conn.close()
