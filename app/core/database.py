from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event

from .config import get_settings

_settings = get_settings()

_initialized: bool = False

# SQLite uses StaticPool by default with aiosqlite, so we don't set pool parameters
# For production with PostgreSQL, you would add: pool_size=10, max_overflow=20
engine: AsyncEngine = create_async_engine(
    _settings.database_url,
    echo=False,  # Disable SQL logging for performance
    future=True,
    pool_pre_ping=True,  # Check connections are alive
)

# Enable WAL mode and busy timeout for SQLite to allow concurrent reads/writes.
# Without WAL, every write acquires an exclusive lock blocking all other operations,
# which causes the email scheduler to timeout when the database is busy.
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")  # Wait up to 30s for locks
    cursor.execute("PRAGMA synchronous=NORMAL")  # Safe with WAL, better performance
    cursor.close()

async_session_factory = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def init_models() -> None:
    # Import models to register tables
    from app import models  # noqa: F401
    async with engine.begin() as conn:
        # Ensure WAL mode is active (belt-and-suspenders with the connect event listener)
        if engine.url.get_backend_name().startswith("sqlite"):
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            await conn.exec_driver_sql("PRAGMA busy_timeout=30000")
            await conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
        # For SQLite dev usage: if schema drift is detected (e.g., missing columns
        # after model changes), drop and recreate all tables to avoid runtime errors.
        try:
            if engine.url.get_backend_name().startswith("sqlite"):
                # Drift check for user table (workspace_id) and task table (new scheduling columns)
                res_user = await conn.exec_driver_sql('PRAGMA table_info("user")')
                user_cols = [row[1] for row in res_user.fetchall()]
                need_rebuild = False
                # Rebuild if critical columns are missing
                for col in ("workspace_id", "preferred_meeting_platform", "email_verified", "verification_code", "verification_expires_at"):
                    if user_cols and col not in user_cols:
                        need_rebuild = True

                res_task = await conn.exec_driver_sql('PRAGMA table_info("task")')
                task_cols = [row[1] for row in res_task.fetchall()]
                expected_task_cols = {"start_date", "start_time", "due_date", "due_time"}
                if task_cols and not expected_task_cols.issubset(set(task_cols)):
                    need_rebuild = True

                # Note: project_member table check removed - table should be added via manual migration
                # to avoid losing data. The table structure is created by SQLModel.metadata.create_all
                # if it doesn't exist, without dropping existing tables.

                if need_rebuild:
                    await conn.run_sync(SQLModel.metadata.drop_all)
        except Exception:
            # Best-effort; continue to create_all
            pass
        await conn.run_sync(SQLModel.metadata.create_all)


async def ensure_initialized() -> None:
    global _initialized
    if not _initialized:
        await init_models()
        _initialized = True


