"""
Unit tests for message parsing and routing logic.

Tests the ConversationOrchestrator's message processing capabilities,
including routing, validation, and response handling.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import Dict, Any, List

from tab.services.conversation_orchestrator import ConversationOrchestrator
from tab.services.session_manager import SessionManager
from tab.services.policy_enforcer import PolicyEnforcer
from tab.models.conversation_session import ConversationSession
from tab.models.turn_message import TurnMessage
from tab.models.agent_adapter import AgentAdapter
from tab.models.orchestration_state import OrchestrationState


@pytest.fixture
def mock_session_manager():
    """Mock session manager for testing."""
    mock = AsyncMock(spec=SessionManager)
    mock.create_session.return_value = Mock(session_id="test_session")
    mock.get_session.return_value = Mock(session_id="test_session", status="active")
    mock.update_session.return_value = None
    mock.save_turn.return_value = None
    return mock


@pytest.fixture
def mock_policy_enforcer():
    """Mock policy enforcer for testing."""
    mock = AsyncMock(spec=PolicyEnforcer)
    mock.validate_turn_message.return_value = {"valid": True, "violations": []}
    mock.enforce_policy.return_value = {"allowed": True, "approval_required": False}
    mock.get_policy.return_value = {"policy_id": "default", "permission_mode": "auto"}
    return mock


@pytest.fixture
def mock_agent_configs():
    """Mock agent configurations for testing."""
    return {
        "claude_code": {
            "agent_id": "claude_code",
            "agent_type": "claude_code",
            "name": "Claude Code",
            "enabled": True,
            "command_path": "/usr/local/bin/claude"
        },
        "codex_cli": {
            "agent_id": "codex_cli",
            "agent_type": "codex_cli",
            "name": "Codex CLI",
            "enabled": True,
            "command_path": "/usr/local/bin/codex"
        }
    }


@pytest.fixture
def orchestrator(mock_session_manager, mock_policy_enforcer, mock_agent_configs):
    """ConversationOrchestrator instance for testing."""
    return ConversationOrchestrator(
        session_manager=mock_session_manager,
        policy_enforcer=mock_policy_enforcer,
        agent_configs=mock_agent_configs
    )


@pytest.fixture
def sample_conversation_session():
    """Sample conversation session for testing."""
    return ConversationSession(
        session_id="test_session",
        participants=["claude_code", "codex_cli"],
        topic="Test conversation",
        status="active",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        turn_history=[],
        metadata={"max_turns": 8, "budget_usd": 1.0},
        policy_config=None
    )


@pytest.fixture
def sample_turn_message():
    """Sample turn message for testing."""
    return TurnMessage(
        turn_id="turn_001",
        session_id="test_session",
        from_agent="user",
        to_agent="claude_code",
        role="user",
        content="Please analyze this code",
        timestamp=datetime.now(),
        policy_constraints={},
        metadata={"cost_usd": 0.01}
    )


class TestMessageRouting:
    """Test message routing functionality."""

    @pytest.mark.asyncio
    async def test_route_message_to_specific_agent(self, orchestrator, sample_turn_message):
        """Test routing message to a specific agent."""
        with patch.object(orchestrator, '_send_to_agent', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {
                "response": {"content": "Analysis complete", "from_agent": "claude_code"},
                "metadata": {"cost_usd": 0.02, "duration_ms": 1500}
            }

            result = await orchestrator.route_message(
                message=sample_turn_message,
                target_agent="claude_code"
            )

            mock_send.assert_called_once_with("claude_code", sample_turn_message)
            assert result["response"]["from_agent"] == "claude_code"

    @pytest.mark.asyncio
    async def test_route_message_auto_selection(self, orchestrator, sample_turn_message):
        """Test automatic agent selection for message routing."""
        with patch.object(orchestrator, '_select_next_agent', return_value="claude_code"):
            with patch.object(orchestrator, '_send_to_agent', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {
                    "response": {"content": "Analysis complete", "from_agent": "claude_code"},
                    "metadata": {"cost_usd": 0.02, "duration_ms": 1500}
                }

                result = await orchestrator.route_message(
                    message=sample_turn_message,
                    target_agent="auto"
                )

                mock_send.assert_called_once()
                assert result["response"]["from_agent"] == "claude_code"

    @pytest.mark.asyncio
    async def test_route_message_invalid_agent(self, orchestrator, sample_turn_message):
        """Test routing to invalid agent."""
        with pytest.raises(ValueError) as exc_info:
            await orchestrator.route_message(
                message=sample_turn_message,
                target_agent="invalid_agent"
            )

        assert "Agent 'invalid_agent' not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_route_message_agent_unavailable(self, orchestrator, sample_turn_message):
        """Test routing to unavailable agent."""
        with patch.object(orchestrator, '_check_agent_availability', return_value=False):
            with pytest.raises(RuntimeError) as exc_info:
                await orchestrator.route_message(
                    message=sample_turn_message,
                    target_agent="claude_code"
                )

            assert "not available" in str(exc_info.value)


class TestMessageValidation:
    """Test message validation functionality."""

    @pytest.mark.asyncio
    async def test_validate_message_success(self, orchestrator, sample_turn_message):
        """Test successful message validation."""
        result = await orchestrator.validate_message(
            message=sample_turn_message,
            session_id="test_session"
        )

        assert result["valid"] is True
        assert "errors" not in result or len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_validate_message_empty_content(self, orchestrator, sample_turn_message):
        """Test validation with empty message content."""
        sample_turn_message.content = ""

        result = await orchestrator.validate_message(
            message=sample_turn_message,
            session_id="test_session"
        )

        assert result["valid"] is False
        assert any("empty" in error.lower() for error in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_message_invalid_session(self, orchestrator, sample_turn_message):
        """Test validation with invalid session ID."""
        orchestrator.session_manager.get_session.side_effect = KeyError("Session not found")

        result = await orchestrator.validate_message(
            message=sample_turn_message,
            session_id="invalid_session"
        )

        assert result["valid"] is False
        assert any("session" in error.lower() for error in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_message_content_length(self, orchestrator, sample_turn_message):
        """Test validation with message content length limits."""
        sample_turn_message.content = "x" * 100000  # Very long content

        result = await orchestrator.validate_message(
            message=sample_turn_message,
            session_id="test_session"
        )

        assert result["valid"] is False
        assert any("length" in error.lower() or "size" in error.lower() for error in result["errors"])


class TestMessageParsing:
    """Test message parsing functionality."""

    @pytest.mark.asyncio
    async def test_parse_message_basic(self, orchestrator):
        """Test basic message parsing."""
        raw_message = {
            "content": "Please analyze this code",
            "to_agent": "claude_code",
            "attachments": []
        }

        parsed = await orchestrator.parse_message(
            raw_message=raw_message,
            session_id="test_session",
            from_agent="user"
        )

        assert isinstance(parsed, TurnMessage)
        assert parsed.content == "Please analyze this code"
        assert parsed.to_agent == "claude_code"
        assert parsed.from_agent == "user"
        assert parsed.session_id == "test_session"

    @pytest.mark.asyncio
    async def test_parse_message_with_attachments(self, orchestrator):
        """Test parsing message with file attachments."""
        raw_message = {
            "content": "Analyze these files",
            "to_agent": "claude_code",
            "attachments": [
                {"path": "/workspace/file1.py", "type": "file", "size": 1024},
                {"path": "/workspace/file2.py", "type": "file", "size": 2048}
            ]
        }

        parsed = await orchestrator.parse_message(
            raw_message=raw_message,
            session_id="test_session",
            from_agent="user"
        )

        assert len(parsed.attachments) == 2
        assert parsed.attachments[0]["path"] == "/workspace/file1.py"
        assert parsed.attachments[1]["size"] == 2048

    @pytest.mark.asyncio
    async def test_parse_message_invalid_format(self, orchestrator):
        """Test parsing malformed message."""
        raw_message = {
            "content": "",  # Missing required content
            "to_agent": "claude_code"
            # Missing other required fields
        }

        with pytest.raises(ValueError) as exc_info:
            await orchestrator.parse_message(
                raw_message=raw_message,
                session_id="test_session",
                from_agent="user"
            )

        assert "Invalid message format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_parse_message_sanitization(self, orchestrator):
        """Test message content sanitization."""
        raw_message = {
            "content": "<script>alert('xss')</script>Please analyze this",
            "to_agent": "claude_code",
            "attachments": []
        }

        parsed = await orchestrator.parse_message(
            raw_message=raw_message,
            session_id="test_session",
            from_agent="user"
        )

        # Should sanitize potentially malicious content
        assert "<script>" not in parsed.content
        assert "Please analyze this" in parsed.content


class TestResponseProcessing:
    """Test response processing and formatting."""

    @pytest.mark.asyncio
    async def test_process_agent_response(self, orchestrator):
        """Test processing agent response."""
        raw_response = {
            "request_id": "req_001",
            "status": "completed",
            "response": {
                "content": "Analysis complete. Found 3 issues.",
                "reasoning": "Based on code review patterns",
                "confidence": 0.85
            },
            "metadata": {
                "execution_time_ms": 2500,
                "cost_usd": 0.03,
                "tools_used": ["read", "analyze"]
            }
        }

        processed = await orchestrator.process_agent_response(
            response=raw_response,
            from_agent="claude_code",
            session_id="test_session"
        )

        assert processed["response"]["content"] == "Analysis complete. Found 3 issues."
        assert processed["response"]["from_agent"] == "claude_code"
        assert processed["metadata"]["cost_usd"] == 0.03

    @pytest.mark.asyncio
    async def test_process_agent_response_with_error(self, orchestrator):
        """Test processing agent response with errors."""
        raw_response = {
            "request_id": "req_001",
            "status": "failed",
            "response": {"content": ""},
            "metadata": {
                "execution_time_ms": 1000,
                "error_details": "Agent timeout"
            }
        }

        processed = await orchestrator.process_agent_response(
            response=raw_response,
            from_agent="claude_code",
            session_id="test_session"
        )

        assert processed["status"] == "failed"
        assert "timeout" in processed["error_details"].lower()

    @pytest.mark.asyncio
    async def test_format_response_for_client(self, orchestrator):
        """Test formatting response for client consumption."""
        internal_response = {
            "turn_id": "turn_001",
            "response": {
                "content": "Analysis complete",
                "from_agent": "claude_code",
                "metadata": {"cost_usd": 0.02}
            },
            "session_status": "active",
            "convergence_detected": False
        }

        formatted = await orchestrator.format_response_for_client(internal_response)

        assert "turn_id" in formatted
        assert "response" in formatted
        assert "session_status" in formatted
        assert formatted["response"]["from_agent"] == "claude_code"


class TestConversationFlow:
    """Test conversation flow management."""

    @pytest.mark.asyncio
    async def test_manage_conversation_turn(self, orchestrator, sample_conversation_session, sample_turn_message):
        """Test managing a complete conversation turn."""
        with patch.object(orchestrator, 'route_message', new_callable=AsyncMock) as mock_route:
            with patch.object(orchestrator, '_update_orchestration_state', new_callable=AsyncMock):
                mock_route.return_value = {
                    "turn_id": "turn_002",
                    "response": {"content": "Response", "from_agent": "claude_code"},
                    "session_status": "active"
                }

                result = await orchestrator.manage_conversation_turn(
                    session=sample_conversation_session,
                    message=sample_turn_message
                )

                mock_route.assert_called_once()
                assert result["turn_id"] == "turn_002"

    @pytest.mark.asyncio
    async def test_detect_conversation_convergence(self, orchestrator, sample_conversation_session):
        """Test conversation convergence detection."""
        # Add some turn history
        sample_conversation_session.turn_history = [
            Mock(content="Initial question", from_agent="user"),
            Mock(content="Analysis result", from_agent="claude_code"),
            Mock(content="Verification complete", from_agent="codex_cli"),
            Mock(content="Both agents agree on solution", from_agent="claude_code")
        ]

        convergence = await orchestrator.detect_convergence(sample_conversation_session)

        assert "converged" in convergence
        assert "confidence" in convergence
        assert "signals" in convergence

    @pytest.mark.asyncio
    async def test_handle_turn_limit_reached(self, orchestrator, sample_conversation_session):
        """Test handling when turn limit is reached."""
        sample_conversation_session.metadata["max_turns"] = 2
        sample_conversation_session.turn_history = [Mock(), Mock()]  # Already at limit

        result = await orchestrator.check_conversation_limits(sample_conversation_session)

        assert result["limit_reached"] is True
        assert "turn" in result["limit_type"]

    @pytest.mark.asyncio
    async def test_handle_budget_limit_reached(self, orchestrator, sample_conversation_session):
        """Test handling when budget limit is reached."""
        sample_conversation_session.metadata["budget_usd"] = 0.10
        sample_conversation_session.metadata["total_cost_usd"] = 0.12  # Over budget

        result = await orchestrator.check_conversation_limits(sample_conversation_session)

        assert result["limit_reached"] is True
        assert "budget" in result["limit_type"]


class TestAgentSelection:
    """Test agent selection logic."""

    @pytest.mark.asyncio
    async def test_select_next_agent_round_robin(self, orchestrator, sample_conversation_session):
        """Test round-robin agent selection."""
        # Mock conversation history
        sample_conversation_session.turn_history = [
            Mock(from_agent="claude_code"),
            Mock(from_agent="codex_cli")
        ]

        next_agent = await orchestrator._select_next_agent(
            session=sample_conversation_session,
            strategy="round_robin"
        )

        assert next_agent == "claude_code"  # Should cycle back

    @pytest.mark.asyncio
    async def test_select_next_agent_based_on_capability(self, orchestrator, sample_conversation_session):
        """Test agent selection based on required capability."""
        message_requiring_analysis = Mock(content="Please analyze this code for security issues")

        next_agent = await orchestrator._select_next_agent(
            session=sample_conversation_session,
            strategy="capability_based",
            required_capabilities=["code_analysis", "security_review"]
        )

        # Should select agent with required capabilities
        assert next_agent in ["claude_code", "codex_cli"]

    @pytest.mark.asyncio
    async def test_select_next_agent_load_balancing(self, orchestrator, sample_conversation_session):
        """Test agent selection with load balancing."""
        with patch.object(orchestrator, '_get_agent_load', side_effect=[0.8, 0.3]):  # claude_code busy, codex_cli free
            next_agent = await orchestrator._select_next_agent(
                session=sample_conversation_session,
                strategy="load_balanced"
            )

            assert next_agent == "codex_cli"  # Should select less loaded agent


class TestErrorHandling:
    """Test error handling in message processing."""

    @pytest.mark.asyncio
    async def test_handle_agent_timeout(self, orchestrator, sample_turn_message):
        """Test handling agent timeout during message processing."""
        with patch.object(orchestrator, '_send_to_agent', side_effect=asyncio.TimeoutError()):
            result = await orchestrator.route_message(
                message=sample_turn_message,
                target_agent="claude_code"
            )

            assert result["status"] == "timeout"
            assert "timeout" in result["error_details"].lower()

    @pytest.mark.asyncio
    async def test_handle_agent_error(self, orchestrator, sample_turn_message):
        """Test handling agent errors during message processing."""
        with patch.object(orchestrator, '_send_to_agent', side_effect=RuntimeError("Agent crashed")):
            result = await orchestrator.route_message(
                message=sample_turn_message,
                target_agent="claude_code"
            )

            assert result["status"] == "failed"
            assert "crashed" in result["error_details"].lower()

    @pytest.mark.asyncio
    async def test_handle_policy_violation(self, orchestrator, sample_turn_message):
        """Test handling policy violations during message processing."""
        orchestrator.policy_enforcer.enforce_policy.return_value = {
            "allowed": False,
            "violations": ["Tool 'delete' is disallowed"]
        }

        result = await orchestrator.route_message(
            message=sample_turn_message,
            target_agent="claude_code"
        )

        assert result["status"] == "policy_violation"
        assert "disallowed" in result["error_details"].lower()