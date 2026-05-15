"""
Migration script to create call tables for WebRTC calling feature
"""
import sqlite3
import sys
from pathlib import Path

def run_migration():
    db_path = Path("data.db")
    
    if not db_path.exists():
        print("Database not found. Tables will be created on first run.")
        return True
    
    print("=" * 60)
    print("Creating Call Tables for WebRTC Calling Feature")
    print("=" * 60)
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Create call table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS call (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caller_id INTEGER NOT NULL REFERENCES user(id),
                recipient_id INTEGER NOT NULL REFERENCES user(id),
                workspace_id INTEGER NOT NULL REFERENCES workspace(id),
                call_type VARCHAR DEFAULT 'voice',
                status VARCHAR DEFAULT 'ringing',
                offer_sdp TEXT,
                answer_sdp TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                answered_at DATETIME,
                ended_at DATETIME,
                duration_seconds INTEGER,
                end_reason VARCHAR
            )
        """)
        print("✅ Created 'call' table")
        
        # Create indexes for call table
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_call_caller ON call(caller_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_call_recipient ON call(recipient_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_call_workspace ON call(workspace_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_call_status ON call(status)")
        print("✅ Created indexes for 'call' table")
        
        # Create call_ice_candidate table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_ice_candidate (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id INTEGER NOT NULL REFERENCES call(id) ON DELETE CASCADE,
                from_user_id INTEGER NOT NULL REFERENCES user(id),
                candidate_data TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Created 'call_ice_candidate' table")
        
        # Create index for ice candidates
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ice_call ON call_ice_candidate(call_id)")
        print("✅ Created indexes for 'call_ice_candidate' table")
        
        conn.commit()
        print("\n" + "=" * 60)
        print("✅ Call tables created successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
    
    return True

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
