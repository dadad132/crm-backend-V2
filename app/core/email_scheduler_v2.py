"""
Email-to-Ticket Scheduler V2
Uses database settings for each workspace - supports multiple email accounts
"""

import asyncio
import traceback
from datetime import datetime
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.core.database import engine
from app.core.email_to_ticket_v2 import process_workspace_emails, process_email_account
from app.core.system_logger import log_fire_and_forget
from app.models.workspace import Workspace
from app.models.email_settings import EmailSettings
from app.models.incoming_email_account import IncomingEmailAccount


# Maximum time (seconds) to wait for a single email account to finish processing
ACCOUNT_PROCESS_TIMEOUT = 120  # 2 minutes per account


class EmailScheduler:
    """Background scheduler for email-to-ticket processing"""
    
    def __init__(self, check_interval: int = 120):
        """
        Initialize scheduler
        
        Args:
            check_interval: Seconds between checks (default: 2 minutes)
        """
        self.check_interval = check_interval
        self.running = False
        self.task = None
        self._wake_event = asyncio.Event()
        self._lock = asyncio.Lock()
        # Track check status for UI polling
        self._last_check_completed_at: datetime | None = None
        self._checking = False
    
    async def check_now(self):
        """Wake the scheduler to run an immediate email check.
        Returns immediately after triggering — does not wait for completion."""
        if not self.running:
            return
        self._wake_event.set()
    
    async def check_emails_task(self):
        """Background task to check emails periodically"""
        
        print(f"[Email-to-Ticket] ✅ Scheduler started (checking every {self.check_interval}s)")
        log_fire_and_forget('INFO', 'Scheduler', 'Scheduler', f'Scheduler started (interval={self.check_interval}s)')
        check_count = 0
        
        while self.running:
            check_count += 1
            try:
                # Clear the wake event at the START of each cycle so that
                # check_now() calls during processing are NOT lost
                self._wake_event.clear()
                self._checking = True
                
                async with self._lock:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print(f"[{timestamp}] [Email-to-Ticket] 📧 Check #{check_count} starting...")
                    log_fire_and_forget('INFO', 'Scheduler', 'Scheduler', f'Email check #{check_count} starting')
                    
                    total_tickets_created = 0
                    
                    # Process legacy workspace email settings (single account)
                    workspace_ids = []
                    
                    try:
                        async with AsyncSession(engine) as db:
                            # Get all workspaces with legacy email settings
                            result = await db.execute(
                                select(EmailSettings.workspace_id).where(EmailSettings.incoming_mail_host.isnot(None))
                            )
                            workspace_ids = [row[0] for row in result.all()]
                        
                        print(f"[Email-to-Ticket] Found {len(workspace_ids)} workspaces with legacy email settings")
                        
                        # Process legacy workspaces sequentially
                        for ws_id in workspace_ids:
                            await self._process_workspace(ws_id)
                    except Exception as e:
                        if "no such table" in str(e).lower():
                            print(f"[Email-to-Ticket] EmailSettings table not found - skipping legacy email check")
                            log_fire_and_forget('WARNING', 'Scheduler', 'Scheduler', 'EmailSettings table not found - skipping legacy check')
                        else:
                            print(f"[Email-to-Ticket] Error checking legacy email settings: {e}")
                            log_fire_and_forget('ERROR', 'Scheduler', 'Scheduler', f'Error checking legacy email settings: {str(e)[:200]}')
                    
                    # Process new multi-account email settings
                    await self._process_email_accounts()
                    
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print(f"[{timestamp}] [Email-to-Ticket] ✅ Check #{check_count} complete. Next check in {self.check_interval}s")
                    log_fire_and_forget('INFO', 'Scheduler', 'Scheduler', f'Email check #{check_count} complete')
                
                # Mark done BEFORE the wait so the polling UI sees it immediately
                self._checking = False
                self._last_check_completed_at = datetime.now()
                
                # Wait for next check OR be woken up by check_now()
                # If check_now() was called during processing, the event is already set
                # and this will return immediately — no trigger lost
                if not self._wake_event.is_set():
                    try:
                        await asyncio.wait_for(self._wake_event.wait(), timeout=self.check_interval)
                        print("[Email-to-Ticket] 🔔 Manual check requested - running immediately")
                    except asyncio.TimeoutError:
                        pass  # Normal timeout, proceed with next scheduled check
                else:
                    print("[Email-to-Ticket] 🔔 Manual check was requested during processing - running again immediately")
                
            except asyncio.CancelledError:
                print("[Email-to-Ticket] Task cancelled")
                raise
            except Exception as e:
                self._checking = False
                self._last_check_completed_at = datetime.now()
                print(f"[Email-to-Ticket] Error in background task: {e}")
                print(f"[Email-to-Ticket] Traceback: {traceback.format_exc()}")
                log_fire_and_forget('ERROR', 'Scheduler', 'Scheduler', f'Background task error: {str(e)[:200]}')
                # Wait before retrying (single sleep, not double)
                await asyncio.sleep(self.check_interval)
    
    async def _process_workspace(self, workspace_id: int):
        """Process emails for a single workspace with its own session (legacy single-account)"""
        try:
            async with AsyncSession(engine) as db:
                tickets = await process_workspace_emails(db, workspace_id)
                
                if tickets:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print(f"[{timestamp}] Workspace {workspace_id}: Created {len(tickets)} ticket(s) from emails")
                    log_fire_and_forget('INFO', 'Scheduler', 'Scheduler', f'Workspace {workspace_id}: Created {len(tickets)} ticket(s)')
        
        except Exception as e:
            print(f"[Email-to-Ticket] Error processing workspace {workspace_id}: {e}")
            log_fire_and_forget('ERROR', 'Scheduler', 'Scheduler', f'Error processing workspace {workspace_id}: {str(e)[:200]}')
    
    async def _process_email_accounts(self):
        """Process emails for all active incoming email accounts (new multi-account)"""
        try:
            # Load accounts in one session, then close it
            # This avoids expire_on_commit issues when processing multiple accounts
            async with AsyncSession(engine) as db:
                result = await db.execute(
                    select(IncomingEmailAccount).where(
                        IncomingEmailAccount.is_active == True
                    )
                )
                accounts = result.scalars().all()
            
            if not accounts:
                return
            
            print(f"[Email-to-Ticket] Found {len(accounts)} active incoming email account(s)")
            
            # Process each account with its own fresh session
            # Previously, all accounts shared one session and db.commit() after the
            # first account expired all remaining account objects (expire_on_commit=True),
            # causing MissingGreenlet errors on subsequent accounts
            for account in accounts:
                account_name = account.name
                try:
                    async with AsyncSession(engine) as account_db:
                        # Timeout prevents a hanging IMAP connection from blocking the scheduler forever
                        tickets = await asyncio.wait_for(
                            process_email_account(account_db, account),
                            timeout=ACCOUNT_PROCESS_TIMEOUT
                        )
                        if tickets:
                            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            print(f"[{timestamp}] Email '{account_name}': Created {len(tickets)} ticket(s) from emails")
                        
                        # Update last_checked_at
                        account.last_checked_at = datetime.utcnow()
                        account_db.add(account)
                        await account_db.commit()
                except asyncio.TimeoutError:
                    print(f"[Email-to-Ticket] ⚠️ TIMEOUT: Account '{account_name}' exceeded {ACCOUNT_PROCESS_TIMEOUT}s - skipping")
                    log_fire_and_forget('ERROR', 'Scheduler', f'Timeout processing account: {account_name}', f'Exceeded {ACCOUNT_PROCESS_TIMEOUT}s')
                except Exception as e:
                    err_str = str(e).lower()
                    if 'database is locked' in err_str or 'locked' in err_str:
                        print(f"[Email-to-Ticket] ⚠️ DATABASE LOCKED for account '{account_name}' - will retry next cycle")
                        log_fire_and_forget('WARNING', 'Scheduler', f'Database locked for account: {account_name}', 'Will retry next cycle')
                    else:
                        print(f"[Email-to-Ticket] Error processing email account '{account_name}': {e}")
                        print(f"[Email-to-Ticket] Traceback: {traceback.format_exc()}")
                        log_fire_and_forget('ERROR', 'Scheduler', f'Error processing account: {account_name}', str(e)[:200])
        
        except Exception as e:
            if "no such table" in str(e).lower():
                print(f"[Email-to-Ticket] IncomingEmailAccount table not found - skipping multi-account check")
                log_fire_and_forget('WARNING', 'Scheduler', 'Scheduler', 'IncomingEmailAccount table not found - skipping')
            else:
                print(f"[Email-to-Ticket] Error processing email accounts: {e}")
                print(f"[Email-to-Ticket] Traceback: {traceback.format_exc()}")
                log_fire_and_forget('ERROR', 'Scheduler', 'Scheduler', f'Error processing email accounts: {str(e)[:200]}')
    
    async def start(self):
        """Start the scheduler"""
        if self.running:
            print("[Email-to-Ticket] Scheduler already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self.check_emails_task())
        # Add exception handler to log if task crashes
        self.task.add_done_callback(self._task_done_callback)
        print("[Email-to-Ticket] Scheduler started successfully")
    
    def _task_done_callback(self, task):
        """Handle task completion/failure — auto-restart if crashed"""
        try:
            exception = task.exception()
            if exception:
                print(f"[Email-to-Ticket] ❌ Background task crashed: {exception}")
                print(f"[Email-to-Ticket] Traceback: {traceback.format_exception(type(exception), exception, exception.__traceback__)}")
                log_fire_and_forget('ERROR', 'Scheduler', 'Scheduler', f'Background task crashed: {str(exception)[:200]}')
                # Auto-restart the scheduler after a crash
                if self.running:
                    print("[Email-to-Ticket] 🔄 Auto-restarting scheduler after crash...")
                    loop = asyncio.get_event_loop()
                    loop.call_soon(lambda: asyncio.ensure_future(self._restart()))
        except asyncio.CancelledError:
            print("[Email-to-Ticket] Task was cancelled")
        except asyncio.InvalidStateError:
            pass  # Task not done yet
    
    async def _restart(self):
        """Restart the scheduler task after a crash"""
        try:
            await asyncio.sleep(10)  # Brief delay before restart
            self.task = asyncio.create_task(self.check_emails_task())
            self.task.add_done_callback(self._task_done_callback)
            print("[Email-to-Ticket] ✅ Scheduler restarted successfully")
            log_fire_and_forget('INFO', 'Scheduler', 'Scheduler', 'Scheduler restarted after crash')
        except Exception as e:
            print(f"[Email-to-Ticket] ❌ Failed to restart scheduler: {e}")
            log_fire_and_forget('ERROR', 'Scheduler', 'Scheduler', f'Failed to restart scheduler: {str(e)[:200]}')
    
    async def stop(self):
        """Stop the scheduler"""
        if not self.running:
            return
        
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        print("[Email-to-Ticket] Scheduler stopped")


# Global scheduler instance
from app.core.config import get_settings
settings = get_settings()
email_scheduler = EmailScheduler(check_interval=settings.email_check_interval)


async def start_email_scheduler():
    """Start the email-to-ticket scheduler"""
    try:
        await email_scheduler.start()
    except Exception as e:
        print(f"[Email-to-Ticket] Failed to start scheduler: {e}")


async def stop_email_scheduler():
    """Stop the email-to-ticket scheduler"""
    await email_scheduler.stop()


async def check_emails_now():
    """Trigger an immediate email check (wakes the scheduler)"""
    await email_scheduler.check_now()


async def run_email_check_direct() -> dict:
    """
    Run an immediate email check across all configured accounts and return results.

    Used by the manual 'Check Emails Now' button so it can report real results
    without the race condition of polling the background scheduler's state.

    Can run concurrently with the scheduler — ProcessedMail dedup prevents duplicates.

    Returns:
        dict with 'tickets_created' (int), 'accounts_checked' (int), 'errors' (list[str])
    """
    total_tickets = 0
    errors = []
    accounts_checked = 0

    # --- Legacy single-account per workspace ---
    try:
        async with AsyncSession(engine) as db:
            result = await db.execute(
                select(EmailSettings.workspace_id).where(EmailSettings.incoming_mail_host.isnot(None))
            )
            workspace_ids = [row[0] for row in result.all()]

        print(f"[Email Direct Check] Processing {len(workspace_ids)} legacy workspace(s)")

        for ws_id in workspace_ids:
            try:
                async with AsyncSession(engine) as db:
                    tickets = await process_workspace_emails(db, ws_id)
                    total_tickets += len(tickets)
                    accounts_checked += 1
            except Exception as e:
                errors.append(f"Workspace {ws_id}: {str(e)[:120]}")
                print(f"[Email Direct Check] Error in workspace {ws_id}: {e}")
    except Exception as e:
        if "no such table" not in str(e).lower():
            errors.append(f"Legacy check error: {str(e)[:120]}")

    # --- New multi-account email settings ---
    try:
        async with AsyncSession(engine) as db:
            result = await db.execute(
                select(IncomingEmailAccount).where(IncomingEmailAccount.is_active == True)
            )
            accounts = result.scalars().all()

        print(f"[Email Direct Check] Processing {len(accounts)} active account(s)")

        for account in accounts:
            account_name = account.name
            try:
                async with AsyncSession(engine) as account_db:
                    tickets = await asyncio.wait_for(
                        process_email_account(account_db, account),
                        timeout=ACCOUNT_PROCESS_TIMEOUT
                    )
                    total_tickets += len(tickets)
                    accounts_checked += 1

                    account.last_checked_at = datetime.utcnow()
                    account_db.add(account)
                    await account_db.commit()
            except asyncio.TimeoutError:
                errors.append(f"'{account_name}' timed out after {ACCOUNT_PROCESS_TIMEOUT}s")
                print(f"[Email Direct Check] Timeout for account '{account_name}'")
            except Exception as e:
                errors.append(f"'{account_name}': {str(e)[:120]}")
                print(f"[Email Direct Check] Error for account '{account_name}': {e}")
    except Exception as e:
        if "no such table" not in str(e).lower():
            errors.append(f"Multi-account check error: {str(e)[:120]}")

    return {
        'tickets_created': total_tickets,
        'accounts_checked': accounts_checked,
        'errors': errors,
    }
