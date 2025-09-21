"""
Unit tests for session state management.

Tests the SessionManager service for session lifecycle management,
state persistence, recovery, and JSONL logging.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, mock_open
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
import json
import tempfile
import os

from tab.services.session_manager import SessionManager
from tab.models.conversation_session import ConversationSession
from tab.models.turn_message import TurnMessage
from tab.models.orchestration_state import OrchestrationState


@pytest.fixture
def temp_session_dir():
    """Temporary directory for session storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def session_config():
    """Session manager configuration."""
    return {
        "session_dir": "/tmp/tab_sessions",
        "auto_save": True,
        "save_interval_seconds": 60,
        "max_sessions": 1000,
        "cleanup_after_days": 30,
        "compression": False,
        "backup_enabled": True
    }


@pytest.fixture
def session_manager(session_config, temp_session_dir):
    """SessionManager instance for testing."""
    session_config["session_dir"] = temp_session_dir
    return SessionManager(session_config)


@pytest.fixture
def sample_conversation_session():
    """Sample conversation session for testing."""
    return ConversationSession(
        session_id="test_session_001",
        participants=["claude_code", "codex_cli"],
        topic="Test conversation for session management",
        status="active",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        turn_history=[],
        metadata={
            "max_turns": 8,
            "budget_usd": 1.0,
            "total_cost_usd": 0.0,
            "working_directory": "/workspace"
        },
        policy_config=None
    )


@pytest.fixture
def sample_turn_messages():
    """Sample turn messages for testing."""
    base_time = datetime.now()
    return [
        TurnMessage(
            turn_id="turn_001",
            session_id="test_session_001",
            from_agent="user",
            to_agent="claude_code",
            role="user",
            content="Please analyze this code",
            timestamp=base_time,
            policy_constraints={},
            metadata={"cost_usd": 0.01}
        ),
        TurnMessage(
            turn_id="turn_002",
            session_id="test_session_001",
            from_agent="claude_code",
            to_agent="codex_cli",
            role="assistant",
            content="Analysis complete. Found 2 issues.",
            timestamp=base_time + timedelta(seconds=30),
            policy_constraints={},
            metadata={"cost_usd": 0.02}
        ),
        TurnMessage(
            turn_id="turn_003",
            session_id="test_session_001",
            from_agent="codex_cli",
            to_agent="claude_code",
            role="assistant",
            content="Verification complete. Issues confirmed.",
            timestamp=base_time + timedelta(seconds=60),
            policy_constraints={},
            metadata={"cost_usd": 0.015}
        )
    ]


@pytest.fixture
def sample_orchestration_state():
    """Sample orchestration state for testing."""
    return OrchestrationState(
        state_id="state_001",
        session_id="test_session_001",
        current_turn=3,
        active_agent="claude_code",
        conversation_flow="processing",
        convergence_signals={"consensus_reached": False},
        timeout_deadline=datetime.now() + timedelta(minutes=5),
        cost_budget_remaining=0.95,
        turn_budget_remaining=5,
        error_count=0,
        retry_count=0,
        context_summary="Code analysis in progress"
    )


class TestSessionLifecycle:
    """Test session lifecycle management."""

    @pytest.mark.asyncio
    async def test_create_session(self, session_manager, sample_conversation_session):
        """Test creating a new session."""
        created_session = await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            policy_config=sample_conversation_session.policy_config,
            metadata=sample_conversation_session.metadata
        )

        assert created_session.session_id is not None
        assert created_session.topic == sample_conversation_session.topic
        assert created_session.participants == sample_conversation_session.participants
        assert created_session.status == "active"
        assert created_session.created_at is not None

    @pytest.mark.asyncio
    async def test_get_session_existing(self, session_manager, sample_conversation_session):
        """Test retrieving an existing session."""
        # First create the session
        await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            metadata=sample_conversation_session.metadata
        )

        # Then retrieve it
        retrieved_session = await session_manager.get_session(sample_conversation_session.session_id)

        assert retrieved_session.session_id == sample_conversation_session.session_id
        assert retrieved_session.topic == sample_conversation_session.topic

    @pytest.mark.asyncio
    async def test_get_session_nonexistent(self, session_manager):
        """Test retrieving a nonexistent session."""
        with pytest.raises(KeyError):
            await session_manager.get_session("nonexistent_session")

    @pytest.mark.asyncio
    async def test_update_session(self, session_manager, sample_conversation_session):
        """Test updating an existing session."""
        # Create session first
        created_session = await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            metadata=sample_conversation_session.metadata
        )

        # Update session
        created_session.status = "completed"
        created_session.metadata["total_cost_usd"] = 0.15

        await session_manager.update_session(created_session)

        # Retrieve and verify update
        updated_session = await session_manager.get_session(created_session.session_id)
        assert updated_session.status == "completed"
        assert updated_session.metadata["total_cost_usd"] == 0.15

    @pytest.mark.asyncio
    async def test_delete_session(self, session_manager, sample_conversation_session):
        """Test deleting a session."""
        # Create session first
        created_session = await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            metadata=sample_conversation_session.metadata
        )

        # Delete session
        await session_manager.delete_session(created_session.session_id)

        # Verify deletion
        with pytest.raises(KeyError):
            await session_manager.get_session(created_session.session_id)


