"""
Seed default IT Solutions (categories + articles) for all workspaces.
Safe to re-run — skips workspaces that already have articles.
"""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CATEGORIES = [
    ("Network & Connectivity", "fas fa-wifi",        "Issues with internet, VPN, Wi-Fi and network access"),
    ("Printer & Scanning",     "fas fa-print",        "Problems with printing, scanning and shared printers"),
    ("Software & Applications","fas fa-laptop-code",  "Software crashes, installation errors and app issues"),
    ("Hardware & Devices",     "fas fa-desktop",      "Computer, monitor, keyboard and peripheral problems"),
    ("Email & Communication",  "fas fa-envelope",     "Email setup, sending/receiving issues and calendar sync"),
]

ARTICLES = [
    # Network
    ("network", "Cannot Connect to Internet",
     "No internet access, browser shows 'no connection'",
     "internet,no connection,offline,network,wifi,ethernet",
     "1. Check that the network cable is plugged in (or Wi-Fi is on)\n2. Restart your router/modem (unplug for 30 seconds)\n3. Restart your computer\n4. Run Windows Network Diagnostics: Settings → System → Troubleshoot → Other Troubleshooters → Internet Connections\n5. Try forgetting and reconnecting to Wi-Fi\n6. If still no internet, contact your ISP or create a support ticket"),
    ("network", "VPN Not Connecting",
     "VPN client fails to connect or disconnects frequently",
     "vpn,remote access,cisco,openconnect,tunnel,disconnect",
     "1. Check your internet connection is working first\n2. Verify VPN credentials (username/password)\n3. Disconnect and reconnect to VPN\n4. Restart the VPN client application\n5. Check if your password has expired — reset it via the company portal\n6. Try a different VPN server/region if available\n7. Temporarily disable firewall/antivirus to test\n8. Contact IT if the issue persists"),
    ("network", "Wi-Fi Connection Drops Frequently",
     "Wireless connection keeps disconnecting",
     "wifi,wireless,drops,disconnects,slow,unstable",
     "1. Move closer to the router\n2. Forget the Wi-Fi network and reconnect\n3. Update your network adapter drivers: Device Manager → Network Adapters → right-click → Update driver\n4. Disable Wi-Fi power-saving: Device Manager → Network Adapters → right-click → Properties → Power Management → uncheck 'Allow the computer to turn off this device'\n5. Change Wi-Fi channel in router settings (2.4GHz or 5GHz)\n6. Restart the router"),
    # Printer
    ("printer", "Printer Not Printing",
     "Print jobs are sent but nothing prints",
     "printer,not printing,print queue,stuck,offline",
     "1. Check the printer is on and has paper/ink\n2. Check the printer shows as 'Online' in Windows: Settings → Bluetooth & Devices → Printers\n3. Clear the print queue: open the printer → click 'Open queue' → cancel all jobs\n4. Restart the print spooler: Win+R → services.msc → Print Spooler → Restart\n5. Reconnect the USB cable or reconnect to the network printer\n6. Reinstall the printer driver if needed"),
    ("printer", "Printer Shows Offline",
     "Printer appears as 'Offline' in Windows",
     "printer,offline,status,network printer,shared",
     "1. Make sure the printer is powered on\n2. Right-click the printer → 'See what's printing' → Printer menu → uncheck 'Use Printer Offline'\n3. Restart both the printer and your computer\n4. For network printers: check the printer's IP address matches what Windows has configured\n5. Remove and re-add the printer: Settings → Bluetooth & Devices → Printers → Remove → Add device"),
    # Software
    ("software", "Application Crashes on Startup",
     "Program closes immediately when opened or freezes",
     "crash,application,error,not responding,freeze,closes",
     "1. Restart your computer first\n2. Run the application as Administrator: right-click → 'Run as administrator'\n3. Check for updates: open the app → Help → Check for Updates\n4. Clear the application cache (location varies — check the app documentation)\n5. Uninstall and reinstall the application\n6. Check Windows Event Viewer for error details: Win+R → eventvwr.msc → Windows Logs → Application"),
    ("software", "Windows Update Stuck or Failing",
     "Windows Update gets stuck or shows errors",
     "windows update,stuck,error,0x800,update failed,downloading",
     "1. Wait at least 2 hours — some updates are very slow\n2. Restart your PC and try again\n3. Run the Windows Update Troubleshooter: Settings → System → Troubleshoot → Other Troubleshooters → Windows Update\n4. Clear update cache: open Command Prompt as Admin → net stop wuauserv → del /f /s /q C:\\Windows\\SoftwareDistribution\\* → net start wuauserv\n5. Try updating again\n6. Contact IT if error codes persist"),
    # Hardware
    ("hardware", "Computer Running Very Slowly",
     "PC is sluggish, slow to open programs or respond",
     "slow,performance,sluggish,lag,freezing,cpu,ram,disk",
     "1. Restart your computer (don't just sleep/wake)\n2. Check for background processes: Ctrl+Shift+Esc → Task Manager → check CPU/RAM/Disk usage\n3. Disable startup programs: Task Manager → Startup → disable unnecessary apps\n4. Run Disk Cleanup: search 'Disk Cleanup' → select C: drive\n5. Check for malware: Windows Security → Quick Scan\n6. Make sure Windows and drivers are up to date\n7. If SSD/HDD is over 85% full, free up space"),
    ("hardware", "Monitor Has No Display / Black Screen",
     "Monitor is blank or shows no signal",
     "monitor,black screen,no display,no signal,blank",
     "1. Check the monitor power cable and power button\n2. Check the video cable (HDMI/DisplayPort/VGA) on both ends\n3. Try a different cable or port\n4. Restart the computer\n5. For laptops: press Win+P to switch display mode\n6. Test with a different monitor if available\n7. If the PC has integrated graphics, try that port instead of the graphics card"),
    # Email
    ("email", "Cannot Send or Receive Emails",
     "Outlook or email client fails to send or receive",
     "email,outlook,send,receive,not syncing,smtp,imap,error",
     "1. Check your internet connection\n2. Restart Outlook / your email client\n3. Check if the email server is down (ask colleagues if they have the same issue)\n4. Repair your Outlook profile: File → Account Settings → Account Settings → select account → Repair\n5. Check your mailbox size — if it is full, delete old emails or empty Deleted Items\n6. Re-enter your email password if prompted\n7. Contact IT for server settings or account reset"),
    ("email", "Outlook Password Keeps Asking",
     "Outlook repeatedly prompts for password after entering it",
     "outlook,password,prompt,keeps asking,credentials,login",
     "1. Enter your current password and tick 'Remember password'\n2. Open Credential Manager: Control Panel → User Accounts → Credential Manager → Windows Credentials → remove any Outlook/Office entries\n3. Sign out of Office: File → Office Account → Sign Out, then sign back in\n4. Check if your company password has expired — reset via company portal\n5. Disable 'Always prompt for credentials': File → Account Settings → Change → More Settings → Security → uncheck the option"),
]

