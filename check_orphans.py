import sqlite3

conn = sqlite3.connect('data.db')
cursor = conn.cursor()

print("=== USERS WITH NULL username/email ===")
cursor.execute("SELECT id, username, email, full_name, is_active, deleted_at FROM user WHERE username IS NULL OR email IS NULL")
for r in cursor.fetchall():
    print(f"  id={r[0]}, username={r[1]}, email={r[2]}, full_name={r[3]}, is_active={r[4]}, deleted_at={r[5]}")

print("\n=== ORPHAN: Assignment with invalid assignee_id ===")
cursor.execute("SELECT a.id, a.task_id, a.assignee_id FROM assignment a WHERE a.assignee_id NOT IN (SELECT id FROM user)")
for r in cursor.fetchall():
    print(f"  assignment_id={r[0]}, task_id={r[1]}, assignee_id={r[2]}")

print("\n=== ORPHAN: ProjectMembers with invalid project_id ===")
cursor.execute("SELECT pm.id, pm.project_id, pm.user_id FROM project_member pm WHERE pm.project_id NOT IN (SELECT id FROM project)")
for r in cursor.fetchall():
    print(f"  pm_id={r[0]}, project_id={r[1]}, user_id={r[2]}")

print("\n=== ORPHAN: ProjectMembers with invalid user_id ===")
cursor.execute("SELECT pm.id, pm.project_id, pm.user_id FROM project_member pm WHERE pm.user_id NOT IN (SELECT id FROM user)")
for r in cursor.fetchall():
    print(f"  pm_id={r[0]}, project_id={r[1]}, user_id={r[2]}")

print("\n=== ORPHAN: Notifications with invalid user_id (sample) ===")
cursor.execute("SELECT n.id, n.user_id, n.type, n.message FROM notification n WHERE n.user_id NOT IN (SELECT id FROM user) LIMIT 5")
for r in cursor.fetchall():
    print(f"  notif_id={r[0]}, user_id={r[1]}, type={r[2]}, msg={r[3][:80] if r[3] else 'NULL'}")

# Check if there are soft-deleted users  
print("\n=== SOFT-DELETED USERS ===")
cursor.execute("SELECT id, username, email, full_name, deleted_at, deleted_by FROM user WHERE deleted_at IS NOT NULL")
for r in cursor.fetchall():
    print(f"  id={r[0]}, username={r[1]}, email={r[2]}, full_name={r[3]}, deleted_at={r[4]}, deleted_by={r[5]}")

# Check all user IDs to understand gaps
print("\n=== ALL USER IDs ===")
cursor.execute("SELECT id, username, full_name, is_active, deleted_at FROM user ORDER BY id")
for r in cursor.fetchall():
    print(f"  id={r[0]}, username={r[1]}, full_name={r[2]}, active={r[3]}, deleted={r[4]}")

conn.close()
