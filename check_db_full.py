import sqlite3

conn = sqlite3.connect('data.db')
cursor = conn.cursor()

# Collect all DB columns per table
db_schema = {}
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cursor.fetchall()]
for t in tables:
    cursor.execute(f"PRAGMA table_info({t})")
    db_schema[t] = [c[1] for c in cursor.fetchall()]

# Check specific known model columns vs DB
issues = []

# --- emailsettings ---
es_cols = db_schema.get('emailsettings', [])
for col in ['completion_notify_enabled', 'completion_notify_email', 'completion_notify_task',
            'completion_notify_ticket', 'completion_email_subject', 'completion_email_body']:
    if col not in es_cols:
        issues.append(f"MISSING: emailsettings.{col}")

# --- task ---
task_cols = db_schema.get('task', [])
for col in ['customer_name', 'customer_surname', 'customer_email', 'customer_phone',
            'completion_notes',
            'billable_traveling', 'billable_labour_onsite', 'billable_remote_labour',
            'billable_equipment_used', 'non_billable_traveling', 'non_billable_labour_onsite',
            'non_billable_remote_labour', 'non_billable_equipment_used']:
    if col not in task_cols:
        issues.append(f"MISSING: task.{col}")

# --- ticket ---
ticket_cols = db_schema.get('ticket', [])
for col in ['closing_notes',
            'billable_traveling', 'billable_labour_onsite', 'billable_remote_labour',
            'billable_equipment_used', 'non_billable_traveling', 'non_billable_labour_onsite',
            'non_billable_remote_labour', 'non_billable_equipment_used']:
    if col not in ticket_cols:
        issues.append(f"MISSING: ticket.{col}")

# --- user ---
user_cols = db_schema.get('user', [])
for col in ['mute_ticket_notifications', 'show_bubbles_analytics', 'last_seen_at', 'away_summary_preference']:
    if col not in user_cols:
        issues.append(f"MISSING: user.{col}")

# --- processedmail ---
pm_cols = db_schema.get('processedmail', [])
for col in ['email_account']:
    if col not in pm_cols:
        issues.append(f"MISSING: processedmail.{col}")

# --- workspace ---
ws_cols = db_schema.get('workspace', [])
for col in ['business_hours_start', 'business_hours_end', 'business_hours_exclude_weekends']:
    if col not in ws_cols:
        issues.append(f"MISSING: workspace.{col}")

# --- Check for tables in models but not in DB ---
expected_tables = ['activity', 'activitylog', 'assignment', 'chat', 'chatmember', 'comment',
                   'comment_attachment', 'company', 'contact', 'customfield', 'customfieldvalue',
                   'deal', 'emailsettings', 'incoming_email_account', 'lead', 'meeting',
                   'meetingattendee', 'message', 'messageattachment', 'notification',
                   'processedmail', 'project', 'project_member', 'recurringtask',
                   'recurringtaskinstance', 'savedview', 'subtask', 'task', 'taskattachment',
                   'taskdependency', 'taskhistory', 'taskwatcher', 'ticket', 'ticketattachment',
                   'ticketcomment', 'ticketwatcher', 'timelog', 'user', 'workspace',
                   'focustask', 'goal', 'milestone', 'tasktemplate']

for t in expected_tables:
    if t not in db_schema:
        issues.append(f"MISSING TABLE: {t}")

# --- Check row counts for key tables ---
print("=== DATA ROW COUNTS ===")
key_tables = ['user', 'workspace', 'project', 'task', 'subtask', 'assignment', 'comment',
              'comment_attachment', 'ticket', 'ticketcomment', 'tickethistory', 'ticketattachment',
              'notification', 'processedmail', 'meeting', 'meetingattendee', 'chat', 'message',
              'project_member', 'taskhistory', 'emailsettings', 'incoming_email_account',
              'messageattachment', 'pending_email']
for t in key_tables:
    if t in db_schema:
        cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
        count = cursor.fetchone()[0]
        print(f"  {t}: {count} rows")

# --- Check for orphaned references ---
print("\n=== REFERENTIAL INTEGRITY CHECKS ===")

# Tasks referencing non-existent projects
cursor.execute("SELECT COUNT(*) FROM task WHERE project_id NOT IN (SELECT id FROM project)")
orphan_tasks = cursor.fetchone()[0]
print(f"  Tasks with invalid project_id: {orphan_tasks}")

