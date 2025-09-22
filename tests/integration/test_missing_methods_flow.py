"""Integration test for missing ConversationSession methods."""
import pytest
from src.tab.models.conversation_session import ConversationSession

class TestMissingMethodsFlow:
    def test_missing_methods_integration(self):
        """Test that missing methods work in conversation flow."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test missing methods"
        )

        # These methods must exist and work
        auto_complete = session.should_auto_complete()
        assert isinstance(auto_complete, bool)

        stats = session.get_summary_stats()
        assert isinstance(stats, dict)
        assert "total_turns" in stats

        status = session.get_session_status()
        assert isinstance(status, dict)
        assert "status" in status