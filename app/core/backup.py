"""
Database backup and restore functionality with automatic crash recovery
Includes database + attachments (comments and chat messages)
"""
import os
import shutil
import asyncio
import zipfile
import lzma
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class DatabaseBackup:
    """Handles automatic database backup and restore operations with attachments"""
    
    def __init__(self, db_path: str = "data.db", backup_dir: str = "backups"):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.uploads_dir = Path("app/uploads")  # Attachments directory
        self.max_backups = 10  # Keep last 10 automatic backups
        self.max_manual_backups = 15  # Keep last 15 manual backups
        self.max_uploaded_backups = 5  # Keep last 5 uploaded backups
        self.backup_interval = 43200  # Backup every 12 hours (43200 seconds)
        self._backup_task: Optional[asyncio.Task] = None
        # Status tracking for async backup operations
        self.backup_status: str = 'idle'  # idle | running | done | error
        self.backup_progress: str = ''
        self.backup_result_file: Optional[str] = None
        
    def get_backup_filename(self, is_manual: bool = False, include_attachments: bool = True) -> str:
        """Generate timestamped backup filename"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_type = "MANUAL" if is_manual else "AUTO"
        extension = ".zip" if include_attachments else ".db"
        return f"backup_{backup_type}_{timestamp}{extension}"
    
    def create_backup(self, is_manual: bool = False, include_attachments: bool = True) -> Optional[Path]:
        """Create a backup of the database and optionally attachments
        
        Args:
            is_manual: If True, marks as manual backup (won't be auto-deleted)
            include_attachments: If True, includes uploads folder in a zip archive
        """
        if not self.db_path.exists():
            logger.warning(f"Database {self.db_path} does not exist, skipping backup")
            return None
        
        try:
            backup_file = self.backup_dir / self.get_backup_filename(is_manual=is_manual, include_attachments=include_attachments)
            backup_type = "MANUAL" if is_manual else "AUTO"
            
            if include_attachments:
                # Collect files first so we can track progress
                files_to_add = []
                if self.uploads_dir.exists():
                    files_to_add = [f for f in self.uploads_dir.rglob('*') if f.is_file()]
                total_files = len(files_to_add) + 1  # +1 for database
                
                # Create ZIP archive with database + attachments using LZMA compression
                # LZMA gives significantly smaller files than DEFLATE (~30-50% smaller)
                with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_LZMA) as zipf:
                    # Add database
                    self.backup_progress = f'Compressing database (1/{total_files})'
                    zipf.write(self.db_path, arcname='data.db')
                    
                    # Add all attachments
                    for i, file_path in enumerate(files_to_add, start=2):
                        self.backup_progress = f'Compressing file {i}/{total_files}'
                        arcname = str(file_path.relative_to(self.uploads_dir.parent))
                        zipf.write(file_path, arcname=arcname)
                
                # Log backup size
                backup_size_mb = backup_file.stat().st_size / (1024 * 1024)
                logger.info(f"Full backup (DB + attachments) created: {backup_file} ({backup_type}) - {backup_size_mb:.2f} MB")
            else:
                # Simple database-only backup
                shutil.copy2(self.db_path, backup_file)
                logger.info(f"✅ Database backup created: {backup_file} ({backup_type})")
            
            # Create a "latest" backup link for easy restore
            latest_backup = self.backup_dir / ("backup_latest.zip" if include_attachments else "data_latest.db")
            if latest_backup.exists():
                latest_backup.unlink()
            shutil.copy2(backup_file, latest_backup)
            
            # Cleanup old automatic backups
            if not is_manual:
                self._cleanup_old_backups()
            else:
                # Also cleanup old manual backups (keep last 20)
                self._cleanup_old_manual_backups()
            
            return backup_file
        except Exception as e:
            logger.error(f"❌ Failed to create backup: {e}")
            return None
    
    def _cleanup_old_backups(self):
        """Remove old AUTOMATIC backup files only, keeping manual backups forever"""
        try:
            # Only get automatic backups (both .db and .zip)
            auto_backups = sorted(
                [f for f in self.backup_dir.glob("backup_AUTO_*.*") if f.suffix in ['.db', '.zip']],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            # Remove automatic backups beyond max_backups
            for old_backup in auto_backups[self.max_backups:]:
                old_backup.unlink()
                logger.info(f"🗑️  Removed old automatic backup: {old_backup.name}")
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
    
    def _cleanup_old_manual_backups(self):
        """Remove old MANUAL backup files beyond max_manual_backups (default 15)"""
        try:
            # Only get manual backups (both .db and .zip)
            manual_backups = sorted(
                [f for f in self.backup_dir.glob("backup_MANUAL_*.*") if f.suffix in ['.db', '.zip']],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            # Remove manual backups beyond max_manual_backups
            for old_backup in manual_backups[self.max_manual_backups:]:
                old_backup.unlink()
                logger.info(f"🗑️  Removed old manual backup: {old_backup.name}")
        except Exception as e:
            logger.error(f"Error cleaning up old manual backups: {e}")
    
    def _cleanup_old_uploaded_backups(self):
        """Remove old UPLOADED backup files beyond max_uploaded_backups (default 5)"""
        try:
            # Only get uploaded backups (both .db and .zip)
            uploaded_backups = sorted(
                [f for f in self.backup_dir.glob("backup_UPLOADED_*.*") if f.suffix in ['.db', '.zip']],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            # Remove uploaded backups beyond max_uploaded_backups
            for old_backup in uploaded_backups[self.max_uploaded_backups:]:
                old_backup.unlink()
                logger.info(f"🗑️  Removed old uploaded backup: {old_backup.name}")
        except Exception as e:
            logger.error(f"Error cleaning up old uploaded backups: {e}")
    
    def _cleanup_corrupted_uploads(self):
        """Remove old corrupted_uploads directories, keeping only the most recent one"""
        try:
            corrupted_dirs = sorted(
                [d for d in self.backup_dir.iterdir() if d.is_dir() and d.name.startswith('corrupted_uploads_')],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            # Keep only the most recent corrupted uploads dir
            for old_dir in corrupted_dirs[1:]:
                shutil.rmtree(old_dir)
                logger.info(f"🗑️  Removed old corrupted uploads: {old_dir.name}")
        except Exception as e:
            logger.error(f"Error cleaning up corrupted uploads: {e}")

    def _cleanup_orphan_backups(self):
        """Remove backup files with non-standard prefixes that escape normal retention cleanup"""
        try:
            known_prefixes = ('backup_AUTO_', 'backup_MANUAL_', 'backup_UPLOADED_', 'backup_latest', 'data_latest', 'corrupted_')
            orphans = [
                f for f in self.backup_dir.iterdir()
                if f.is_file() and not any(f.name.startswith(p) for p in known_prefixes)
            ]
            for orphan in orphans:
                orphan.unlink()
                logger.info(f"🗑️  Removed orphan backup: {orphan.name}")
        except Exception as e:
            logger.error(f"Error cleaning up orphan backups: {e}")

    def cleanup_all_old_backups(self):
        """Run cleanup for all backup types - enforces all retention limits
        
        Retention limits:
        - Auto backups: 10
        - Manual backups: 15
        - Uploaded backups: 5
        - Corrupted uploads dirs: 1 (most recent only)
        - Orphan backups (non-standard names): all removed
        """
        logger.info("🧹 Running full backup cleanup...")
        self._cleanup_old_backups()
        self._cleanup_old_manual_backups()
        self._cleanup_old_uploaded_backups()
        self._cleanup_corrupted_uploads()
        self._cleanup_orphan_backups()
        logger.info("🧹 Backup cleanup complete")
    
    def delete_backup(self, filename: str) -> bool:
        """Delete a specific backup file
        
        Args:
            filename: The filename of the backup to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            backup_path = self.backup_dir / filename
            
            # Security check - ensure it's a valid backup file
            if not backup_path.exists():
                logger.error(f"Backup file not found: {filename}")
                return False
            
            # Only allow deleting actual backup files (not corrupted or latest)
            if 'latest' in filename or 'corrupted' in filename:
                logger.error(f"Cannot delete special backup file: {filename}")
                return False
            
            if not filename.startswith('backup_') or filename.split('.')[-1] not in ['db', 'zip']:
                logger.error(f"Invalid backup filename: {filename}")
                return False
            
            backup_path.unlink()
            logger.info(f"🗑️  Deleted backup: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting backup {filename}: {e}")
            return False
    
    def get_latest_backup(self) -> Optional[Path]:
        """Get the most recent backup file (automatic or manual)"""
        # Check for latest links
        latest_zip = self.backup_dir / "backup_latest.zip"
        latest_db = self.backup_dir / "data_latest.db"
        
        if latest_zip.exists():
            return latest_zip
        if latest_db.exists():
            return latest_db
        
        # Fallback to finding most recent timestamped backup (both AUTO and MANUAL, both .db and .zip)
        backups = sorted(
            [f for f in self.backup_dir.glob("backup_*.*") 
             if f.suffix in ['.db', '.zip'] and 'latest' not in f.name],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        return backups[0] if backups else None
    
    def restore_from_backup(self, backup_file: Optional[Path] = None) -> bool:
        """Restore database from backup file (supports .db or .zip)"""
        if backup_file is None:
            backup_file = self.get_latest_backup()
        
        if backup_file is None or not backup_file.exists():
            logger.error("❌ No backup file found for restore")
            return False
        
        try:
            # Create a backup of the current (possibly corrupted) database
            if self.db_path.exists():
                corrupted_backup = self.backup_dir / f"corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                shutil.copy2(self.db_path, corrupted_backup)
                logger.info(f"💾 Saved corrupted database to {corrupted_backup}")
            
            # Backup current uploads directory
            if self.uploads_dir.exists():
                corrupted_uploads = self.backup_dir / f"corrupted_uploads_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copytree(self.uploads_dir, corrupted_uploads)
                logger.info(f"💾 Saved current uploads to {corrupted_uploads}")
            
            # Restore based on file type
            if backup_file.suffix == '.zip':
                # Extract ZIP archive (contains database + attachments)
                with zipfile.ZipFile(backup_file, 'r') as zipf:
                    # Extract database
                    zipf.extract('data.db', path=self.db_path.parent)
                    
                    # Extract attachments
                    for member in zipf.namelist():
                        if member.startswith('app/uploads/'):
                            zipf.extract(member, path='.')
                
                logger.info(f"✅ Full backup restored (DB + attachments) from {backup_file}")
            else:
                # Simple database file restore
                shutil.copy2(backup_file, self.db_path)
                logger.info(f"✅ Database restored from {backup_file}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Failed to restore database: {e}")
            return False
    
    def check_and_restore_on_startup(self) -> bool:
        """Check database integrity on startup and restore ONLY if corrupted or missing"""
        # Only restore if database doesn't exist AND backup is available
        if not self.db_path.exists():
            latest_backup = self.get_latest_backup()
            if latest_backup:
                logger.warning("⚠️  Database does not exist, attempting restore from backup")
                return self.restore_from_backup()
            else:
                # No backup available - this is a fresh install, return True to allow init
                logger.info("ℹ️  Database does not exist and no backup available (fresh install)")
                return True
        
        # Check if database is accessible and has tables
        try:
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Check if database has tables (not empty)
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            
            if table_count == 0:
                conn.close()
                logger.warning("⚠️  Database is empty, attempting restore from backup")
                return self.restore_from_backup()
            
            # Try to query a critical table to ensure it's not corrupted
            cursor.execute("SELECT COUNT(*) FROM user")
            cursor.fetchone()
            
            conn.close()
            logger.info("✅ Database integrity check passed")
            return True
        except sqlite3.DatabaseError as e:
            logger.error(f"⚠️  Database is corrupted: {e}")
            logger.info("🔄 Attempting to restore from backup...")
            return self.restore_from_backup()
        except Exception as e:
            # If table doesn't exist or other error, database might be incomplete but not corrupted
            logger.warning(f"⚠️  Database check warning: {e}")
            # Don't restore automatically - let the app handle schema creation
            return True
    
    async def start_auto_backup(self):
        """Start automatic periodic backup in background"""
        if self._backup_task is not None:
            logger.warning("Auto-backup already running")
            return
        
        # Run initial cleanup to enforce retention limits
        self.cleanup_all_old_backups()
        
        self._backup_task = asyncio.create_task(self._backup_loop())
        logger.info(f"🔄 Auto-backup started (interval: {self.backup_interval}s) - Limits: AUTO={self.max_backups}, MANUAL={self.max_manual_backups}, UPLOADED={self.max_uploaded_backups}")
    
    async def stop_auto_backup(self):
        """Stop automatic backup"""
        if self._backup_task is not None:
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                pass
            self._backup_task = None
            logger.info("⏸️  Auto-backup stopped")
    
    async def _backup_loop(self):
        """Background task for periodic backups"""
        while True:
            try:
                await asyncio.sleep(self.backup_interval)
                # Run in thread pool to avoid blocking the event loop
                await asyncio.to_thread(self.create_backup, include_attachments=True)
                await asyncio.to_thread(self.cleanup_all_old_backups)
            except asyncio.CancelledError:
                logger.info("Backup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in backup loop: {e}")
    
    def save_uploaded_backup(self, file_content: bytes, filename: str) -> Optional[Path]:
        """Save an uploaded backup file from local machine
        
        Args:
            file_content: The backup file content
            filename: Original filename (will be prefixed with timestamp)
        
        Returns:
            Path to saved backup file or None if failed
        """
        try:
            # Validate file extension
            if not filename.endswith(('.db', '.zip')):
                logger.error(f"Invalid backup file extension: {filename}")
                return None
            
            # Create unique filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            extension = '.zip' if filename.endswith('.zip') else '.db'
            new_filename = f"backup_UPLOADED_{timestamp}{extension}"
            
            backup_path = self.backup_dir / new_filename
            
            # Save the file
            with open(backup_path, 'wb') as f:
                f.write(file_content)
            
            logger.info(f"✅ Uploaded backup saved: {backup_path}")
            
            # Cleanup old uploaded backups
            self._cleanup_old_uploaded_backups()
            
            return backup_path
            
        except Exception as e:
            logger.error(f"❌ Failed to save uploaded backup: {e}")
            return None
    
    def get_backup_stats(self) -> dict:
        """Get statistics about backups (automatic, manual, and uploaded)"""
        all_backups = [f for f in self.backup_dir.glob("backup_*.*") 
                      if f.suffix in ['.db', '.zip'] and 'latest' not in f.name and 'corrupted' not in f.name]
        auto_backups = [f for f in all_backups if "_AUTO_" in f.name]
        manual_backups = [f for f in all_backups if "_MANUAL_" in f.name]
        uploaded_backups = [f for f in all_backups if "_UPLOADED_" in f.name]
        full_backups = [f for f in all_backups if f.suffix == '.zip']
        db_only_backups = [f for f in all_backups if f.suffix == '.db']
        
        if not all_backups:
            return {
                "count": 0,
                "auto_count": 0,
                "manual_count": 0,
                "uploaded_count": 0,
                "full_count": 0,
                "db_only_count": 0,
                "total_size": 0,
                "total_size_mb": 0,
                "latest": None,
                "latest_time": None,
                "oldest": None,
                "oldest_time": None,
                "limits": {
                    "auto": self.max_backups,
                    "manual": self.max_manual_backups,
                    "uploaded": self.max_uploaded_backups
                }
            }
        
        backups_sorted = sorted(all_backups, key=lambda x: x.stat().st_mtime, reverse=True)
        total_size = sum(b.stat().st_size for b in all_backups)
        
        return {
            "count": len(all_backups),
            "auto_count": len(auto_backups),
            "manual_count": len(manual_backups),
            "uploaded_count": len(uploaded_backups),
            "full_count": len(full_backups),
            "db_only_count": len(db_only_backups),
            "total_size": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "latest": backups_sorted[0].name if backups_sorted else None,
            "latest_time": datetime.fromtimestamp(backups_sorted[0].stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S') if backups_sorted else None,
            "oldest": backups_sorted[-1].name if backups_sorted else None,
            "oldest_time": datetime.fromtimestamp(backups_sorted[-1].stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S') if backups_sorted else None,
            "limits": {
                "auto": self.max_backups,
                "manual": self.max_manual_backups,
                "uploaded": self.max_uploaded_backups
            }
        }


# Global backup instance
backup_manager = DatabaseBackup()
