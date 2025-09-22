"""Unit tests for missing ConversationSession methods.

Tests the implementation of should_auto_complete(), get_summary_stats(),
and get_session_status() methods to ensure they work correctly and
integrate properly with existing convergence logic.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from src.tab.models.conversation_session import ConversationSession, SessionStatus
from src.tab.models.turn_message import TurnMessage, MessageRole


class TestShouldAutoComplete:
    """Test should_auto_complete() method implementation."""

    def test_should_auto_complete_with_explicit_completion(self):
        """Test auto-completion with explicit completion signals."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test explicit completion"
        )

        # Add turns with completion keywords
        completion_turn = TurnMessage(
            session_id=session.session_id,
            from_agent="claude_code",
            to_agent="codex_cli",
            role=MessageRole.ASSISTANT,
            content="Task completed successfully. Implementation finished."
        )
        session.add_turn_message(completion_turn)

        # Mock convergence signals to return explicit completion
        with patch.object(session, 'check_convergence_signals') as mock_convergence:
            mock_convergence.return_value = {
                "signals": {
                    "explicit_completion": True,
                    "resource_exhaustion": False,
                    "repetitive_content": False,
                    "quality_degradation": False
                },
                "confidence": 0.9
            }

            assert session.should_auto_complete() is True

    def test_should_auto_complete_with_resource_exhaustion(self):
        """Test auto-completion with resource exhaustion."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test resource exhaustion",
            max_turns=10,
            budget_usd=1.0
        )

        # Simulate near resource exhaustion
        session.current_turn = 9  # Near max turns
        session.total_cost_usd = 0.95  # Near budget limit

        with patch.object(session, 'check_convergence_signals') as mock_convergence:
            mock_convergence.return_value = {
                "signals": {
                    "explicit_completion": False,
                    "resource_exhaustion": True,
                    "repetitive_content": False,
                    "quality_degradation": False
                },
                "confidence": 0.85
            }

            assert session.should_auto_complete() is True

    def test_should_auto_complete_with_repetitive_content(self):
        """Test auto-completion with repetitive content detection."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test repetitive content"
        )

        with patch.object(session, 'check_convergence_signals') as mock_convergence:
            mock_convergence.return_value = {
                "signals": {
                    "explicit_completion": False,
                    "resource_exhaustion": False,
                    "repetitive_content": True,
                    "quality_degradation": False
                },
                "confidence": 0.3  # Low confidence due to repetition
            }

            assert session.should_auto_complete() is True

    def test_should_auto_complete_with_quality_degradation(self):
        """Test auto-completion with quality degradation."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test quality degradation"
        )

        with patch.object(session, 'check_convergence_signals') as mock_convergence:
            mock_convergence.return_value = {
                "signals": {
                    "explicit_completion": False,
                    "resource_exhaustion": False,
                    "repetitive_content": False,
                    "quality_degradation": True
                },
                "confidence": 0.4
            }

            assert session.should_auto_complete() is True

    def test_should_auto_complete_normal_conversation(self):
        """Test auto-completion with normal conversation state."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test normal conversation"
        )

        with patch.object(session, 'check_convergence_signals') as mock_convergence:
            mock_convergence.return_value = {
                "signals": {
                    "explicit_completion": False,
                    "resource_exhaustion": False,
                    "repetitive_content": False,
                    "quality_degradation": False
                },
                "confidence": 0.8
            }

            assert session.should_auto_complete() is False

    def test_should_auto_complete_error_handling(self):
        """Test error handling in should_auto_complete()."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test error handling"
        )

        # Mock convergence check to raise exception
        with patch.object(session, 'check_convergence_signals') as mock_convergence:
            mock_convergence.side_effect = Exception("Convergence analysis failed")

            # Should return False on error (don't auto-complete on errors)
            assert session.should_auto_complete() is False


class TestGetSummaryStats:
    """Test get_summary_stats() method implementation."""

    def test_get_summary_stats_empty_session(self):
        """Test summary stats for empty session."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Empty session test"
        )

        stats = session.get_summary_stats()

        assert isinstance(stats, dict)
        assert stats["total_turns"] == 0
        assert stats["total_cost"] == 0.0
        assert stats["avg_turn_length"] == 0.0
        assert stats["participants_activity"] == {"claude_code": 0, "codex_cli": 0}
        assert stats["duration_minutes"] >= 0.0
        assert 0.0 <= stats["convergence_confidence"] <= 1.0
        assert stats["topic"] == "Empty session test"
        assert stats["status"] == SessionStatus.ACTIVE.value

    def test_get_summary_stats_with_turns(self):
        """Test summary stats with multiple turns."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Session with turns"
        )

        # Add several turns
        turns_data = [
            ("claude_code", "codex_cli", "First message from Claude"),
            ("codex_cli", "claude_code", "Response from Codex"),
            ("claude_code", "codex_cli", "Another message from Claude with more content"),
            ("codex_cli", "claude_code", "Final response")
        ]

        for from_agent, to_agent, content in turns_data:
            turn = TurnMessage(
                session_id=session.session_id,
                from_agent=from_agent,
                to_agent=to_agent,
                role=MessageRole.ASSISTANT if from_agent == "claude_code" else MessageRole.USER,
                content=content
            )
            session.add_turn_message(turn)

        stats = session.get_summary_stats()

        assert stats["total_turns"] == 4
        assert stats["total_cost"] == session.total_cost_usd
        assert stats["avg_turn_length"] > 0  # Should be average of content lengths
        assert stats["participants_activity"]["claude_code"] == 2
        assert stats["participants_activity"]["codex_cli"] == 2
        assert stats["duration_minutes"] >= 0.0

    def test_get_summary_stats_convergence_integration(self):
        """Test integration with convergence analysis."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Convergence integration test"
        )

        # Mock convergence analysis
        with patch.object(session, 'check_convergence_signals') as mock_convergence:
            mock_convergence.return_value = {"confidence": 0.75}

            stats = session.get_summary_stats()
            assert stats["convergence_confidence"] == 0.75

        # Test error handling in convergence
        with patch.object(session, 'check_convergence_signals') as mock_convergence:
            mock_convergence.side_effect = Exception("Convergence error")

            stats = session.get_summary_stats()
            assert stats["convergence_confidence"] == 0.5  # Default fallback

    def test_get_summary_stats_duration_calculation(self):
        """Test duration calculation in summary stats."""
        # Create session with specific timestamps
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Duration test"
        )

        # Manually set timestamps to test duration calculation
        session.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        session.updated_at = datetime.now(timezone.utc)

        stats = session.get_summary_stats()

        # Duration should be approximately 10 minutes
        assert 9.5 <= stats["duration_minutes"] <= 10.5


