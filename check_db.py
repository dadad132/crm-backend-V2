import sqlite3
conn = sqlite3.connect('data.db')
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cursor.fetchall()]
print("=== TABLES IN DATABASE ===")
for t in tables:
    print(f"  {t}")
print(f"\nTotal: {len(tables)} tables\n")

# For each table, show columns and row count
for t in tables:
    cursor.execute(f"PRAGMA table_info({t})")
    cols = cursor.fetchall()
    cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
    count = cursor.fetchone()[0]
    print(f"\n--- {t} ({count} rows) ---")
    for c in cols:
        print(f"  {c[1]} ({c[2]})")

conn.close()
