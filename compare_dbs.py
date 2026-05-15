import sqlite3
import os

db1_path = 'data.db.backup_test'
db2_path = 'data.db'

size1 = os.path.getsize(db1_path)
size2 = os.path.getsize(db2_path)
print(f"=== FILE SIZES ===")
print(f"  {db1_path}: {size1:,} bytes ({size1/1024/1024:.2f} MB)")
print(f"  {db2_path}: {size2:,} bytes ({size2/1024/1024:.2f} MB)")
print(f"  Difference: {size1 - size2:,} bytes ({(size1-size2)/1024:.1f} KB)")

conn1 = sqlite3.connect(db1_path)
conn2 = sqlite3.connect(db2_path)
c1 = conn1.cursor()
c2 = conn2.cursor()

# Get tables from both
c1.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables1 = set(r[0] for r in c1.fetchall())
c2.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables2 = set(r[0] for r in c2.fetchall())

only_in_backup = tables1 - tables2
only_in_current = tables2 - tables1
common = tables1 & tables2

print(f"\n=== TABLES ===")
print(f"  Backup: {len(tables1)} tables")
print(f"  Current: {len(tables2)} tables")
if only_in_backup:
    print(f"  Only in backup: {sorted(only_in_backup)}")
if only_in_current:
    print(f"  Only in current: {sorted(only_in_current)}")

print(f"\n=== ROW COUNT COMPARISON ===")
print(f"  {'Table':<30} {'Backup':>10} {'Current':>10} {'Diff':>10}  Status")
print(f"  {'-'*30} {'-'*10} {'-'*10} {'-'*10}  ------")

data_loss = []
data_gain = []

for t in sorted(common):
    c1.execute(f"SELECT COUNT(*) FROM [{t}]")
    count1 = c1.fetchone()[0]
    c2.execute(f"SELECT COUNT(*) FROM [{t}]")
    count2 = c2.fetchone()[0]
    diff = count2 - count1
    
    if diff < 0:
        status = "⚠ FEWER ROWS"
        data_loss.append((t, count1, count2, diff))
    elif diff > 0:
        status = "✓ more rows"
        data_gain.append((t, count1, count2, diff))
    else:
        status = "= same"
    
    print(f"  {t:<30} {count1:>10} {count2:>10} {diff:>+10}  {status}")

for t in sorted(only_in_backup):
    c1.execute(f"SELECT COUNT(*) FROM [{t}]")
    count1 = c1.fetchone()[0]
    print(f"  {t:<30} {count1:>10} {'N/A':>10} {'GONE':>10}  ⚠ TABLE MISSING")
    if count1 > 0:
        data_loss.append((t, count1, 0, -count1))

for t in sorted(only_in_current):
    c2.execute(f"SELECT COUNT(*) FROM [{t}]")
    count2 = c2.fetchone()[0]
    print(f"  {t:<30} {'N/A':>10} {count2:>10} {'NEW':>10}  + NEW TABLE")

# Deep compare: check if specific IDs are missing  
print(f"\n=== DETAILED CHECKS ON TABLES WITH FEWER ROWS ===")
for t, cnt1, cnt2, diff in data_loss:
    print(f"\n--- {t}: {cnt1} -> {cnt2} (lost {abs(diff)}) ---")
    
    # Get column names
    c1.execute(f"PRAGMA table_info([{t}])")
    cols1 = [r[1] for r in c1.fetchall()]
    c2.execute(f"PRAGMA table_info([{t}])")
    cols2 = [r[1] for r in c2.fetchall()]
    
    # Check if 'id' column exists
    if 'id' in cols1 and 'id' in cols2:
        c1.execute(f"SELECT id FROM [{t}] ORDER BY id")
        ids1 = set(r[0] for r in c1.fetchall())
        c2.execute(f"SELECT id FROM [{t}] ORDER BY id")
        ids2 = set(r[0] for r in c2.fetchall())
        
        missing_ids = ids1 - ids2
        new_ids = ids2 - ids1
        
        if missing_ids:
            missing_list = sorted(missing_ids)
            if len(missing_list) > 20:
                print(f"  Missing IDs ({len(missing_list)} total): {missing_list[:20]}... and {len(missing_list)-20} more")
            else:
                print(f"  Missing IDs: {missing_list}")
        if new_ids:
            new_list = sorted(new_ids)
            if len(new_list) > 20:
                print(f"  New IDs ({len(new_list)} total): {new_list[:20]}... and {len(new_list)-20} more")
            else:
                print(f"  New IDs: {new_list}")
                
        # For key tables, show what was lost
        if t in ('task', 'ticket', 'user', 'project', 'comment', 'ticketcomment') and missing_ids:
            id_col = 'id'
            if t == 'task':
                label_col = 'title'
            elif t == 'ticket':
                label_col = 'subject'
            elif t == 'user':
                label_col = 'username'
            elif t == 'project':
                label_col = 'name'
            elif t in ('comment', 'ticketcomment'):
                label_col = 'content'
            else:
                label_col = None
            
            if label_col and label_col in cols1:
                for mid in sorted(missing_ids)[:15]:
                    c1.execute(f"SELECT [{label_col}] FROM [{t}] WHERE id = ?", (mid,))
                    row = c1.fetchone()
                    val = row[0][:80] if row and row[0] else 'NULL'
                    print(f"    id={mid}: {val}")
    else:
        # No id column, just show column differences  
        only_cols_backup = set(cols1) - set(cols2)
        only_cols_current = set(cols2) - set(cols1)
        if only_cols_backup:
            print(f"  Columns only in backup: {only_cols_backup}")
        if only_cols_current:
            print(f"  Columns only in current: {only_cols_current}")

# Schema comparison for common tables
print(f"\n=== SCHEMA DIFFERENCES ===")
schema_diffs = 0
for t in sorted(common):
    c1.execute(f"PRAGMA table_info([{t}])")
    cols1 = [(r[1], r[2]) for r in c1.fetchall()]
    c2.execute(f"PRAGMA table_info([{t}])")
    cols2 = [(r[1], r[2]) for r in c2.fetchall()]
    
    cols1_names = set(c[0] for c in cols1)
    cols2_names = set(c[0] for c in cols2)
    
    only_backup = cols1_names - cols2_names
    only_current = cols2_names - cols1_names
    
    if only_backup or only_current:
        schema_diffs += 1
        print(f"  {t}:")
        if only_backup:
            print(f"    Only in backup: {sorted(only_backup)}")
        if only_current:
            print(f"    Only in current: {sorted(only_current)}")

if schema_diffs == 0:
    print("  No schema differences between the two databases.")

# Summary
print(f"\n{'='*60}")
print(f"=== SUMMARY ===")
print(f"{'='*60}")
if data_loss:
    print(f"  TABLES WITH DATA LOSS: {len(data_loss)}")
    for t, cnt1, cnt2, diff in data_loss:
        print(f"    {t}: {cnt1} -> {cnt2} ({diff})")
else:
    print(f"  NO DATA LOSS DETECTED")
if data_gain:
    print(f"  Tables with more data in current: {len(data_gain)}")
    for t, cnt1, cnt2, diff in data_gain:
        print(f"    {t}: {cnt1} -> {cnt2} (+{diff})")

conn1.close()
conn2.close()