def migrate():
    db_path = 'data.db'
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}"); return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        # Get all workspace IDs
        cursor.execute("SELECT id FROM workspace")
        workspace_ids = [row[0] for row in cursor.fetchall()]
        if not workspace_ids:
            print("No workspaces found — nothing to seed"); return

        for ws_id in workspace_ids:
            # Skip if already has articles
            cursor.execute("SELECT COUNT(*) FROM supportarticle WHERE workspace_id = ?", (ws_id,))
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"[SKIP] Workspace {ws_id} already has {count} articles")
                continue

            # Add categories
            cat_ids = {}
            for name, icon, desc in CATEGORIES:
                cursor.execute("""
                    INSERT INTO supportcategory (workspace_id, name, icon, description, article_count, is_active, created_at)
                    VALUES (?, ?, ?, ?, 0, 1, datetime('now'))
                """, (ws_id, name, icon, desc))
                cat_ids[name] = cursor.lastrowid

            # Add articles
            for cat_key, title, desc, keywords, steps in ARTICLES:
                # Map category key to category id
                cat_name_map = {
                    "network":  "Network & Connectivity",
                    "printer":  "Printer & Scanning",
                    "software": "Software & Applications",
                    "hardware": "Hardware & Devices",
                    "email":    "Email & Communication",
                }
                full_cat = cat_name_map[cat_key]
                cursor.execute("""
                    INSERT INTO supportarticle
                    (workspace_id, problem_keywords, problem_title, problem_description,
                     category, solution_steps, solution_source, times_shown, times_helpful,
                     times_not_helpful, success_rate, is_verified, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'manual', 0, 0, 0, 0.0, 1, 1, datetime('now'), datetime('now'))
                """, (ws_id, keywords, title, desc, full_cat, steps))

            # Update article counts on categories
            for cat_name, cat_id in cat_ids.items():
                cursor.execute("""
                    UPDATE supportcategory SET article_count = (
                        SELECT COUNT(*) FROM supportarticle
                        WHERE workspace_id = ? AND category = ?
                    ) WHERE id = ?
                """, (ws_id, cat_name, cat_id))

            print(f"[OK] Workspace {ws_id}: added {len(CATEGORIES)} categories + {len(ARTICLES)} articles")

        conn.commit()
        print("\n[DONE] IT Solutions seed completed!")
    except Exception as e:
        print(f"[ERROR] {e}"); conn.rollback(); raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