class TestGetSessionStatus:
    """Test get_session_status() method implementation."""

    def test_get_session_status_basic_structure(self):
        """Test basic structure of session status."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Status structure test"
        )

        status = session.get_session_status()

        # Check required fields
        required_fields = [
            "status", "turn_progress", "budget_progress",
            "health_indicators", "next_actions", "last_activity", "active_since"
        ]

        for field in required_fields:
            assert field in status, f"Missing required field: {field}"

        # Check field types
        assert isinstance(status["status"], str)
        assert isinstance(status["turn_progress"], dict)
        assert isinstance(status["budget_progress"], dict)
        assert isinstance(status["health_indicators"], list)
        assert isinstance(status["next_actions"], list)
        assert isinstance(status["last_activity"], str)
        assert isinstance(status["active_since"], str)

    def test_get_session_status_progress_tracking(self):
        """Test progress tracking in session status."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Progress tracking test",
            max_turns=10,
            budget_usd=2.0
        )

        # Add some turns and cost
        session.current_turn = 3
        session.total_cost_usd = 0.5

        status = session.get_session_status()

        # Check turn progress
        assert status["turn_progress"]["current"] == 3
        assert status["turn_progress"]["max"] == 10

        # Check budget progress
        assert status["budget_progress"]["used"] == 0.5
        assert status["budget_progress"]["total"] == 2.0

    def test_get_session_status_health_indicators(self):
        """Test health indicators in session status."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Health indicators test",
            max_turns=10,
            budget_usd=1.0
        )

        # Test healthy session (low usage)
        session.current_turn = 2
        session.total_cost_usd = 0.2

        status = session.get_session_status()
        health_indicators = status["health_indicators"]

        assert any("healthy" in indicator.lower() for indicator in health_indicators)

        # Test session approaching limits
        session.current_turn = 9  # 90% of max turns
        session.total_cost_usd = 0.95  # 95% of budget

        status = session.get_session_status()
        health_indicators = status["health_indicators"]

        assert any("high" in indicator.lower() or "approaching" in indicator.lower()
                  for indicator in health_indicators)

    def test_get_session_status_next_actions(self):
        """Test next actions recommendations in session status."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Next actions test"
        )

        # Test active session
        status = session.get_session_status()
        next_actions = status["next_actions"]

        assert len(next_actions) > 0
        assert any("continue" in action.lower() or "monitor" in action.lower()
                  for action in next_actions)

        # Test completed session
        session.status = SessionStatus.COMPLETED
        status = session.get_session_status()
        next_actions = status["next_actions"]

        assert any("completed" in action.lower() for action in next_actions)

    def test_get_session_status_convergence_integration(self):
        """Test integration with convergence analysis in status."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Convergence status test"
        )

        # Mock convergence to suggest completion
        with patch.object(session, 'check_convergence_signals') as mock_convergence:
            mock_convergence.return_value = {"should_continue": False}

            status = session.get_session_status()
            next_actions = status["next_actions"]

            assert any("completion" in action.lower() or "ready" in action.lower()
                      for action in next_actions)

        # Mock convergence error
        with patch.object(session, 'check_convergence_signals') as mock_convergence:
            mock_convergence.side_effect = Exception("Convergence error")

            status = session.get_session_status()
            next_actions = status["next_actions"]

            assert any("check" in action.lower() for action in next_actions)

    def test_get_session_status_timestamp_formats(self):
        """Test timestamp formatting in session status."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Timestamp format test"
        )

        status = session.get_session_status()

        # Check that timestamps are valid ISO format
        last_activity = status["last_activity"]
        active_since = status["active_since"]

        # Should be able to parse as ISO datetime
        datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
        datetime.fromisoformat(active_since.replace('Z', '+00:00'))