class TestTurnManagement:
    """Test turn message management."""

    @pytest.mark.asyncio
    async def test_save_turn(self, session_manager, sample_conversation_session, sample_turn_messages):
        """Test saving turn messages."""
        # Create session first
        created_session = await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            metadata=sample_conversation_session.metadata
        )

        # Save turns
        for turn in sample_turn_messages:
            turn.session_id = created_session.session_id
            await session_manager.save_turn(turn)

        # Verify turns are saved
        session = await session_manager.get_session(created_session.session_id)
        assert len(session.turn_history) == 3
        assert session.turn_history[0].content == "Please analyze this code"

    @pytest.mark.asyncio
    async def test_get_turn_history(self, session_manager, sample_conversation_session, sample_turn_messages):
        """Test retrieving turn history."""
        # Create session and save turns
        created_session = await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            metadata=sample_conversation_session.metadata
        )

        for turn in sample_turn_messages:
            turn.session_id = created_session.session_id
            await session_manager.save_turn(turn)

        # Get turn history
        history = await session_manager.get_turn_history(
            session_id=created_session.session_id,
            limit=2
        )

        assert len(history) == 2
        assert history[0].turn_id == "turn_003"  # Most recent first

    @pytest.mark.asyncio
    async def test_get_turn_history_with_offset(self, session_manager, sample_conversation_session, sample_turn_messages):
        """Test retrieving turn history with offset."""
        # Setup session and turns
        created_session = await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            metadata=sample_conversation_session.metadata
        )

        for turn in sample_turn_messages:
            turn.session_id = created_session.session_id
            await session_manager.save_turn(turn)

        # Get history with offset
        history = await session_manager.get_turn_history(
            session_id=created_session.session_id,
            offset=1,
            limit=2
        )

        assert len(history) == 2
        assert history[0].turn_id == "turn_002"  # Second most recent


class TestSessionPersistence:
    """Test session persistence and recovery."""

    @pytest.mark.asyncio
    async def test_save_session_to_file(self, session_manager, sample_conversation_session, temp_session_dir):
        """Test saving session to file."""
        created_session = await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            metadata=sample_conversation_session.metadata
        )

        await session_manager.save_session_to_file(created_session)

        # Check file exists
        session_file = Path(temp_session_dir) / f"{created_session.session_id}.json"
        assert session_file.exists()

        # Verify content
        with open(session_file, 'r') as f:
            saved_data = json.load(f)
            assert saved_data["session_id"] == created_session.session_id

    @pytest.mark.asyncio
    async def test_load_session_from_file(self, session_manager, sample_conversation_session, temp_session_dir):
        """Test loading session from file."""
        # Save session first
        created_session = await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            metadata=sample_conversation_session.metadata
        )
        await session_manager.save_session_to_file(created_session)

        # Clear in-memory cache
        session_manager._session_cache.clear()

        # Load from file
        loaded_session = await session_manager.load_session_from_file(created_session.session_id)

        assert loaded_session.session_id == created_session.session_id
        assert loaded_session.topic == created_session.topic

    @pytest.mark.asyncio
    async def test_recover_sessions_on_startup(self, session_manager, temp_session_dir):
        """Test recovering sessions from disk on startup."""
        # Create some session files
        session_data = {
            "session_id": "recovered_session",
            "topic": "Recovered conversation",
            "participants": ["claude_code"],
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "turn_history": [],
            "metadata": {}
        }

        session_file = Path(temp_session_dir) / "recovered_session.json"
        with open(session_file, 'w') as f:
            json.dump(session_data, f)

        # Initialize new session manager (simulating startup)
        new_manager = SessionManager({"session_dir": temp_session_dir})
        await new_manager.recover_sessions()

        # Verify session was recovered
        recovered = await new_manager.get_session("recovered_session")
        assert recovered.topic == "Recovered conversation"


