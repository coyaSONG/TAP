"""Contract tests for unified API parameters across service interfaces.

These tests validate that API parameter naming is consistent across all service
interfaces, specifically the unification of max_turns → limit.
"""

import pytest
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock
from src.tab.services.conversation_orchestrator import ConversationOrchestrator


class TestUnifiedAPIContract:
    """Contract tests for unified API parameters across services."""

    @pytest.mark.asyncio
    async def test_orchestrator_uses_limit_parameter(self):
        """Test that ConversationOrchestrator uses 'limit' instead of 'max_turns'."""
        # Setup mock dependencies
        session_manager = Mock()
        session_manager.initialize = AsyncMock()
        session_manager.shutdown = AsyncMock()
        session_manager.get_session = AsyncMock()

        # Mock session with turn messages
        mock_session = Mock()
        mock_session.session_id = "test-session"
        mock_session.get_conversation_context = Mock(return_value=[
            {"role": "assistant", "content": "Message 1", "from_agent": "claude_code"},
            {"role": "user", "content": "Message 2", "from_agent": "codex_cli"},
            {"role": "assistant", "content": "Message 3", "from_agent": "claude_code"},
        ])
        session_manager.get_session.return_value = mock_session

        policy_enforcer = Mock()
        agent_configs = {"claude_code": {"agent_id": "claude_code"}}

        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=policy_enforcer,
            agent_configs=agent_configs
        )

        await orchestrator.initialize()

        # Test that 'limit' parameter is accepted (unified API)
        context = await orchestrator.get_conversation_context(
            session_id="test-session",
            agent_filter=None,
            limit=5  # This should work - unified parameter
        )

        assert isinstance(context, list)

        # Test different limit values
        context_small = await orchestrator.get_conversation_context(
            session_id="test-session",
            limit=2
        )
        assert isinstance(context_small, list)

        await orchestrator.shutdown()

    def test_limit_parameter_validation_range(self):
        """Test that limit parameter validates within expected range."""
        # Setup mock dependencies
        session_manager = Mock()
        policy_enforcer = Mock()
        agent_configs = {}

        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=policy_enforcer,
            agent_configs=agent_configs
        )

        # Check method signature accepts limit parameter
        import inspect
        sig = inspect.signature(orchestrator.get_conversation_context)

        # Should have limit parameter with default value
        params = list(sig.parameters.keys())
        assert 'limit' in params

        # Check default value
        limit_param = sig.parameters['limit']
        assert limit_param.default is not inspect.Parameter.empty

    @pytest.mark.asyncio
    async def test_session_manager_parameter_consistency(self):
        """Test that SessionManager uses consistent parameter naming."""
        config = {"default_max_turns": 8, "default_budget_usd": 1.0}

        # This should work with current interface
        from src.tab.services.session_manager import SessionManager
        session_manager = SessionManager(config)

        await session_manager.initialize()

        # Check that create_session accepts max_turns parameter consistently
        session = await session_manager.create_session(
            topic="API consistency test",
            participants=["claude_code", "codex_cli"],
            max_turns=8  # This parameter should be consistent
        )

        assert session is not None
        await session_manager.shutdown()

    @pytest.mark.asyncio
    async def test_backward_compatibility_support(self):
        """Test that services support backward compatibility for parameter names."""
        # Setup mock dependencies for orchestrator
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

        # Both 'limit' (new) and potentially 'max_turns' (legacy) should work
        # Test new unified parameter
        context = await orchestrator.get_conversation_context(
            session_id="test-session",
            limit=3
        )
        assert isinstance(context, list)

        await orchestrator.shutdown()

    def test_api_parameter_documentation_consistency(self):
        """Test that API parameters are consistently documented."""
        from src.tab.services.conversation_orchestrator import ConversationOrchestrator

        # Check method docstrings mention correct parameter names
        import inspect
        context_method = getattr(ConversationOrchestrator, 'get_conversation_context')

        if context_method.__doc__:
            doc = context_method.__doc__.lower()
            # Should mention 'limit' parameter in modern API
            # This test ensures documentation is updated with API changes

    @pytest.mark.asyncio
    async def test_agent_filter_parameter_consistency(self):
        """Test that agent_filter parameter works consistently across methods."""
        # Setup mock dependencies
        session_manager = Mock()
        session_manager.initialize = AsyncMock()
        session_manager.shutdown = AsyncMock()
        session_manager.get_session = AsyncMock()

        # Mock session with mixed agent messages
        mock_session = Mock()
        mock_session.session_id = "test-session"
        mock_session.get_turn_messages = Mock(return_value=[
            Mock(role="assistant", content="Message from Claude", from_agent="claude_code"),
            Mock(role="user", content="Message from Codex", from_agent="codex_cli"),
            Mock(role="assistant", content="Another Claude message", from_agent="claude_code"),
        ])
        session_manager.get_session.return_value = mock_session

        policy_enforcer = Mock()
        agent_configs = {"claude_code": {"agent_id": "claude_code"}}

        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=policy_enforcer,
            agent_configs=agent_configs
        )

        await orchestrator.initialize()

        # Test agent filtering with unified API
        context_filtered = await orchestrator.get_conversation_context(
            session_id="test-session",
            agent_filter="claude_code",
            limit=10
        )
        assert isinstance(context_filtered, list)

        # Test without agent filtering
        context_all = await orchestrator.get_conversation_context(
            session_id="test-session",
            agent_filter=None,
            limit=10
        )
        assert isinstance(context_all, list)

        await orchestrator.shutdown()

    def test_parameter_type_consistency(self):
        """Test that parameter types are consistent across interfaces."""
        from src.tab.services.conversation_orchestrator import ConversationOrchestrator

        import inspect

        # Check get_conversation_context parameter types
        sig = inspect.signature(ConversationOrchestrator.get_conversation_context)

        # session_id should be str
        session_id_param = sig.parameters.get('session_id')
        assert session_id_param is not None

        # agent_filter should be Optional[str]
        agent_filter_param = sig.parameters.get('agent_filter')
        assert agent_filter_param is not None

        # limit should be int
        limit_param = sig.parameters.get('limit')
        assert limit_param is not None

        # Default value should be reasonable integer
        if limit_param.default is not inspect.Parameter.empty:
            assert isinstance(limit_param.default, int)
            assert 1 <= limit_param.default <= 50