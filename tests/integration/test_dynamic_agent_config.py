"""Integration test for dynamic agent configuration."""
import pytest
from src.tab.models.conversation_session import ConversationSession

class TestDynamicAgentConfig:
    def test_dynamic_agent_types_accepted(self):
        """Test that conversation session accepts dynamic agent types."""
        # This should work with any agent type (not restricted to enum)
        session = ConversationSession(
            participants=["custom_agent", "another_agent"],
            topic="Dynamic agent test"
        )

        # Should not raise validation error for custom agent types
        assert session.participants == ["custom_agent", "another_agent"]