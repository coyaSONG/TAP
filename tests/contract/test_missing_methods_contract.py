"""Contract tests for missing ConversationSession methods.

These tests validate that ConversationSession implements the missing methods
should_auto_complete(), get_summary_stats(), and get_session_status().
"""

import pytest
from typing import Dict, Any
from src.tab.models.conversation_session import ConversationSession
from src.tab.models.turn_message import TurnMessage, MessageRole


class TestConversationSessionMissingMethodsContract:
    """Contract tests for missing ConversationSession methods."""

    def test_should_auto_complete_method_exists(self):
        """Test that should_auto_complete() method exists with correct signature."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test missing methods"
        )

        # Method should exist
        assert hasattr(session, 'should_auto_complete')

        # Check method signature (from class, not bound instance)
        import inspect
        sig = inspect.signature(ConversationSession.should_auto_complete)
        assert len(sig.parameters) == 1  # self only
        assert sig.return_annotation == bool or sig.return_annotation == inspect.Signature.empty

    def test_should_auto_complete_returns_boolean(self):
        """Test that should_auto_complete() returns boolean value."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test auto completion logic"
        )

        # Add some test turns
        for i in range(3):
            turn = TurnMessage(
                session_id=session.session_id,
                from_agent="claude_code" if i % 2 == 0 else "codex_cli",
                to_agent="codex_cli" if i % 2 == 0 else "claude_code",
                role=MessageRole.ASSISTANT if i % 2 == 0 else MessageRole.USER,
                content=f"Test message {i+1}"
            )
            session.add_turn_message(turn)

        # Method should return boolean
        result = session.should_auto_complete()
        assert isinstance(result, bool)

    def test_get_summary_stats_method_exists(self):
        """Test that get_summary_stats() method exists with correct signature."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test summary stats"
        )

        # Method should exist
        assert hasattr(session, 'get_summary_stats')

        # Check method signature (from class, not bound instance)
        import inspect
        sig = inspect.signature(ConversationSession.get_summary_stats)
        assert len(sig.parameters) == 1  # self only
        assert sig.return_annotation in [Dict[str, Any], inspect.Signature.empty]

    def test_get_summary_stats_returns_dict_with_required_fields(self):
        """Test that get_summary_stats() returns dict with required fields."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test summary statistics"
        )

        # Add some test turns
        for i in range(4):
            turn = TurnMessage(
                session_id=session.session_id,
                from_agent="claude_code" if i % 2 == 0 else "codex_cli",
                to_agent="codex_cli" if i % 2 == 0 else "claude_code",
                role=MessageRole.ASSISTANT if i % 2 == 0 else MessageRole.USER,
                content=f"Test message {i+1} with varying length for statistics"
            )
            session.add_turn_message(turn)

        # Method should return dict with required fields
        stats = session.get_summary_stats()
        assert isinstance(stats, dict)

        # Check required fields
        required_fields = [
            "total_turns", "total_cost", "avg_turn_length",
            "participants_activity", "duration_minutes", "convergence_confidence",
            "topic", "status"
        ]
        for field in required_fields:
            assert field in stats, f"Missing required field: {field}"

        # Check field types
        assert isinstance(stats["total_turns"], int)
        assert isinstance(stats["total_cost"], (int, float))
        assert isinstance(stats["avg_turn_length"], (int, float))
        assert isinstance(stats["participants_activity"], dict)
        assert isinstance(stats["duration_minutes"], (int, float))
        assert isinstance(stats["convergence_confidence"], (int, float))
        assert isinstance(stats["topic"], str)
        assert isinstance(stats["status"], str)

    def test_get_session_status_method_exists(self):
        """Test that get_session_status() method exists with correct signature."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test session status"
        )

        # Method should exist
        assert hasattr(session, 'get_session_status')

        # Check method signature (from class, not bound instance)
        import inspect
        sig = inspect.signature(ConversationSession.get_session_status)
        assert len(sig.parameters) == 1  # self only
        assert sig.return_annotation in [Dict[str, Any], inspect.Signature.empty]

    def test_get_session_status_returns_dict_with_required_fields(self):
        """Test that get_session_status() returns dict with required fields."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test session status information"
        )

        # Add some test turns
        for i in range(2):
            turn = TurnMessage(
                session_id=session.session_id,
                from_agent="claude_code" if i % 2 == 0 else "codex_cli",
                to_agent="codex_cli" if i % 2 == 0 else "claude_code",
                role=MessageRole.ASSISTANT if i % 2 == 0 else MessageRole.USER,
                content=f"Test turn {i+1}"
            )
            session.add_turn_message(turn)

        # Method should return dict with required fields
        status = session.get_session_status()
        assert isinstance(status, dict)

        # Check required fields
        required_fields = [
            "status", "turn_progress", "budget_progress",
            "health_indicators", "next_actions", "last_activity", "active_since"
        ]
        for field in required_fields:
            assert field in status, f"Missing required field: {field}"

        # Check field types and structure
        assert isinstance(status["status"], str)
        assert isinstance(status["turn_progress"], dict)
        assert "current" in status["turn_progress"]
        assert "max" in status["turn_progress"]
        assert isinstance(status["budget_progress"], dict)
        assert "used" in status["budget_progress"]
        assert "total" in status["budget_progress"]
        assert isinstance(status["health_indicators"], list)
        assert isinstance(status["next_actions"], list)
        assert isinstance(status["last_activity"], str)
        assert isinstance(status["active_since"], str)

    def test_missing_methods_integration_with_convergence(self):
        """Test that missing methods integrate with existing convergence analysis."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test convergence integration"
        )

        # Add turns to test convergence analysis
        for i in range(5):
            turn = TurnMessage(
                session_id=session.session_id,
                from_agent="claude_code" if i % 2 == 0 else "codex_cli",
                to_agent="codex_cli" if i % 2 == 0 else "claude_code",
                role=MessageRole.ASSISTANT if i % 2 == 0 else MessageRole.USER,
                content=f"Convergence test message {i+1}"
            )
            session.add_turn_message(turn)

        # Test that should_auto_complete uses convergence signals
        auto_complete = session.should_auto_complete()
        convergence = session.check_convergence_signals()

        # They should be related - if convergence says stop, auto_complete should be True
        if not convergence.get("should_continue", True):
            assert auto_complete == True

        # Test that stats include convergence information
        stats = session.get_summary_stats()
        assert 0.0 <= stats["convergence_confidence"] <= 1.0

    def test_error_handling_for_missing_methods(self):
        """Test error handling in missing methods with invalid session state."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test error handling"
        )

        # Methods should handle empty session gracefully
        try:
            auto_complete = session.should_auto_complete()
            assert isinstance(auto_complete, bool)
        except Exception as e:
            pytest.fail(f"should_auto_complete() failed with empty session: {e}")

        try:
            stats = session.get_summary_stats()
            assert isinstance(stats, dict)
        except Exception as e:
            pytest.fail(f"get_summary_stats() failed with empty session: {e}")

        try:
            status = session.get_session_status()
            assert isinstance(status, dict)
        except Exception as e:
            pytest.fail(f"get_session_status() failed with empty session: {e}")