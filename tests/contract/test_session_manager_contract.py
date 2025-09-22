"""Contract tests for SessionManager constructor dependency injection.

These tests validate that SessionManager properly accepts configuration objects
as expected by TABApplication dependency injection container.
"""

import pytest
from typing import Dict, Any
from src.tab.services.session_manager import SessionManager
from src.tab.models.conversation_session import ConversationSession


class TestSessionManagerContract:
    """Contract tests for SessionManager enhanced constructor."""

    def test_session_manager_accepts_config_parameter(self):
        """Test that SessionManager constructor accepts config dictionary."""
        config = {
            "default_max_turns": 8,
            "default_budget_usd": 1.0,
            "session_timeout": 3600,
            "turn_timeout": 120,
            "max_active_sessions": 50,
            "enable_persistence": True,
            "storage_directory": "~/.tab/sessions"
        }

        # This should work with enhanced constructor
        session_manager = SessionManager(config)
        assert session_manager is not None

    def test_session_manager_config_validation(self):
        """Test that SessionManager validates configuration parameters."""
        invalid_config = {
            "default_max_turns": -1,  # Invalid negative value
            "default_budget_usd": 0,   # Invalid zero value
        }

        # Should raise validation error for invalid config
        with pytest.raises((ValueError, TypeError)):
            SessionManager(invalid_config)

    @pytest.mark.asyncio
    async def test_session_manager_create_session_with_validation(self):
        """Test session creation with enhanced parameter validation."""
        config = {"default_max_turns": 8, "default_budget_usd": 1.0}
        session_manager = SessionManager(config)

        # Initialize session manager
        await session_manager.initialize()

        # Test session creation with validation
        session = await session_manager.create_session(
            topic="Test dependency injection",
            participants=["claude_code", "codex_cli"],
            policy_id="default",
            max_turns=8,
            budget_usd=1.0
        )

        assert isinstance(session, ConversationSession)
        assert session.topic == "Test dependency injection"
        assert len(session.participants) == 2

        # Cleanup
        await session_manager.shutdown()

    @pytest.mark.asyncio
    async def test_session_manager_get_session_contract(self):
        """Test session retrieval contract."""
        config = {"default_max_turns": 8, "default_budget_usd": 1.0}
        session_manager = SessionManager(config)

        await session_manager.initialize()

        # Test retrieving non-existent session
        session = await session_manager.get_session("non-existent-session-id")
        assert session is None

        # Cleanup
        await session_manager.shutdown()

    def test_session_manager_interface_compliance(self):
        """Test that SessionManager implements expected interface methods."""
        config = {"default_max_turns": 8}
        session_manager = SessionManager(config)

        # Check required async methods exist
        assert hasattr(session_manager, 'create_session')
        assert hasattr(session_manager, 'get_session')
        assert hasattr(session_manager, 'initialize')
        assert hasattr(session_manager, 'shutdown')

        # Check methods are coroutines
        import inspect
        assert inspect.iscoroutinefunction(session_manager.create_session)
        assert inspect.iscoroutinefunction(session_manager.get_session)
        assert inspect.iscoroutinefunction(session_manager.initialize)