@asynccontextmanager
async def lifespan(app):  # FastAPI lifespan
    # Initialize database
    await init_models()
    
    # Setup graceful shutdown handlers
    from app.core.shutdown import shutdown_handler
    shutdown_handler.setup_handlers()
    
    import logging
    logger = logging.getLogger(__name__)
    
    # ─── Schema fixes ───────────────────────────────────────────────
    # These MUST run before any schedulers start, since the schedulers
    # read/write these tables. Direct sqlite3 connections use timeout
    # to avoid hanging if another process holds a lock.
    
    # Fix ticketattachment.uploaded_by_id NOT NULL constraint
    # The model says Optional[int] but the DB column may still have NOT NULL from original create
    # SQLite doesn't support ALTER COLUMN, so we recreate the table if needed
    try:
        import sqlite3
        from pathlib import Path
        
        db_path = Path("data.db")
        if db_path.exists():
            conn = sqlite3.connect(str(db_path), timeout=30)
            cursor = conn.cursor()
            
            # Check if uploaded_by_id is NOT NULL (notnull=1 in pragma)
            cursor.execute('PRAGMA table_info("ticketattachment")')
            cols = {row[1]: row for row in cursor.fetchall()}
            # PRAGMA table_info columns: cid, name, type, notnull, dflt_value, pk
            if "uploaded_by_id" in cols and cols["uploaded_by_id"][3] == 1:
                logger.info("🔧 Fixing ticketattachment.uploaded_by_id NOT NULL constraint...")
                cursor.execute("PRAGMA foreign_keys=OFF")
                cursor.execute("BEGIN TRANSACTION")
                try:
                    cursor.execute("""
                        CREATE TABLE ticketattachment_new (
                            id INTEGER PRIMARY KEY,
                            ticket_id INTEGER NOT NULL REFERENCES ticket(id),
                            comment_id INTEGER REFERENCES ticketcomment(id),
                            filename VARCHAR NOT NULL,
                            file_path VARCHAR NOT NULL,
                            file_size INTEGER NOT NULL,
                            mime_type VARCHAR,
                            uploaded_by_id INTEGER REFERENCES "user"(id),
                            uploaded_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP)
                        )
                    """)
                    cursor.execute("""
                        INSERT INTO ticketattachment_new
                            (id, ticket_id, comment_id, filename, file_path, file_size, mime_type, uploaded_by_id, uploaded_at)
                        SELECT id, ticket_id, comment_id, filename, file_path, file_size, mime_type, uploaded_by_id, uploaded_at
                        FROM ticketattachment
                    """)
                    cursor.execute("DROP TABLE ticketattachment")
                    cursor.execute("ALTER TABLE ticketattachment_new RENAME TO ticketattachment")
                    # Recreate indexes
                    cursor.execute("CREATE INDEX IF NOT EXISTS ix_ticketattachment_ticket_id ON ticketattachment(ticket_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS ix_ticketattachment_comment_id ON ticketattachment(comment_id)")
                    cursor.execute("COMMIT")
                    logger.info("✅ Fixed ticketattachment.uploaded_by_id - now allows NULL for email attachments")
                except Exception:
                    cursor.execute("ROLLBACK")
                    raise
                finally:
                    cursor.execute("PRAGMA foreign_keys=ON")
            
            conn.close()
    except Exception as e:
        logger.warning(f"⚠️  Could not fix ticketattachment schema: {e}")
    
    # Fix attachment paths from absolute to relative on startup
    try:
        import sqlite3
        from pathlib import Path
        
        db_path = Path("data.db")
        if db_path.exists():
            conn = sqlite3.connect(str(db_path), timeout=30)
            cursor = conn.cursor()
            
            # Quick fix for comment_attachment
            cursor.execute("SELECT id, file_path FROM comment_attachment WHERE file_path LIKE '/%' OR file_path LIKE '_:%'")
            rows = cursor.fetchall()
            if rows:
                logger.info(f"🔧 Fixing {len(rows)} comment attachment paths...")
                for att_id, file_path in rows:
                    uuid_filename = Path(file_path).name
                    new_path = f"app/uploads/comments/{uuid_filename}"
                    cursor.execute("UPDATE comment_attachment SET file_path = ? WHERE id = ?", (new_path, att_id))
                conn.commit()
                logger.info(f"✅ Fixed {len(rows)} comment attachment paths")
            
            conn.close()
    except Exception as e:
        logger.warning(f"⚠️  Could not fix attachment paths: {e}")
    
    # Add gui_theme column to workspace table (added for 5-theme system)
    try:
        import sqlite3
        from pathlib import Path
        db_path = Path("data.db")
        if db_path.exists():
            conn = sqlite3.connect(str(db_path), timeout=30)
            cursor = conn.cursor()
            cursor.execute('PRAGMA table_info("workspace")')
            ws_cols = {row[1] for row in cursor.fetchall()}
            if ws_cols and "gui_theme" not in ws_cols:
                logger.info("🔧 Adding gui_theme column to workspace...")
                cursor.execute("ALTER TABLE workspace ADD COLUMN gui_theme VARCHAR DEFAULT 'crimson'")
                conn.commit()
                logger.info("✅ Added workspace.gui_theme")
            if ws_cols and "anthropic_api_key" not in ws_cols:
                cursor.execute("ALTER TABLE workspace ADD COLUMN anthropic_api_key VARCHAR")
                conn.commit()
            if ws_cols and "bubbles_ai_provider" not in ws_cols:
                cursor.execute("ALTER TABLE workspace ADD COLUMN bubbles_ai_provider VARCHAR")
                conn.commit()
            conn.close()
    except Exception as e:
        logger.warning(f"⚠️  Could not migrate workspace schema: {e}")

    # Ensure support KB tables exist (added after initial deploy)
    # create_all handles this for new installs; belt-and-suspenders for upgrades
    try:
        import sqlite3
        from pathlib import Path
        db_path = Path("data.db")
        if db_path.exists():
            conn = sqlite3.connect(str(db_path), timeout=30)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='supportconversation'")
            if not cursor.fetchone():
                logger.info("🔧 Creating supportconversation / supportarticle / supportcategory tables...")
                # Let SQLModel create them via create_all (already called above)
                # but in case it missed them, do a targeted create_all with those models registered
                from app.models.support_kb import SupportArticle, SupportConversation, SupportCategory  # noqa
                conn.close()
                async with engine.begin() as conn2:
                    await conn2.run_sync(SQLModel.metadata.create_all)
                logger.info("✅ Support tables created")
            else:
                conn.close()
    except Exception as e:
        logger.warning(f"⚠️  Could not verify support tables: {e}")

    # Add email_account column to processedmail and change unique constraint
    # from global message_id to per-account (message_id + email_account)
    try:
        import sqlite3
        from pathlib import Path
        
        db_path = Path("data.db")
        if db_path.exists():
            conn = sqlite3.connect(str(db_path), timeout=30)
            cursor = conn.cursor()
            
            cursor.execute('PRAGMA table_info("processedmail")')
            pm_cols = {row[1] for row in cursor.fetchall()}
            
            if "email_account" not in pm_cols:
                logger.info("🔧 Adding email_account column to processedmail...")
                cursor.execute("PRAGMA foreign_keys=OFF")
                cursor.execute("BEGIN TRANSACTION")
                try:
                    cursor.execute("ALTER TABLE processedmail ADD COLUMN email_account VARCHAR NOT NULL DEFAULT ''")
                    # Drop old unique indexes on message_id alone (may have different names)
                    cursor.execute("DROP INDEX IF EXISTS ix_processedmail_message_id")
                    cursor.execute("DROP INDEX IF EXISTS ix_processedmail_message_id_unique")
                    # Create new composite unique index
                    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_processedmail_msg_account ON processedmail(message_id, email_account)")
                    # Re-create regular indexes
                    cursor.execute("CREATE INDEX IF NOT EXISTS ix_processedmail_message_id ON processedmail(message_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS ix_processedmail_email_account ON processedmail(email_account)")
                    cursor.execute("COMMIT")
                    logger.info("✅ Added email_account column - dedup is now per-account")
                except Exception:
                    cursor.execute("ROLLBACK")
                    raise
                finally:
                    cursor.execute("PRAGMA foreign_keys=ON")
            
            conn.close()
    except Exception as e:
        logger.warning(f"⚠️  Could not migrate processedmail schema: {e}")
    
    # ── Comprehensive task table column migration ──────────────────────
    # Covers all columns that may be absent on databases created before
    # the corresponding migration scripts were run manually.
    try:
        import sqlite3
        from pathlib import Path
        db_path = Path("data.db")
        if db_path.exists():
            conn = sqlite3.connect(str(db_path), timeout=30)
            cursor = conn.cursor()
            cursor.execute('PRAGMA table_info("task")')
            t_cols = {row[1] for row in cursor.fetchall()}
            task_ensure = {
                # customer info (added for job card / task-completion form)
                "customer_name":              "VARCHAR",
                "customer_surname":           "VARCHAR",
                "customer_email":             "VARCHAR",
                "customer_phone":             "VARCHAR",
                "customer_office_number":     "VARCHAR",
                # billable line items
                "billable_traveling":         "VARCHAR",
                "billable_labour_onsite":     "VARCHAR",
                "billable_remote_labour":     "VARCHAR",
                "billable_equipment_used":    "VARCHAR",
                # non-billable line items (kept for backwards compatibility)
                "non_billable_traveling":     "VARCHAR",
                "non_billable_labour_onsite": "VARCHAR",
                "non_billable_remote_labour": "VARCHAR",
                "non_billable_equipment_used":"VARCHAR",
                # completion notes
                "completion_notes":           "VARCHAR",
                # scheduling / display
                "tags":                       "VARCHAR",
                "working_days":               "VARCHAR DEFAULT '0,1,2,3,4'",
                "estimated_hours":            "FLOAT",
                "time_spent_hours":           "FLOAT",
                "is_archived":                "BOOLEAN NOT NULL DEFAULT 0",
                "archived_at":                "TIMESTAMP",
                "parent_task_id":             "INTEGER",
            }
            added = []
            for col, col_type in task_ensure.items():
                if t_cols and col not in t_cols:
                    cursor.execute(f"ALTER TABLE task ADD COLUMN {col} {col_type}")
                    added.append(col)
            if added:
                conn.commit()
                logger.info(f"✅ Added task columns: {', '.join(added)}")
            conn.close()
    except Exception as e:
        logger.warning(f"⚠️  Could not migrate task schema: {e}")

    # ── Comprehensive ticket table column migration ─────────────────────
    # Covers all columns that may be absent on older production databases.
    try:
        import sqlite3
        from pathlib import Path
        db_path = Path("data.db")
        if db_path.exists():
            conn = sqlite3.connect(str(db_path), timeout=30)
            cursor = conn.cursor()
            cursor.execute('PRAGMA table_info("ticket")')
            tkt_cols = {row[1] for row in cursor.fetchall()}
            ticket_ensure = {
                # job card client details (latest addition)
                "job_client_name":            "VARCHAR",
                "job_client_surname":         "VARCHAR",
                "job_client_phone":           "VARCHAR",
                "job_client_office_number":   "VARCHAR",
                # billable line items
                "billable_traveling":         "VARCHAR",
                "billable_labour_onsite":     "VARCHAR",
                "billable_remote_labour":     "VARCHAR",
                "billable_equipment_used":    "VARCHAR",
                # non-billable line items (kept for backwards compatibility)
                "non_billable_traveling":     "VARCHAR",
                "non_billable_labour_onsite": "VARCHAR",
                "non_billable_remote_labour": "VARCHAR",
                "non_billable_equipment_used":"VARCHAR",
                # closing details
                "closing_notes":              "VARCHAR",
                # guest fields
                "guest_office_number":        "VARCHAR",
                # scheduling / archive
                "working_days":               "VARCHAR DEFAULT '0,1,2,3,4'",
                "scheduled_date":             "TIMESTAMP",
                "is_archived":                "BOOLEAN NOT NULL DEFAULT 0",
                "archived_at":                "TIMESTAMP",
                "closed_by_id":               "INTEGER",
                "related_project_id":         "INTEGER",
                "related_task_id":            "INTEGER",
            }
            added = []
            for col, col_type in ticket_ensure.items():
                if tkt_cols and col not in tkt_cols:
                    cursor.execute(f"ALTER TABLE ticket ADD COLUMN {col} {col_type}")
                    added.append(col)
            if added:
                conn.commit()
                logger.info(f"✅ Added ticket columns: {', '.join(added)}")
            conn.close()
    except Exception as e:
        logger.warning(f"⚠️  Could not migrate ticket schema: {e}")

    # ─── Background schedulers ──────────────────────────────────────
    # Start these AFTER all schema fixes are done, so they don't read
    # tables that are being modified.
    
    # Start automatic backup system
    from app.core.backup import backup_manager
    
    try:
        await backup_manager.start_auto_backup()
        logger.info("✅ Automatic backup system started")
    except Exception as e:
        logger.error(f"⚠️  Failed to start backup system: {e}")
    
    # Start email-to-ticket scheduler (V2 - uses database settings)
    try:
        from app.core.email_scheduler_v2 import start_email_scheduler
        await start_email_scheduler()
        logger.info("✅ Email-to-Ticket scheduler started (V2 - database config)")
    except Exception as e:
        logger.warning(f"⚠️  Email-to-Ticket scheduler not started: {e}")
    
    # Start system log cleanup scheduler (deletes logs older than 7 days)
    try:
        from app.core.system_logger import start_log_cleanup_scheduler, cleanup_old_logs
        await cleanup_old_logs()  # Run once on startup
        asyncio.create_task(start_log_cleanup_scheduler())
        logger.info("✅ System log cleanup scheduler started")
    except Exception as e:
        logger.warning(f"⚠️  System log cleanup scheduler not started: {e}")
    
    # Start data retention scheduler (cleans notifications, bot conversations, behavior tracking)
    try:
        from app.core.data_retention import start_data_retention_scheduler, cleanup_old_data
        await cleanup_old_data()  # Run once on startup
        asyncio.create_task(start_data_retention_scheduler())
        logger.info("✅ Data retention scheduler started")
    except Exception as e:
        logger.warning(f"⚠️  Data retention scheduler not started: {e}")
    
    yield
    
    # Cleanup on shutdown - execute graceful shutdown sequence
    try:
        logger.info("🛑 Application shutdown requested...")
        await shutdown_handler.shutdown_sequence()
        
        # Stop email scheduler
        from app.core.email_scheduler_v2 import stop_email_scheduler
        await stop_email_scheduler()
        logger.info("✅ Email-to-Ticket scheduler stopped")
    except Exception as e:
        logger.error(f"⚠️  Error during graceful shutdown: {e}")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession.

    Note: do NOT wrap this with @asynccontextmanager — FastAPI expects an async
    generator (uses `yield`) and will manage the context for the dependency.
    Returning the context manager object causes the dependency to be the
    context manager itself, which doesn't have DB methods like `execute`.
    """
    await ensure_initialized()
    async with async_session_factory() as session:
        yield session
