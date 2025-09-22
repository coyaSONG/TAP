"""End-to-end conversation flow integration test."""
import pytest
from unittest.mock import Mock, AsyncMock
from src.tab.services.conversation_orchestrator import ConversationOrchestrator
from src.tab.services.session_manager import SessionManager
from src.tab.services.policy_enforcer import PolicyEnforcer

class TestConversationFlow:
    @pytest.mark.asyncio
    async def test_end_to_end_conversation_flow(self):
        """Test complete conversation flow with enhanced services."""
        # This test will fail until all components are properly integrated
        config = {"default_max_turns": 8, "storage_directory": "/tmp/test"}

        session_manager = SessionManager(config)  # Must accept config
        policy_enforcer = PolicyEnforcer({"default": {"policy_id": "default"}})  # Must accept config
        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=policy_enforcer,
            agent_configs={"claude_code": {"agent_id": "claude_code"}}
        )  # Must accept dependencies

        await session_manager.initialize()
        await orchestrator.initialize()

        # Start conversation
        result = await orchestrator.start_conversation(
            topic="End-to-end test",
            participants=["claude_code", "codex_cli"]
        )

        assert "session_id" in result

        # Get context with unified API
        context = await orchestrator.get_conversation_context(
            session_id=result["session_id"],
            limit=5  # Must use unified parameter
        )
        assert isinstance(context, list)

        await orchestrator.shutdown()
        await session_manager.shutdown()