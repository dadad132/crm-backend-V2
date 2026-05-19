"""
Server startup script with automatic local IP detection.
This script detects the machine's local IP address and starts the server on that IP,
making it accessible from other machines on the same network or data center.
"""
import sys
import os
from pathlib import Path

# Force UTF-8 output to prevent emoji/unicode encoding errors on Windows consoles
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add the project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from app.core.network import get_local_ip, get_all_local_ips, get_public_ip
from app.core.backup import backup_manager


def start_server(host=None, port=8000, use_public_ip=True):
    """
    Start the uvicorn server with automatic IP detection and database backup.
    
    Args:
        host: IP address to bind to. If None, will auto-detect.
        port: Port to bind to. Default is 8000.
        use_public_ip: If True, detects and displays public IP. Server binds to 0.0.0.0 for public access.
    """
    import uvicorn
    import asyncio
    from app.core.database import init_models
    
    # Check if database exists, if not initialize it
    db_path = Path("data.db")
    if not db_path.exists():
        print("[*] Database not found - initializing new database...")
        try:
            asyncio.run(init_models())
            print("[+] Database initialized successfully")
        except Exception as e:
            print(f"[!] Failed to initialize database: {e}")
            return
    else:
        # Check database integrity and restore from backup if corrupted
        print("[*] Checking database integrity...")
        if backup_manager.check_and_restore_on_startup():
            print("[+] Database is ready")
            # Create an initial backup with attachments
            print("[*] Creating startup backup...")
            backup_manager.create_backup(include_attachments=True)
        else:
            print("[!] Failed to restore database. Server may not start properly.")
            return
    
    # Run attachment scanner to fix broken paths
    print("[*] Scanning for attachments...")
    try:
        from app.core.attachment_scanner import run_attachment_scan
        results = run_attachment_scan(db_path='data.db', fix_paths=True)
        if results['fixed'] > 0:
            print(f"[+] Fixed {results['fixed']} broken attachment paths")
        if results['missing'] > 0:
            print(f"[!] Warning: {results['missing']} attachments have missing files")
        print(f"[+] Attachment scan complete ({results['ok']} OK, {results['scanned']} total)")
    except Exception as e:
        print(f"[!] Attachment scan failed: {e}")
    
    # Detect IP if not provided
    if host is None:
        if use_public_ip:
            # For public access, we need to bind to 0.0.0.0 (all interfaces)
            # but display the public IP for access
            public_ip = get_public_ip()
            host = '0.0.0.0'  # Bind to all interfaces
            display_ip = public_ip
        else:
            # For local network only
            host = get_local_ip()
            display_ip = host
    else:
        display_ip = host
    
    print("=" * 60)
    print(">> Starting CRM Backend Server")
    print("=" * 60)
    print(f"Binding to: {host}")
    print(f"Port: {port}")
    
    if use_public_ip and host == '0.0.0.0':
        print(f"\n[PUBLIC ACCESS]")
        print(f"   http://{display_ip}:{port}")
        print(f"\n[LOCAL ACCESS]")
        local_ip = get_local_ip()
        print(f"   http://{local_ip}:{port}")
        print(f"   http://localhost:{port}")
    else:
        print(f"Access URL: http://{display_ip}:{port}")
    
    print("=" * 60)
    
    # Show all available IPs for reference
    all_ips = get_all_local_ips()
    if all_ips and len(all_ips) > 1:
        print("\n[ADDITIONAL LOCAL IPS]")
        for ip in all_ips:
            print(f"   - http://{ip}:{port}")
        print()
    
    print("\n[+] Server is running. Press CTRL+C to stop.\n")
    print("[!] Important: Ensure your firewall allows incoming connections on port", port)
    print()
    
    # Start uvicorn server with optimized settings
    # Note: reload=False on Windows to avoid multiprocessing issues
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,  # Disabled to prevent Windows multiprocessing errors
        log_level="warning",  # Reduce log noise for better performance
        access_log=False,  # Disable access log for faster responses
        workers=1,  # Single worker for SQLite (SQLite doesn't support concurrent writes)
        limit_concurrency=100,  # Limit concurrent connections
        timeout_keep_alive=30,  # Reduce keepalive timeout
    )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Start the CRM backend server with public IP detection')
    parser.add_argument(
        '--host',
        type=str,
        default=None,
        help='Host IP address (default: bind to 0.0.0.0 for public access)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Port number (default: 8000)'
    )
    parser.add_argument(
        '--local-only',
        action='store_true',
        help='Bind to local IP only (not publicly accessible)'
    )
    parser.add_argument(
        '--all-interfaces',
        action='store_true',
        help='Bind to all interfaces (0.0.0.0) - same as default for public access'
    )
    
    args = parser.parse_args()
    
    # Determine host and public IP mode
    if args.all_interfaces:
        host = '0.0.0.0'
        use_public_ip = True
    elif args.host:
        host = args.host
        use_public_ip = False
    else:
        # Default behavior: public access unless --local-only specified
        host = None
        use_public_ip = not args.local_only
    
    try:
        start_server(host=host, port=args.port, use_public_ip=use_public_ip)
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        sys.exit(1)
