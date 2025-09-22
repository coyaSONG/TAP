"""Integration test for unified API parameters flow."""
import pytest
from unittest.mock import Mock, AsyncMock
from src.tab.services.conversation_orchestrator import ConversationOrchestrator

class TestUnifiedAPIFlow:
    @pytest.mark.asyncio
    async def test_limit_parameter_flow(self):
        """Test unified API parameter (limit) works in conversation flow."""
        session_manager = Mock()
        session_manager.initialize = AsyncMock()
        session_manager.shutdown = AsyncMock()
        session_manager.get_session = AsyncMock()
        session_manager.get_session.return_value = Mock(
            get_turn_messages=Mock(return_value=[])
        )

        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=Mock(),
            agent_configs={}
        )

        await orchestrator.initialize()
        context = await orchestrator.get_conversation_context(
            session_id="test", limit=5  # This must work
        )
        assert isinstance(context, list)
        await orchestrator.shutdown()