class TestMissingMethodsIntegration:
    """Test integration between missing methods and existing functionality."""

    def test_methods_work_together(self):
        """Test that all missing methods work together correctly."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Integration test"
        )

        # Add some conversation content
        for i in range(3):
            turn = TurnMessage(
                session_id=session.session_id,
                from_agent="claude_code" if i % 2 == 0 else "codex_cli",
                to_agent="codex_cli" if i % 2 == 0 else "claude_code",
                role=MessageRole.ASSISTANT if i % 2 == 0 else MessageRole.USER,
                content=f"Integration test message {i+1}"
            )
            session.add_turn_message(turn)

        # All methods should work without errors
        auto_complete = session.should_auto_complete()
        stats = session.get_summary_stats()
        status = session.get_session_status()

        # Basic sanity checks
        assert isinstance(auto_complete, bool)
        assert isinstance(stats, dict) and stats["total_turns"] == 3
        assert isinstance(status, dict) and status["turn_progress"]["current"] > 0

        # Check consistency between methods
        assert stats["total_turns"] == status["turn_progress"]["current"]
        assert stats["status"] == status["status"]

    def test_methods_with_existing_convergence(self):
        """Test integration with existing convergence analysis."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Existing convergence test"
        )

        # Use actual convergence analysis (not mocked)
        auto_complete = session.should_auto_complete()
        stats = session.get_summary_stats()

        # Should work with real convergence analysis
        assert isinstance(auto_complete, bool)
        assert isinstance(stats["convergence_confidence"], float)
        assert 0.0 <= stats["convergence_confidence"] <= 1.0