"""Add api_key and webhook tables."""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate():
    db_path = 'data.db'
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}"); return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        # --- APIKey table ---
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='apikey'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE apikey (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
                    name TEXT NOT NULL,
                    key_prefix TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT
                )
            """)
            cursor.execute("CREATE INDEX ix_apikey_workspace_id ON apikey(workspace_id)")
            cursor.execute("CREATE INDEX ix_apikey_key_hash ON apikey(key_hash)")
            cursor.execute("CREATE INDEX ix_apikey_key_prefix ON apikey(key_prefix)")
            print("[OK] Created apikey table")
        else:
            print("[SKIP] apikey table already exists")

        # --- Webhook table ---
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='webhook'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE webhook (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER NOT NULL REFERENCES workspace(id),
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    secret TEXT,
                    events TEXT NOT NULL DEFAULT 'ticket.created,ticket.closed',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_triggered_at TEXT,
                    last_status_code INTEGER
                )
            """)
            cursor.execute("CREATE INDEX ix_webhook_workspace_id ON webhook(workspace_id)")
            print("[OK] Created webhook table")
        else:
            print("[SKIP] webhook table already exists")

        conn.commit()
        print("\n[DONE] API keys & webhooks migration completed!")
    except Exception as e:
        print(f"[ERROR] {e}"); conn.rollback(); raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
