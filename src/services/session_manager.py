"""Session manager with state persistence."""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import aiofiles

from tab.models.conversation_session import ConversationSession, SessionStatus
from tab.models.orchestration_state import OrchestrationState
from tab.models.audit_record import AuditRecord


logger = logging.getLogger(__name__)


class SessionManager:
    """Manages conversation session lifecycle and state persistence."""

    def __init__(self, storage_path: str = "./data/sessions"):
        """Initialize session manager.

        Args:
            storage_path: Path for session storage
        """
        self.logger = logging.getLogger(__name__)
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # In-memory session cache
        self._sessions: Dict[str, ConversationSession] = {}
        self._orchestration_states: Dict[str, OrchestrationState] = {}
        self._session_locks: Dict[str, asyncio.Lock] = {}

        # Cleanup configuration
        self.auto_cleanup_enabled = True
        self.cleanup_interval_hours = 24
        self.session_timeout_hours = 48
        self._cleanup_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize session manager and load existing sessions."""
        self.logger.info("Initializing session manager")

        # Load existing sessions from storage
        await self._load_sessions_from_storage()

        # Start cleanup task if enabled
        if self.auto_cleanup_enabled:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

        self.logger.info(f"Session manager initialized with {len(self._sessions)} sessions")

    async def create_session(
        self,
        topic: str,
        participants: List[str],
        policy_id: str = "default",
        max_turns: int = 8,
        budget_usd: float = 1.0,
        **kwargs
    ) -> ConversationSession:
        """Create a new conversation session.

        Args:
            topic: Initial question or task description
            participants: List of agent identifiers
            policy_id: Policy configuration to apply
            max_turns: Maximum conversation turns allowed
            budget_usd: Maximum cost budget in USD
            **kwargs: Additional session parameters

        Returns:
            Created ConversationSession
        """
        # Create session
        session = ConversationSession(
            topic=topic,
            participants=participants,
            policy_config=policy_id,
            max_turns=max_turns,
            budget_usd=budget_usd,
            **kwargs
        )

        # Create orchestration state
        orchestration_state = OrchestrationState(
            session_id=session.session_id,
            active_agent=participants[0],
            cost_budget_remaining=budget_usd,
            turn_budget_remaining=max_turns
        )

        # Store in memory and create lock
        self._sessions[session.session_id] = session
        self._orchestration_states[session.session_id] = orchestration_state
        self._session_locks[session.session_id] = asyncio.Lock()

        # Persist to storage
        await self._save_session_to_storage(session, orchestration_state)

        self.logger.info(f"Created session {session.session_id} with {len(participants)} participants")
        return session

    async def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            ConversationSession if found, None otherwise
        """
        # Try memory cache first
        if session_id in self._sessions:
            return self._sessions[session_id]

        # Try loading from storage
        session = await self._load_session_from_storage(session_id)
        if session:
            # Cache in memory
            self._sessions[session_id] = session
            if session_id not in self._session_locks:
                self._session_locks[session_id] = asyncio.Lock()

        return session

    async def get_orchestration_state(self, session_id: str) -> Optional[OrchestrationState]:
        """Get orchestration state for session.

        Args:
            session_id: Session identifier

        Returns:
            OrchestrationState if found, None otherwise
        """
        # Try memory cache first
        if session_id in self._orchestration_states:
            return self._orchestration_states[session_id]

        # Try loading from storage
        state = await self._load_orchestration_state_from_storage(session_id)
        if state:
            self._orchestration_states[session_id] = state

        return state

    async def update_session(
        self,
        session_id: str,
        session: ConversationSession,
        orchestration_state: Optional[OrchestrationState] = None
    ) -> bool:
        """Update session state.

        Args:
            session_id: Session identifier
            session: Updated session
            orchestration_state: Updated orchestration state

        Returns:
            True if update was successful
        """
        if session_id not in self._session_locks:
            self._session_locks[session_id] = asyncio.Lock()

        async with self._session_locks[session_id]:
            try:
                # Update memory cache
                self._sessions[session_id] = session
                if orchestration_state:
                    self._orchestration_states[session_id] = orchestration_state

                # Persist to storage
                await self._save_session_to_storage(session, orchestration_state)

                return True

            except Exception as e:
                self.logger.error(f"Failed to update session {session_id}: {str(e)}")
                return False

    async def delete_session(self, session_id: str) -> bool:
        """Delete session and its data.

        Args:
            session_id: Session identifier

        Returns:
            True if deletion was successful
        """
        try:
            # Remove from memory
            self._sessions.pop(session_id, None)
            self._orchestration_states.pop(session_id, None)
            self._session_locks.pop(session_id, None)

            # Remove from storage
            session_file = self.storage_path / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()

            self.logger.info(f"Deleted session {session_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to delete session {session_id}: {str(e)}")
            return False

    async def list_sessions(
        self,
        status: Optional[SessionStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List sessions with optional filtering.

        Args:
            status: Filter by session status
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip

        Returns:
            List of session summaries
        """
        sessions = []

        # Include memory sessions
        for session in self._sessions.values():
            if status is None or session.status == status:
                sessions.append(session.get_summary_stats())

        # Include storage-only sessions (not in memory)
        storage_sessions = await self._list_storage_sessions()
        for session_id in storage_sessions:
            if session_id not in self._sessions:
                session = await self._load_session_from_storage(session_id)
                if session and (status is None or session.status == status):
                    sessions.append(session.get_summary_stats())

        # Sort by creation time (newest first)
        sessions.sort(key=lambda x: x['created_at'], reverse=True)

        # Apply pagination
        return sessions[offset:offset + limit]

    async def get_active_sessions(self) -> List[ConversationSession]:
        """Get all active sessions.

        Returns:
            List of active ConversationSession objects
        """
        active_sessions = []

        # Check memory sessions
        for session in self._sessions.values():
            if session.status == SessionStatus.ACTIVE:
                active_sessions.append(session)

        # Check storage sessions not in memory
        storage_sessions = await self._list_storage_sessions()
        for session_id in storage_sessions:
            if session_id not in self._sessions:
                session = await self._load_session_from_storage(session_id)
                if session and session.status == SessionStatus.ACTIVE:
                    active_sessions.append(session)

        return active_sessions

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        cleaned_count = 0
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.session_timeout_hours)

        # Get all sessions
        all_sessions = list(self._sessions.keys())
        storage_sessions = await self._list_storage_sessions()
        all_session_ids = set(all_sessions + storage_sessions)

        for session_id in all_session_ids:
            try:
                session = await self.get_session(session_id)
                if session:
                    # Check if session is expired
                    if (session.updated_at < cutoff_time and
                        session.status in [SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.TIMEOUT]):

                        await self.delete_session(session_id)
                        cleaned_count += 1
                        self.logger.info(f"Cleaned up expired session {session_id}")

            except Exception as e:
                self.logger.error(f"Error cleaning up session {session_id}: {str(e)}")

        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} expired sessions")

        return cleaned_count

    async def export_session_data(
        self,
        session_id: str,
        include_audit_records: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Export complete session data.

        Args:
            session_id: Session identifier
            include_audit_records: Whether to include audit records

        Returns:
            Complete session data or None if not found
        """
        session = await self.get_session(session_id)
        orchestration_state = await self.get_orchestration_state(session_id)

        if not session:
            return None

        export_data = {
            "session": session.model_dump(),
            "orchestration_state": orchestration_state.model_dump() if orchestration_state else None,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "export_version": "1.0"
        }

        if include_audit_records:
            # Load audit records from storage if available
            audit_records = await self._load_audit_records(session_id)
            export_data["audit_records"] = [record.model_dump() for record in audit_records]

        return export_data

    async def _save_session_to_storage(
        self,
        session: ConversationSession,
        orchestration_state: Optional[OrchestrationState] = None
    ) -> None:
        """Save session to persistent storage.

        Args:
            session: Session to save
            orchestration_state: Orchestration state to save
        """
        session_file = self.storage_path / f"{session.session_id}.json"

        data = {
            "session": session.model_dump(),
            "orchestration_state": orchestration_state.model_dump() if orchestration_state else None,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0"
        }

        async with aiofiles.open(session_file, 'w') as f:
            await f.write(json.dumps(data, indent=2, default=str))

    async def _load_session_from_storage(self, session_id: str) -> Optional[ConversationSession]:
        """Load session from persistent storage.

        Args:
            session_id: Session identifier

        Returns:
            ConversationSession if found, None otherwise
        """
        session_file = self.storage_path / f"{session_id}.json"

        if not session_file.exists():
            return None

        try:
            async with aiofiles.open(session_file, 'r') as f:
                content = await f.read()
                data = json.loads(content)

            session_data = data.get("session")
            if session_data:
                return ConversationSession(**session_data)

        except Exception as e:
            self.logger.error(f"Failed to load session {session_id}: {str(e)}")

        return None

    async def _load_orchestration_state_from_storage(self, session_id: str) -> Optional[OrchestrationState]:
        """Load orchestration state from persistent storage.

        Args:
            session_id: Session identifier

        Returns:
            OrchestrationState if found, None otherwise
        """
        session_file = self.storage_path / f"{session_id}.json"

        if not session_file.exists():
            return None

        try:
            async with aiofiles.open(session_file, 'r') as f:
                content = await f.read()
                data = json.loads(content)

            state_data = data.get("orchestration_state")
            if state_data:
                return OrchestrationState(**state_data)

        except Exception as e:
            self.logger.error(f"Failed to load orchestration state {session_id}: {str(e)}")

        return None

    async def _load_sessions_from_storage(self) -> None:
        """Load existing sessions from storage into memory."""
        if not self.storage_path.exists():
            return

        session_files = list(self.storage_path.glob("*.json"))
        loaded_count = 0

        for session_file in session_files:
            try:
                session_id = session_file.stem
                session = await self._load_session_from_storage(session_id)
                orchestration_state = await self._load_orchestration_state_from_storage(session_id)

                if session:
                    self._sessions[session_id] = session
                    self._session_locks[session_id] = asyncio.Lock()

                    if orchestration_state:
                        self._orchestration_states[session_id] = orchestration_state

                    loaded_count += 1

            except Exception as e:
                self.logger.error(f"Failed to load session from {session_file}: {str(e)}")

        if loaded_count > 0:
            self.logger.info(f"Loaded {loaded_count} sessions from storage")

    async def _list_storage_sessions(self) -> List[str]:
        """List session IDs available in storage.

        Returns:
            List of session IDs
        """
        if not self.storage_path.exists():
            return []

        session_files = list(self.storage_path.glob("*.json"))
        return [f.stem for f in session_files]

    async def _load_audit_records(self, session_id: str) -> List[AuditRecord]:
        """Load audit records for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of audit records
        """
        # This is a placeholder - in a full implementation, audit records
        # would be stored separately, possibly in a database or log files
        return []

    async def _periodic_cleanup(self) -> None:
        """Periodic cleanup task for expired sessions."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval_hours * 3600)  # Convert hours to seconds
                await self.cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in periodic cleanup: {str(e)}")

    async def shutdown(self) -> None:
        """Shutdown session manager and cleanup resources."""
        self.logger.info("Shutting down session manager")

        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Save all sessions to storage
        for session_id, session in self._sessions.items():
            orchestration_state = self._orchestration_states.get(session_id)
            try:
                await self._save_session_to_storage(session, orchestration_state)
            except Exception as e:
                self.logger.error(f"Failed to save session {session_id} during shutdown: {str(e)}")

        self.logger.info("Session manager shut down")

    def get_statistics(self) -> Dict[str, Any]:
        """Get session manager statistics.

        Returns:
            Statistics dictionary
        """
        status_counts = {}
        for session in self._sessions.values():
            status = session.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_sessions_in_memory": len(self._sessions),
            "status_breakdown": status_counts,
            "storage_path": str(self.storage_path),
            "auto_cleanup_enabled": self.auto_cleanup_enabled,
            "cleanup_interval_hours": self.cleanup_interval_hours,
            "session_timeout_hours": self.session_timeout_hours
        }