class TestJSONLLogging:
    """Test JSONL logging functionality."""

    @pytest.mark.asyncio
    async def test_write_jsonl_log(self, session_manager, sample_conversation_session, sample_turn_messages):
        """Test writing JSONL logs."""
        created_session = await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            metadata=sample_conversation_session.metadata
        )

        # Write JSONL entries
        for turn in sample_turn_messages:
            turn.session_id = created_session.session_id
            await session_manager.write_jsonl_log(turn)

        # Verify JSONL file exists and has correct content
        jsonl_file = Path(session_manager.config["session_dir"]) / f"{created_session.session_id}.jsonl"
        assert jsonl_file.exists()

        lines = jsonl_file.read_text().strip().split('\n')
        assert len(lines) == 3

        # Verify first line content
        first_entry = json.loads(lines[0])
        assert first_entry["turn_id"] == "turn_001"
        assert first_entry["content"] == "Please analyze this code"

    @pytest.mark.asyncio
    async def test_read_jsonl_log(self, session_manager, sample_conversation_session, sample_turn_messages, temp_session_dir):
        """Test reading JSONL logs."""
        created_session = await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            metadata=sample_conversation_session.metadata
        )

        # Write JSONL entries
        for turn in sample_turn_messages:
            turn.session_id = created_session.session_id
            await session_manager.write_jsonl_log(turn)

        # Read back JSONL entries
        entries = await session_manager.read_jsonl_log(created_session.session_id)

        assert len(entries) == 3
        assert entries[0]["turn_id"] == "turn_001"
        assert entries[2]["content"] == "Verification complete. Issues confirmed."

    @pytest.mark.asyncio
    async def test_parse_jsonl_log_with_metadata(self, session_manager, temp_session_dir):
        """Test parsing JSONL logs with metadata extraction."""
        session_id = "test_session_metadata"

        # Create JSONL file with entries
        jsonl_content = [
            {"turn_id": "turn_001", "cost_usd": 0.01, "timestamp": "2024-01-01T10:00:00"},
            {"turn_id": "turn_002", "cost_usd": 0.02, "timestamp": "2024-01-01T10:01:00"},
            {"turn_id": "turn_003", "cost_usd": 0.015, "timestamp": "2024-01-01T10:02:00"}
        ]

        jsonl_file = Path(temp_session_dir) / f"{session_id}.jsonl"
        with open(jsonl_file, 'w') as f:
            for entry in jsonl_content:
                f.write(json.dumps(entry) + '\n')

        # Parse with metadata
        parsed = await session_manager.parse_jsonl_log(session_id, include_metadata=True)

        assert parsed["total_turns"] == 3
        assert parsed["total_cost"] == 0.045
        assert len(parsed["entries"]) == 3


class TestSessionStatus:
    """Test session status management."""

    @pytest.mark.asyncio
    async def test_get_session_status_basic(self, session_manager, sample_conversation_session):
        """Test getting basic session status."""
        created_session = await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            metadata=sample_conversation_session.metadata
        )

        status = await session_manager.get_session_status(
            session_id=created_session.session_id,
            include_history=False
        )

        assert status["session_id"] == created_session.session_id
        assert status["status"] == "active"
        assert status["participants"] == sample_conversation_session.participants
        assert "turn_history" not in status

    @pytest.mark.asyncio
    async def test_get_session_status_with_history(self, session_manager, sample_conversation_session, sample_turn_messages):
        """Test getting session status with turn history."""
        created_session = await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            metadata=sample_conversation_session.metadata
        )

        # Add some turns
        for turn in sample_turn_messages[:2]:
            turn.session_id = created_session.session_id
            await session_manager.save_turn(turn)

        status = await session_manager.get_session_status(
            session_id=created_session.session_id,
            include_history=True
        )

        assert "turn_history" in status
        assert len(status["turn_history"]) == 2

    @pytest.mark.asyncio
    async def test_list_sessions(self, session_manager):
        """Test listing sessions with filters."""
        # Create multiple sessions
        sessions = []
        for i in range(3):
            session = await session_manager.create_session(
                topic=f"Test conversation {i}",
                participants=["claude_code", "codex_cli"],
                metadata={"test_id": i}
            )
            sessions.append(session)

        # Update one session status
        sessions[1].status = "completed"
        await session_manager.update_session(sessions[1])

        # List all sessions
        all_sessions = await session_manager.list_sessions()
        assert len(all_sessions) == 3

        # List only active sessions
        active_sessions = await session_manager.list_sessions(status_filter="active")
        assert len(active_sessions) == 2

        # List with limit
        limited_sessions = await session_manager.list_sessions(limit=2)
        assert len(limited_sessions) == 2


