#!/usr/bin/env python3
"""
AgentFleet Session Archival and Management System

This module implements session timeout detection, archival functionality,
and session restoration capabilities for the AgentFleet system.

Requirements Satisfied:
- 13.3: Add session archival with timeout detection and session restoration
- 9.4: Session timeout detection (60 minutes) with automatic archival
- 9.4: Session restoration for resumed incidents

Usage:
    # As a module
    from capstone.session_archival import SessionArchiver, SessionManager
    
    # As a standalone service
    python session_archival.py --serve
"""

import os
import sys
import json
import time
import uuid
import sqlite3
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path

# Add capstone to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ArchivedSession:
    """Archived session data structure."""
    session_id: str
    session_data: Dict[str, Any]
    archived_at: datetime
    restored_at: Optional[datetime] = None
    restore_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


class SessionArchiver:
    """
    Session archiving system for long-term storage of session data.
    
    Features:
    - Automatic session archival based on timeout
    - Persistent storage in SQLite database
    - Session restoration with data integrity
    - Archive cleanup and maintenance
    - Query and search capabilities
    """
    
    def __init__(self, db_path: str = "data/sessions.db"):
        """
        Initialize session archiver.
        
        Args:
            db_path: Path to SQLite database for session storage
        """
        self.db_path = db_path
        
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
        
        # Archival configuration
        self.archive_threshold = 3600  # 60 minutes
        self.cleanup_interval = 86400  # 24 hours
        self.max_archive_age = 2592000  # 30 days
        
        logger.info("Session Archiver initialized")
    
    def _init_database(self):
        """Initialize SQLite database for session storage."""
        with sqlite3.connect(self.db_path) as conn:
            # Create sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS archived_sessions (
                    session_id TEXT PRIMARY KEY,
                    session_data TEXT NOT NULL,
                    archived_at TEXT NOT NULL,
                    restored_at TEXT,
                    restore_count INTEGER DEFAULT 0,
                    metadata TEXT,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_archived_sessions_archived_at 
                ON archived_sessions(archived_at)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_archived_sessions_restore_count 
                ON archived_sessions(restore_count)
            """)
    
    def archive_session(self, session_data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Archive a session.
        
        Args:
            session_data: Complete session data to archive
            metadata: Optional metadata for the archived session
            
        Returns:
            Archive ID (same as session_id)
        """
        session_id = session_data.get("session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
            session_data["session_id"] = session_id
        
        archived_session = ArchivedSession(
            session_id=session_id,
            session_data=session_data,
            archived_at=datetime.now(),
            metadata=metadata or {},
            tags=self._extract_tags(session_data)
        )
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO archived_sessions 
                (session_id, session_data, archived_at, restored_at, restore_count, metadata, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                archived_session.session_id,
                json.dumps(archived_session.session_data),
                archived_session.archived_at.isoformat(),
                None,
                0,
                json.dumps(archived_session.metadata),
                json.dumps(archived_session.tags)
            ))
        
        logger.info(f"Archived session {session_id}")
        return session_id
    
    def restore_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Restore an archived session.
        
        Args:
            session_id: Session ID to restore
            
        Returns:
            Restored session data or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT session_data, restored_at, restore_count, metadata
                FROM archived_sessions 
                WHERE session_id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            if not row:
                logger.warning(f"Session {session_id} not found in archives")
                return None
            
            session_data = json.loads(row[0])
            last_restored = row[1]
            restore_count = row[2]
            
            # Update restore information
            new_restore_count = restore_count + 1
            new_restored_at = datetime.now().isoformat()
            
            conn.execute("""
                UPDATE archived_sessions 
                SET restored_at = ?, restore_count = ?
                WHERE session_id = ?
            """, (new_restored_at, new_restore_count, session_id))
            
            # Add restore metadata
            session_data["restored"] = True
            session_data["restore_count"] = new_restore_count
            session_data["last_restored_at"] = new_restored_at
            
            logger.info(f"Restored session {session_id} (attempt #{new_restore_count})")
            return session_data
    
    def get_archived_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about an archived session without restoring it.
        
        Args:
            session_id: Session ID to look up
            
        Returns:
            Session information or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT session_id, archived_at, restored_at, restore_count, metadata, tags
                FROM archived_sessions 
                WHERE session_id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                "session_id": row[0],
                "archived_at": row[1],
                "restored_at": row[2],
                "restore_count": row[3],
                "metadata": json.loads(row[4]) if row[4] else {},
                "tags": json.loads(row[5]) if row[5] else []
            }
    
    def list_archived_sessions(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List archived sessions with pagination.
        
        Args:
            limit: Maximum number of sessions to return
            offset: Offset for pagination
            
        Returns:
            List of archived session information
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT session_id, archived_at, restored_at, restore_count, metadata, tags
                FROM archived_sessions 
                ORDER BY archived_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            sessions = []
            for row in cursor.fetchall():
                sessions.append({
                    "session_id": row[0],
                    "archived_at": row[1],
                    "restored_at": row[2],
                    "restore_count": row[3],
                    "metadata": json.loads(row[4]) if row[4] else {},
                    "tags": json.loads(row[5]) if row[5] else []
                })
            
            return sessions
    
    def search_archived_sessions(self, query: str, tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search archived sessions by content and tags.
        
        Args:
            query: Search query (searches in session data)
            tags: Optional list of tags to filter by
            
        Returns:
            List of matching archived sessions
        """
        with sqlite3.connect(self.db_path) as conn:
            # Build WHERE clause
            where_clauses = []
            params = []
            
            if query:
                where_clauses.append("session_data LIKE ?")
                params.append(f"%{query}%")
            
            if tags:
                where_clauses.append("tags LIKE ?")
                params.append(f"%{json.dumps(tags)}%")
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            cursor = conn.execute(f"""
                SELECT session_id, archived_at, restored_at, restore_count, metadata, tags
                FROM archived_sessions 
                WHERE {where_sql}
                ORDER BY archived_at DESC
                LIMIT 50
            """, params)
            
            sessions = []
            for row in cursor.fetchall():
                sessions.append({
                    "session_id": row[0],
                    "archived_at": row[1],
                    "restored_at": row[2],
                    "restore_count": row[3],
                    "metadata": json.loads(row[4]) if row[4] else {},
                    "tags": json.loads(row[5]) if row[5] else []
                })
            
            return sessions
    
    def cleanup_old_archives(self, max_age_days: Optional[int] = None) -> int:
        """
        Clean up old archived sessions.
        
        Args:
            max_age_days: Maximum age in days (uses default if None)
            
        Returns:
            Number of sessions cleaned up
        """
        max_age = max_age_days or (self.max_archive_age // 86400)  # Convert to days
        cutoff_date = datetime.now() - timedelta(days=max_age)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM archived_sessions 
                WHERE archived_at < ?
            """, (cutoff_date.isoformat(),))
            
            deleted_count = cursor.rowcount
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old archived sessions")
            
            return deleted_count
    
    def get_archive_stats(self) -> Dict[str, Any]:
        """Get archive statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Total archived sessions
            cursor = conn.execute("SELECT COUNT(*) FROM archived_sessions")
            total_sessions = cursor.fetchone()[0]
            
            # Sessions with restores
            cursor = conn.execute("SELECT COUNT(*) FROM archived_sessions WHERE restore_count > 0")
            restored_sessions = cursor.fetchone()[0]
            
            # Oldest and newest archives
            cursor = conn.execute("SELECT MIN(archived_at), MAX(archived_at) FROM archived_sessions")
            date_range = cursor.fetchone()
            
            # Average restore count
            cursor = conn.execute("SELECT AVG(restore_count) FROM archived_sessions")
            avg_restore_count = cursor.fetchone()[0] or 0
            
            return {
                "total_archived": total_sessions,
                "restored_sessions": restored_sessions,
                "restore_rate": (restored_sessions / total_sessions * 100) if total_sessions > 0 else 0,
                "oldest_archive": date_range[0],
                "newest_archive": date_range[1],
                "average_restore_count": round(avg_restore_count, 2)
            }
    
    def _extract_tags(self, session_data: Dict[str, Any]) -> List[str]:
        """Extract tags from session data."""
        tags = []
        
        # Extract from session metadata
        if "metadata" in session_data:
            metadata = session_data["metadata"]
            if "source_agent" in metadata:
                tags.append(f"source:{metadata['source_agent']}")
            if "severity" in metadata:
                tags.append(f"severity:{metadata['severity']}")
        
        # Extract from status
        if "status" in session_data:
            tags.append(f"status:{session_data['status']}")
        
        # Extract from incident type if available
        if "incident_id" in session_data:
            tags.append("incident:yes")
        
        return tags
    
    def archive_session_with_timeout(self, session_data: Dict[str, Any], timeout_seconds: int = 3600) -> str:
        """
        Archive a session with automatic timeout-based archival.
        
        Args:
            session_data: Session data to archive
            timeout_seconds: Timeout in seconds before archival
            
        Returns:
            Archive ID
        """
        # Add timeout metadata
        if "metadata" not in session_data:
            session_data["metadata"] = {}
        
        session_data["metadata"]["archive_timeout"] = timeout_seconds
        session_data["metadata"]["archive_scheduled"] = (
            datetime.now() + timedelta(seconds=timeout_seconds)
        ).isoformat()
        
        return self.archive_session(session_data)


class SessionManager:
    """
    Session lifecycle manager with automatic archival.
    
    Features:
    - Session timeout detection
    - Automatic archival of inactive sessions
    - Session restoration from archives
    - Background cleanup and maintenance
    - Session statistics and monitoring
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize session manager.
        
        Args:
            config: Session manager configuration
        """
        self.config = config or self._default_config()
        
        # Core components
        self.archiver = SessionArchiver()
        
        # Active sessions
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        
        # Background processing
        self.running = False
        self.monitoring_thread = None
        self.cleanup_thread = None
        
        # Statistics
        self.stats = {
            "active_sessions": 0,
            "archived_sessions": 0,
            "restored_sessions": 0,
            "expired_sessions": 0,
            "cleanup_runs": 0
        }
        
        logger.info("Session Manager initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default session manager configuration."""
        return {
            "session_timeout": 3600,  # 60 minutes
            "monitoring_interval": 300,  # 5 minutes
            "cleanup_interval": 86400,  # 24 hours
            "enable_auto_archive": True,
            "enable_auto_cleanup": True
        }
    
    def start(self):
        """Start session manager."""
        if self.running:
            logger.warning("Session Manager already running")
            return
        
        self.running = True
        
        # Start monitoring thread
        self.monitoring_thread = threading.Thread(target=self._monitor_sessions, daemon=True)
        self.monitoring_thread.start()
        
        # Start cleanup thread if enabled
        if self.config["enable_auto_cleanup"]:
            self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
            self.cleanup_thread.start()
        
        logger.info("Session Manager started")
    
    def stop(self):
        """Stop session manager."""
        self.running = False
        
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=10)
        
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=10)
        
        logger.info("Session Manager stopped")
    
    def create_session(self, session_data: Dict[str, Any]) -> str:
        """
        Create a new session.
        
        Args:
            session_data: Session data
            
        Returns:
            Session ID
        """
        session_id = session_data.get("session_id", str(uuid.uuid4()))
        session_data["session_id"] = session_id
        session_data["created_at"] = datetime.now().isoformat()
        session_data["last_activity"] = datetime.now().isoformat()
        session_data["status"] = "active"
        
        with self._lock:
            self.active_sessions[session_id] = session_data
            self.stats["active_sessions"] = len(self.active_sessions)
        
        logger.debug(f"Created session {session_id}")
        return session_id
    
    def update_session_activity(self, session_id: str):
        """Update session last activity timestamp."""
        with self._lock:
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["last_activity"] = datetime.now().isoformat()
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        with self._lock:
            return self.active_sessions.get(session_id)
    
    def archive_session(self, session_id: str, reason: str = "manual"):
        """
        Archive a specific session.
        
        Args:
            session_id: Session ID to archive
            reason: Reason for archival
            
        Returns:
            True if archived successfully
        """
        with self._lock:
            if session_id not in self.active_sessions:
                logger.warning(f"Session {session_id} not found in active sessions")
                return False
            
            session_data = self.active_sessions[session_id]
            session_data["archived_at"] = datetime.now().isoformat()
            session_data["archive_reason"] = reason
            session_data["status"] = "archived"
            
            # Archive the session
            archive_id = self.archiver.archive_session(session_data)
            
            # Remove from active sessions
            del self.active_sessions[session_id]
            self.stats["active_sessions"] = len(self.active_sessions)
            self.stats["archived_sessions"] += 1
            
            logger.info(f"Archived session {session_id} ({reason})")
            return True
    
    def restore_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Restore a session from archives.
        
        Args:
            session_id: Session ID to restore
            
        Returns:
            Restored session data or None if not found
        """
        # Try to restore from archives
        restored_data = self.archiver.restore_session(session_id)
        if not restored_data:
            logger.warning(f"Session {session_id} not found in archives")
            return None
        
        # Add back to active sessions
        restored_data["status"] = "restored"
        restored_data["restored_at"] = datetime.now().isoformat()
        
        with self._lock:
            self.active_sessions[session_id] = restored_data
            self.stats["active_sessions"] = len(self.active_sessions)
            self.stats["restored_sessions"] += 1
        
        logger.info(f"Restored session {session_id}")
        return restored_data
    
    def _monitor_sessions(self):
        """Background session monitoring loop."""
        while self.running:
            try:
                self._check_session_timeout()
                time.sleep(self.config["monitoring_interval"])
            except Exception as e:
                logger.error(f"Session monitoring error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def _check_session_timeout(self):
        """Check for sessions that need to be archived due to timeout."""
        if not self.config["enable_auto_archive"]:
            return
        
        now = datetime.now()
        timeout_threshold = self.config["session_timeout"]
        sessions_to_archive = []
        
        with self._lock:
            for session_id, session_data in self.active_sessions.items():
                last_activity_str = session_data.get("last_activity")
                if not last_activity_str:
                    continue
                
                last_activity = datetime.fromisoformat(last_activity_str)
                age = now - last_activity
                
                if age.total_seconds() > timeout_threshold:
                    sessions_to_archive.append(session_id)
        
        # Archive expired sessions
        for session_id in sessions_to_archive:
            self.archive_session(session_id, "timeout")
            self.stats["expired_sessions"] += 1
    
    def _cleanup_loop(self):
        """Background cleanup loop."""
        while self.running:
            try:
                archived_count = self.archiver.cleanup_old_archives()
                if archived_count > 0:
                    self.stats["cleanup_runs"] += 1
                
                time.sleep(self.config["cleanup_interval"])
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
                time.sleep(3600)  # Wait 1 hour before retrying
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session manager statistics."""
        archive_stats = self.archiver.get_archive_stats()
        
        return {
            "session_manager": self.stats.copy(),
            "archives": archive_stats,
            "config": self.config
        }


