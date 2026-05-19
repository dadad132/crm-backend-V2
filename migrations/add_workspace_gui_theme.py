"""Add gui_theme column to workspace table."""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate():
    db_path = 'data.db'
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}"); return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(workspace)")
        columns = {row[1] for row in cursor.fetchall()}
        if 'gui_theme' not in columns:
            cursor.execute("ALTER TABLE workspace ADD COLUMN gui_theme TEXT DEFAULT 'crimson'")
            print("[OK] Added gui_theme")
        else:
            print("[SKIP] gui_theme already exists")
        conn.commit()
        print("\n[DONE] Workspace gui_theme migration completed!")
    except Exception as e:
        print(f"[ERROR] {e}"); conn.rollback(); raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
