"""Contract tests for ConversationOrchestrator dependency injection.

These tests validate that ConversationOrchestrator properly accepts injected
dependencies as expected by TABApplication service container.
"""

import pytest
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock
from src.tab.services.conversation_orchestrator import ConversationOrchestrator


class TestConversationOrchestratorContract:
    """Contract tests for ConversationOrchestrator enhanced constructor."""

    def test_orchestrator_accepts_dependency_injection(self):
        """Test that ConversationOrchestrator accepts injected dependencies."""
        # Create mock dependencies
        session_manager = Mock()
        session_manager.initialize = AsyncMock()
        session_manager.shutdown = AsyncMock()

        policy_enforcer = Mock()

        agent_configs = {
            "claude_code": {
                "agent_id": "claude_code",
                "agent_type": "claude_code",
                "name": "Claude Code"
            },
            "codex_cli": {
                "agent_id": "codex_cli",
                "agent_type": "codex_cli",
                "name": "Codex CLI"
            }
        }

        # This should work with enhanced constructor
        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=policy_enforcer,
            agent_configs=agent_configs
        )
        assert orchestrator is not None

    def test_orchestrator_dependency_validation(self):
        """Test that ConversationOrchestrator validates injected dependencies."""
        # Missing required dependency should raise error
        with pytest.raises((TypeError, ValueError)):
            ConversationOrchestrator(
                session_manager=None,  # Missing required dependency
                policy_enforcer=Mock(),
                agent_configs={}
            )

    @pytest.mark.asyncio
    async def test_orchestrator_start_conversation_contract(self):
        """Test start_conversation method contract."""
        # Setup mock dependencies
        session_manager = Mock()
        session_manager.initialize = AsyncMock()
        session_manager.shutdown = AsyncMock()
        session_manager.create_session = AsyncMock()
        session_manager.create_session.return_value = Mock(session_id="test-session-123")

        policy_enforcer = Mock()
        policy_enforcer.validate_session_creation = Mock(return_value={"allowed": True, "violations": []})

        agent_configs = {"claude_code": {"agent_id": "claude_code"}}

        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=policy_enforcer,
            agent_configs=agent_configs
        )

        await orchestrator.initialize()

        # Test conversation start
        result = await orchestrator.start_conversation(
            topic="Test dependency injection",
            participants=["claude_code", "codex_cli"]
        )

        assert isinstance(result, dict)
        assert "session_id" in result

        await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_orchestrator_get_conversation_context_unified_api(self):
        """Test get_conversation_context with unified parameters (limit vs max_turns)."""
        # Setup mock dependencies
        session_manager = Mock()
        session_manager.initialize = AsyncMock()
        session_manager.shutdown = AsyncMock()
        session_manager.get_session = AsyncMock()
        session_manager.get_session.return_value = Mock(
            session_id="test-session",
            get_turn_messages=Mock(return_value=[])
        )

        policy_enforcer = Mock()
        agent_configs = {"claude_code": {"agent_id": "claude_code"}}

        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=policy_enforcer,
            agent_configs=agent_configs
        )

        await orchestrator.initialize()

        # Test unified API parameter (limit instead of max_turns)
        context = await orchestrator.get_conversation_context(
            session_id="test-session",
            agent_filter="claude_code",
            limit=5  # Unified parameter name
        )

        assert isinstance(context, list)

        await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_orchestrator_process_turn_contract(self):
        """Test process_turn method contract."""
        # Setup mock dependencies
        session_manager = Mock()
        session_manager.initialize = AsyncMock()
        session_manager.shutdown = AsyncMock()
        session_manager.get_session = AsyncMock()
        session_manager.get_session.return_value = Mock(
            session_id="test-session",
            add_turn_message=Mock()
        )

        policy_enforcer = Mock()
        policy_enforcer.validate_turn_addition = Mock(return_value={"allowed": True, "violations": []})

        agent_configs = {"claude_code": {"agent_id": "claude_code"}}

        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=policy_enforcer,
            agent_configs=agent_configs
        )

        await orchestrator.initialize()

        # Test turn processing
        result = await orchestrator.process_turn(
            session_id="test-session",
            content="Test message",
            from_agent="claude_code",
            to_agent="codex_cli"
        )

        assert isinstance(result, dict)

        await orchestrator.shutdown()

    def test_orchestrator_interface_compliance(self):
        """Test that ConversationOrchestrator implements expected interface."""
        session_manager = Mock()
        policy_enforcer = Mock()
        agent_configs = {}

        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=policy_enforcer,
            agent_configs=agent_configs
        )

        # Check required async methods exist
        assert hasattr(orchestrator, 'start_conversation')
        assert hasattr(orchestrator, 'get_conversation_context')
        assert hasattr(orchestrator, 'process_turn')
        assert hasattr(orchestrator, 'initialize')
        assert hasattr(orchestrator, 'shutdown')

        # Check methods are coroutines
        import inspect
        assert inspect.iscoroutinefunction(orchestrator.start_conversation)
        assert inspect.iscoroutinefunction(orchestrator.get_conversation_context)
        assert inspect.iscoroutinefunction(orchestrator.process_turn)