class TestOrchestrationState:
    """Test orchestration state management."""

    @pytest.mark.asyncio
    async def test_save_orchestration_state(self, session_manager, sample_orchestration_state):
        """Test saving orchestration state."""
        await session_manager.save_orchestration_state(sample_orchestration_state)

        # Verify state is saved
        retrieved_state = await session_manager.get_orchestration_state(
            sample_orchestration_state.session_id
        )

        assert retrieved_state.state_id == sample_orchestration_state.state_id
        assert retrieved_state.current_turn == sample_orchestration_state.current_turn
        assert retrieved_state.active_agent == sample_orchestration_state.active_agent

    @pytest.mark.asyncio
    async def test_update_orchestration_state(self, session_manager, sample_orchestration_state):
        """Test updating orchestration state."""
        # Save initial state
        await session_manager.save_orchestration_state(sample_orchestration_state)

        # Update state
        sample_orchestration_state.current_turn = 4
        sample_orchestration_state.conversation_flow = "converging"
        sample_orchestration_state.cost_budget_remaining = 0.8

        await session_manager.update_orchestration_state(sample_orchestration_state)

        # Verify updates
        updated_state = await session_manager.get_orchestration_state(
            sample_orchestration_state.session_id
        )

        assert updated_state.current_turn == 4
        assert updated_state.conversation_flow == "converging"
        assert updated_state.cost_budget_remaining == 0.8


class TestAuditLogging:
    """Test audit logging functionality."""

    @pytest.mark.asyncio
    async def test_export_audit_log_json(self, session_manager, sample_conversation_session, sample_turn_messages):
        """Test exporting audit log in JSON format."""
        created_session = await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            metadata=sample_conversation_session.metadata
        )

        # Add turns
        for turn in sample_turn_messages:
            turn.session_id = created_session.session_id
            await session_manager.save_turn(turn)

        # Export audit log
        audit_data = await session_manager.export_audit_log(
            session_id=created_session.session_id,
            format="json",
            include_security_events=True
        )

        assert "data" in audit_data
        assert audit_data["record_count"] >= 3
        audit_json = json.loads(audit_data["data"])
        assert "session_info" in audit_json
        assert "conversation_log" in audit_json

    @pytest.mark.asyncio
    async def test_export_audit_log_jsonl(self, session_manager, sample_conversation_session, sample_turn_messages):
        """Test exporting audit log in JSONL format."""
        created_session = await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            metadata=sample_conversation_session.metadata
        )

        # Add turns
        for turn in sample_turn_messages:
            turn.session_id = created_session.session_id
            await session_manager.save_turn(turn)

        # Export as JSONL
        audit_data = await session_manager.export_audit_log(
            session_id=created_session.session_id,
            format="jsonl"
        )

        lines = audit_data["data"].strip().split('\n')
        assert len(lines) >= 3
        # Verify each line is valid JSON
        for line in lines:
            json.loads(line)


class TestSessionCleanup:
    """Test session cleanup and maintenance."""

    @pytest.mark.asyncio
    async def test_cleanup_old_sessions(self, session_manager, temp_session_dir):
        """Test cleaning up old sessions."""
        # Create old session files
        old_time = datetime.now() - timedelta(days=35)

        old_session_data = {
            "session_id": "old_session",
            "created_at": old_time.isoformat(),
            "status": "completed"
        }

        old_file = Path(temp_session_dir) / "old_session.json"
        with open(old_file, 'w') as f:
            json.dump(old_session_data, f)

        # Run cleanup
        cleaned_count = await session_manager.cleanup_old_sessions(max_age_days=30)

        assert cleaned_count == 1
        assert not old_file.exists()

    @pytest.mark.asyncio
    async def test_session_size_limits(self, session_manager, sample_conversation_session):
        """Test session size limits enforcement."""
        created_session = await session_manager.create_session(
            topic=sample_conversation_session.topic,
            participants=sample_conversation_session.participants,
            metadata=sample_conversation_session.metadata
        )

        # Add many turns to test size limits
        for i in range(100):
            turn = TurnMessage(
                turn_id=f"turn_{i:03d}",
                session_id=created_session.session_id,
                from_agent="test_agent",
                to_agent="other_agent",
                role="user",
                content=f"Message {i}" * 100,  # Large content
                timestamp=datetime.now(),
                policy_constraints={},
                metadata={"cost_usd": 0.01}
            )
            await session_manager.save_turn(turn)

        # Check if size limits are enforced
        session = await session_manager.get_session(created_session.session_id)

        # Should have some mechanism to handle large sessions
        assert len(session.turn_history) <= session_manager.config.get("max_turns_per_session", 1000)