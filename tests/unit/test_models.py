"""
Unit tests for data models validation and serialization.

Tests all TAB data models for proper validation, serialization,
and business rule enforcement.
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any
from uuid import uuid4

from pydantic import ValidationError

from tab.models.conversation_session import ConversationSession, SessionStatus
from tab.models.turn_message import TurnMessage, MessageRole
from tab.models.agent_adapter import AgentAdapter, AgentType, AgentStatus
from tab.models.policy_configuration import PolicyConfiguration, PermissionMode
from tab.models.audit_record import AuditRecord, EventType
from tab.models.orchestration_state import OrchestrationState, ConversationFlow


class TestConversationSession:
    """Test ConversationSession model validation and behavior."""

    def test_valid_conversation_session(self):
        """Test creating a valid conversation session."""
        session = ConversationSession(
            session_id="test-session-123",
            participants=["claude_code", "codex_cli"],
            topic="Test code analysis",
            status=SessionStatus.ACTIVE,
            policy_config="default"
        )

        assert session.session_id == "test-session-123"
        assert len(session.participants) == 2
        assert session.status == SessionStatus.ACTIVE
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.updated_at, datetime)
        assert session.turn_history == []
        assert session.metadata == {}

    def test_session_id_required(self):
        """Test that session_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            ConversationSession(
                participants=["claude_code", "codex_cli"],
                topic="Test code analysis"
            )
        assert "session_id" in str(exc_info.value)

    def test_minimum_participants(self):
        """Test that at least 2 participants are required."""
        with pytest.raises(ValidationError) as exc_info:
            ConversationSession(
                session_id="test-session",
                participants=["claude_code"],
                topic="Test code analysis"
            )
        assert "at least 2 items" in str(exc_info.value)

    def test_status_transitions(self):
        """Test valid status transitions."""
        session = ConversationSession(
            session_id="test-session",
            participants=["claude_code", "codex_cli"],
            topic="Test analysis",
            status=SessionStatus.ACTIVE
        )

        # Valid transitions
        session.status = SessionStatus.COMPLETED
        assert session.status == SessionStatus.COMPLETED

        # Reset for next test
        session.status = SessionStatus.ACTIVE
        session.status = SessionStatus.FAILED
        assert session.status == SessionStatus.FAILED

    def test_serialization(self):
        """Test model serialization and deserialization."""
        session_data = {
            "session_id": "test-session",
            "participants": ["claude_code", "codex_cli"],
            "topic": "Test analysis",
            "status": "active",
            "policy_config": "default",
            "metadata": {"test": "value"}
        }

        session = ConversationSession(**session_data)
        serialized = session.dict()

        assert serialized["session_id"] == session_data["session_id"]
        assert serialized["participants"] == session_data["participants"]
        assert serialized["metadata"] == session_data["metadata"]

        # Test round-trip
        reconstructed = ConversationSession(**serialized)
        assert reconstructed.session_id == session.session_id


class TestTurnMessage:
    """Test TurnMessage model validation and behavior."""

    def test_valid_turn_message(self):
        """Test creating a valid turn message."""
        message = TurnMessage(
            turn_id="turn-001",
            session_id="session-123",
            from_agent="claude_code",
            to_agent="codex_cli",
            role=MessageRole.USER,
            content="Please analyze this code for potential issues."
        )

        assert message.turn_id == "turn-001"
        assert message.from_agent == "claude_code"
        assert message.to_agent == "codex_cli"
        assert message.role == MessageRole.USER
        assert message.content == "Please analyze this code for potential issues."
        assert isinstance(message.timestamp, datetime)

    def test_required_fields(self):
        """Test that required fields are validated."""
        with pytest.raises(ValidationError) as exc_info:
            TurnMessage(
                session_id="session-123",
                from_agent="claude_code"
                # Missing required fields
            )

        error_details = str(exc_info.value)
        assert "turn_id" in error_details
        assert "to_agent" in error_details
        assert "content" in error_details

    def test_same_agent_validation(self):
        """Test that from_agent and to_agent must be different."""
        with pytest.raises(ValidationError) as exc_info:
            TurnMessage(
                turn_id="turn-001",
                session_id="session-123",
                from_agent="claude_code",
                to_agent="claude_code",  # Same as from_agent
                role=MessageRole.USER,
                content="Test message"
            )
        assert "from_agent and to_agent must be different" in str(exc_info.value)

    def test_empty_content_validation(self):
        """Test that content cannot be empty."""
        with pytest.raises(ValidationError) as exc_info:
            TurnMessage(
                turn_id="turn-001",
                session_id="session-123",
                from_agent="claude_code",
                to_agent="codex_cli",
                role=MessageRole.USER,
                content=""  # Empty content
            )
        assert "ensure this value has at least 1 characters" in str(exc_info.value)