# Assignments referencing non-existent tasks
cursor.execute("SELECT COUNT(*) FROM assignment WHERE task_id NOT IN (SELECT id FROM task)")
orphan_assign = cursor.fetchone()[0]
print(f"  Assignments with invalid task_id: {orphan_assign}")

# Assignments referencing non-existent users
cursor.execute("SELECT COUNT(*) FROM assignment WHERE assignee_id NOT IN (SELECT id FROM user)")
orphan_assign_user = cursor.fetchone()[0]
print(f"  Assignments with invalid assignee_id: {orphan_assign_user}")

# Comments referencing non-existent tasks
cursor.execute("SELECT COUNT(*) FROM comment WHERE task_id NOT IN (SELECT id FROM task)")
orphan_comments = cursor.fetchone()[0]
print(f"  Comments with invalid task_id: {orphan_comments}")

# Subtasks referencing non-existent tasks
cursor.execute("SELECT COUNT(*) FROM subtask WHERE task_id NOT IN (SELECT id FROM task)")
orphan_subtasks = cursor.fetchone()[0]
print(f"  Subtasks with invalid task_id: {orphan_subtasks}")

# Tickets referencing non-existent users
cursor.execute("SELECT COUNT(*) FROM ticket WHERE assigned_to_id IS NOT NULL AND assigned_to_id NOT IN (SELECT id FROM user)")
orphan_tickets = cursor.fetchone()[0]
print(f"  Tickets with invalid assigned_to_id: {orphan_tickets}")

# Ticket comments referencing non-existent tickets
cursor.execute("SELECT COUNT(*) FROM ticketcomment WHERE ticket_id NOT IN (SELECT id FROM ticket)")
orphan_tc = cursor.fetchone()[0]
print(f"  TicketComments with invalid ticket_id: {orphan_tc}")

# ProjectMembers referencing non-existent projects or users
cursor.execute("SELECT COUNT(*) FROM project_member WHERE project_id NOT IN (SELECT id FROM project)")
orphan_pm_p = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM project_member WHERE user_id NOT IN (SELECT id FROM user)")
orphan_pm_u = cursor.fetchone()[0]
print(f"  ProjectMembers with invalid project_id: {orphan_pm_p}")
print(f"  ProjectMembers with invalid user_id: {orphan_pm_u}")

# Notifications referencing non-existent users
cursor.execute("SELECT COUNT(*) FROM notification WHERE user_id NOT IN (SELECT id FROM user)")
orphan_notif = cursor.fetchone()[0]
print(f"  Notifications with invalid user_id: {orphan_notif}")

# ProcessedMail referencing non-existent tickets
cursor.execute("SELECT COUNT(*) FROM processedmail WHERE ticket_id IS NOT NULL AND ticket_id NOT IN (SELECT id FROM ticket)")
orphan_pm = cursor.fetchone()[0]
print(f"  ProcessedMail with invalid ticket_id: {orphan_pm}")

# Task history referencing non-existent tasks
cursor.execute("SELECT COUNT(*) FROM taskhistory WHERE task_id NOT IN (SELECT id FROM task)")
orphan_th = cursor.fetchone()[0]
print(f"  TaskHistory with invalid task_id: {orphan_th}")

# Ticket history referencing non-existent tickets
cursor.execute("SELECT COUNT(*) FROM tickethistory WHERE ticket_id NOT IN (SELECT id FROM ticket)")
orphan_tkh = cursor.fetchone()[0]
print(f"  TicketHistory with invalid ticket_id: {orphan_tkh}")

print("\n=== SCHEMA ISSUES (model vs DB) ===")
if issues:
    for i in issues:
        print(f"  {i}")
else:
    print("  No schema issues found!")

# --- Check for NULL in required fields ---
print("\n=== NULL CHECKS ON KEY FIELDS ===")
cursor.execute("SELECT COUNT(*) FROM user WHERE username IS NULL OR email IS NULL")
print(f"  Users with NULL username/email: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM task WHERE title IS NULL")
print(f"  Tasks with NULL title: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM ticket WHERE ticket_number IS NULL OR subject IS NULL")
print(f"  Tickets with NULL ticket_number/subject: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM project WHERE name IS NULL")
print(f"  Projects with NULL name: {cursor.fetchone()[0]}")

# Check SQLite integrity
print("\n=== SQLITE INTEGRITY CHECK ===")
cursor.execute("PRAGMA integrity_check")
result = cursor.fetchone()[0]
print(f"  Result: {result}")

conn.close()