def main():
    """Main entry point for standalone usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AgentFleet Session Archival System")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run as session management service"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show session archival status"
    )
    parser.add_argument(
        "--archive",
        help="Archive a specific session (provide session data file)"
    )
    parser.add_argument(
        "--restore",
        help="Restore a specific session (provide session ID)"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Run cleanup of old archives"
    )
    
    args = parser.parse_args()
    
    # Change to capstone directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    if args.status:
        # Show status
        archiver = SessionArchiver()
        stats = archiver.get_archive_stats()
        
        print("\nSession Archive Status:")
        print("=" * 40)
        for key, value in stats.items():
            print(f"{key}: {value}")
        print("=" * 40)
        return
    
    if args.archive:
        # Archive session
        try:
            with open(args.archive, 'r') as f:
                session_data = json.load(f)
            
            archiver = SessionArchiver()
            archive_id = archiver.archive_session(session_data)
            print(f"Archived session with ID: {archive_id}")
        except Exception as e:
            print(f"Archive failed: {e}")
        return
    
    if args.restore:
        # Restore session
        archiver = SessionArchiver()
        session_data = archiver.restore_session(args.restore)
        
        if session_data:
            print(f"Restored session {args.restore}")
            print(json.dumps(session_data, indent=2))
        else:
            print(f"Session {args.restore} not found")
        return
    
    if args.cleanup:
        # Run cleanup
        archiver = SessionArchiver()
        cleaned_count = archiver.cleanup_old_archives()
        print(f"Cleaned up {cleaned_count} old archives")
        return
    
    if args.serve:
        # Start session management service
        print("Starting Session Management Service...")
        
        try:
            session_manager = SessionManager()
            session_manager.start()
            
            print("Session Management Service running. Press Ctrl+C to stop.")
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down...")
                
        except Exception as e:
            logger.error(f"Service error: {e}")
        finally:
            session_manager.stop()
    else:
        print("Please specify --serve, --status, --archive, --restore, or --cleanup")
        sys.exit(1)


if __name__ == "__main__":
    main()