class TestAgentAdapter:
    """Test AgentAdapter model validation and behavior."""

    def test_valid_agent_adapter(self):
        """Test creating a valid agent adapter."""
        adapter = AgentAdapter(
            agent_id="claude_code_1",
            agent_type=AgentType.CLAUDE_CODE,
            name="Claude Code Agent",
            version="1.0.0",
            capabilities=["code_analysis", "file_operations"],
            connection_config={"timeout": 120},
            status=AgentStatus.AVAILABLE
        )

        assert adapter.agent_id == "claude_code_1"
        assert adapter.agent_type == AgentType.CLAUDE_CODE
        assert adapter.status == AgentStatus.AVAILABLE
        assert "code_analysis" in adapter.capabilities
        assert isinstance(adapter.last_health_check, datetime)

    def test_unique_agent_id(self):
        """Test agent_id uniqueness constraint."""
        # This would typically be enforced at the service layer
        # Here we just test the model accepts unique IDs
        adapter1 = AgentAdapter(
            agent_id="unique_id_1",
            agent_type=AgentType.CLAUDE_CODE,
            name="Agent 1",
            version="1.0.0"
        )

        adapter2 = AgentAdapter(
            agent_id="unique_id_2",
            agent_type=AgentType.CODEX_CLI,
            name="Agent 2",
            version="1.0.0"
        )

        assert adapter1.agent_id != adapter2.agent_id

    def test_status_transitions(self):
        """Test valid agent status transitions."""
        adapter = AgentAdapter(
            agent_id="test_agent",
            agent_type=AgentType.CLAUDE_CODE,
            name="Test Agent",
            version="1.0.0",
            status=AgentStatus.AVAILABLE
        )

        # Valid transitions
        adapter.status = AgentStatus.BUSY
        assert adapter.status == AgentStatus.BUSY

        adapter.status = AgentStatus.AVAILABLE
        assert adapter.status == AgentStatus.AVAILABLE

        adapter.status = AgentStatus.FAILED
        assert adapter.status == AgentStatus.FAILED


class TestPolicyConfiguration:
    """Test PolicyConfiguration model validation and behavior."""

    def test_valid_policy_configuration(self):
        """Test creating a valid policy configuration."""
        policy = PolicyConfiguration(
            policy_id="test_policy",
            name="Test Policy",
            description="Policy for testing",
            allowed_tools=["read", "analyze"],
            disallowed_tools=["delete", "execute"],
            permission_mode=PermissionMode.PROMPT,
            resource_limits={"max_cost_usd": 0.5, "max_time_ms": 120000}
        )

        assert policy.policy_id == "test_policy"
        assert policy.permission_mode == PermissionMode.PROMPT
        assert "read" in policy.allowed_tools
        assert "delete" in policy.disallowed_tools
        assert policy.resource_limits["max_cost_usd"] == 0.5

    def test_tool_list_overlap_validation(self):
        """Test that allowed and disallowed tools cannot overlap."""
        with pytest.raises(ValidationError) as exc_info:
            PolicyConfiguration(
                policy_id="invalid_policy",
                name="Invalid Policy",
                description="Policy with overlapping tools",
                allowed_tools=["read", "write"],
                disallowed_tools=["write", "delete"]  # 'write' overlaps
            )
        assert "cannot be both allowed and disallowed" in str(exc_info.value)

    def test_empty_tool_lists(self):
        """Test policy with empty tool lists."""
        policy = PolicyConfiguration(
            policy_id="empty_policy",
            name="Empty Policy",
            description="Policy with no tool restrictions",
            allowed_tools=[],
            disallowed_tools=[]
        )

        assert policy.allowed_tools == []
        assert policy.disallowed_tools == []


class TestAuditRecord:
    """Test AuditRecord model validation and behavior."""

    def test_valid_audit_record(self):
        """Test creating a valid audit record."""
        record = AuditRecord(
            record_id="audit-001",
            event_type=EventType.ACTION,
            session_id="session-123",
            agent_id="claude_code",
            action="code_analysis",
            result="success",
            reason="Analysis completed successfully",
            policy_applied="default",
            resource_usage={"cost_usd": 0.05, "time_ms": 1500},
            trace_id="trace-abc123"
        )

        assert record.record_id == "audit-001"
        assert record.event_type == EventType.ACTION
        assert record.action == "code_analysis"
        assert record.result == "success"
        assert isinstance(record.timestamp, datetime)
        assert record.resource_usage["cost_usd"] == 0.05

    def test_required_fields(self):
        """Test required field validation."""
        with pytest.raises(ValidationError) as exc_info:
            AuditRecord(
                event_type=EventType.ACTION,
                # Missing required fields
            )

        error_details = str(exc_info.value)
        assert "record_id" in error_details

    def test_future_timestamp_validation(self):
        """Test that timestamp cannot be in the future."""
        future_time = datetime.now(timezone.utc).replace(year=2030)

        with pytest.raises(ValidationError) as exc_info:
            AuditRecord(
                record_id="future-record",
                event_type=EventType.ACTION,
                timestamp=future_time
            )
        assert "timestamp cannot be in the future" in str(exc_info.value)


class TestOrchestrationState:
    """Test OrchestrationState model validation and behavior."""

    def test_valid_orchestration_state(self):
        """Test creating a valid orchestration state."""
        state = OrchestrationState(
            state_id="state-001",
            session_id="session-123",
            current_turn=3,
            active_agent="claude_code",
            conversation_flow=FlowState.PROCESSING,
            cost_budget_remaining=0.75,
            turn_budget_remaining=5,
            error_count=0,
            retry_count=1
        )

        assert state.state_id == "state-001"
        assert state.current_turn == 3
        assert state.conversation_flow == FlowState.PROCESSING
        assert state.cost_budget_remaining == 0.75
        assert state.turn_budget_remaining == 5

    def test_positive_turn_validation(self):
        """Test that current_turn must be positive."""
        with pytest.raises(ValidationError) as exc_info:
            OrchestrationState(
                state_id="state-001",
                session_id="session-123",
                current_turn=0,  # Invalid: must be positive
                active_agent="claude_code",
                conversation_flow=FlowState.WAITING
            )
        assert "ensure this value is greater than 0" in str(exc_info.value)

    def test_non_negative_budgets(self):
        """Test that budget values must be non-negative."""
        with pytest.raises(ValidationError) as exc_info:
            OrchestrationState(
                state_id="state-001",
                session_id="session-123",
                current_turn=1,
                active_agent="claude_code",
                conversation_flow=FlowState.WAITING,
                cost_budget_remaining=-0.1  # Invalid: negative budget
            )
        assert "ensure this value is greater than or equal to 0" in str(exc_info.value)

    def test_flow_state_transitions(self):
        """Test valid flow state transitions."""
        state = OrchestrationState(
            state_id="state-001",
            session_id="session-123",
            current_turn=1,
            active_agent="claude_code",
            conversation_flow=FlowState.WAITING
        )

        # Valid transitions
        state.conversation_flow = FlowState.PROCESSING
        assert state.conversation_flow == FlowState.PROCESSING

        state.conversation_flow = FlowState.CONVERGING
        assert state.conversation_flow == FlowState.CONVERGING


class TestModelSerialization:
    """Test model serialization and deserialization."""

    def test_json_serialization(self):
        """Test models can be serialized to JSON."""
        models = [
            ConversationSession(
                session_id="test",
                participants=["a", "b"],
                topic="test"
            ),
            TurnMessage(
                turn_id="turn-1",
                session_id="session-1",
                from_agent="a",
                to_agent="b",
                role=MessageRole.USER,
                content="test"
            ),
            AgentAdapter(
                agent_id="agent-1",
                agent_type=AgentType.CLAUDE_CODE,
                name="Test Agent",
                version="1.0.0"
            ),
            PolicyConfiguration(
                policy_id="policy-1",
                name="Test Policy",
                description="Test policy"
            ),
            AuditRecord(
                record_id="audit-1",
                event_type=EventType.ACTION
            ),
            OrchestrationState(
                state_id="state-1",
                session_id="session-1",
                current_turn=1,
                active_agent="agent-1",
                conversation_flow=FlowState.WAITING
            )
        ]

        for model in models:
            # Test serialization
            json_data = model.json()
            assert isinstance(json_data, str)

            # Test deserialization
            reconstructed = type(model).parse_raw(json_data)
            assert reconstructed.dict() == model.dict()

    def test_dict_conversion(self):
        """Test models can be converted to dictionaries."""
        session = ConversationSession(
            session_id="test",
            participants=["claude_code", "codex_cli"],
            topic="test analysis",
            metadata={"key": "value"}
        )

        session_dict = session.dict()
        assert isinstance(session_dict, dict)
        assert session_dict["session_id"] == "test"
        assert session_dict["participants"] == ["claude_code", "codex_cli"]
        assert session_dict["metadata"]["key"] == "value"

        # Test excluding fields
        session_dict_minimal = session.dict(exclude={"metadata", "turn_history"})
        assert "metadata" not in session_dict_minimal
        assert "turn_history" not in session_dict_minimal


class TestModelValidationEdgeCases:
    """Test edge cases and boundary conditions for model validation."""

    def test_very_long_strings(self):
        """Test behavior with very long string inputs."""
        long_content = "x" * 10001  # Exceeds typical limits

        with pytest.raises(ValidationError):
            TurnMessage(
                turn_id="turn-1",
                session_id="session-1",
                from_agent="a",
                to_agent="b",
                role=MessageRole.USER,
                content=long_content
            )

    def test_special_characters(self):
        """Test handling of special characters in string fields."""
        special_chars_content = "Test with special chars: äöü 中文 🚀 \n\t\""

        message = TurnMessage(
            turn_id="turn-1",
            session_id="session-1",
            from_agent="agent-a",
            to_agent="agent-b",
            role=MessageRole.USER,
            content=special_chars_content
        )

        assert message.content == special_chars_content

    def test_model_updates(self):
        """Test updating model fields after creation."""
        session = ConversationSession(
            session_id="test",
            participants=["a", "b"],
            topic="original topic"
        )

        # Update topic
        original_updated_at = session.updated_at
        session.topic = "updated topic"
        session.updated_at = datetime.now(timezone.utc)

        assert session.topic == "updated topic"
        assert session.updated_at > original_updated_at