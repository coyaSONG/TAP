"""Unit tests for service interface implementations.

Tests the service interface abstractions to ensure they work correctly
and prevent regressions in the dependency injection pattern.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any

from src.tab.services.interfaces.session_service import IConversationSessionService
from src.tab.services.interfaces.policy_validator import IPolicyValidator
from src.tab.services.interfaces.service_lifecycle import IServiceLifecycle


class MockSessionService(IConversationSessionService):
    """Mock implementation of session service for testing."""

    async def create_session(self, topic: str, participants: list, policy_id: str = "default", max_turns: int = 8, **kwargs):
        from src.tab.models.conversation_session import ConversationSession
        return ConversationSession(participants=participants, topic=topic)

    async def get_session(self, session_id: str):
        if session_id == "valid-session":
            from src.tab.models.conversation_session import ConversationSession
            return ConversationSession(participants=["agent1", "agent2"], topic="test")
        return None

    async def add_turn_to_session(self, session_id: str, turn):
        return session_id == "valid-session"

    async def get_session_context(self, session_id: str, agent_filter: str = None, limit: int = 5):
        if session_id == "valid-session":
            return [{"role": "assistant", "content": "test", "from_agent": "agent1"}]
        return []


class MockPolicyValidator(IPolicyValidator):
    """Mock implementation of policy validator for testing."""

    async def validate_session_creation(self, policy_id: str, session_params: Dict[str, Any]):
        return {"allowed": policy_id != "strict", "violations": [] if policy_id != "strict" else ["policy violation"]}

    async def validate_turn_addition(self, policy_id: str, session, turn):
        return {"allowed": True, "violations": []}


class MockServiceLifecycle(IServiceLifecycle):
    """Mock implementation of service lifecycle for testing."""

    def __init__(self):
        self.initialized = False
        self.started = False
        self.stopped = False

    async def initialize(self):
        self.initialized = True

    async def start(self):
        if not self.initialized:
            raise RuntimeError("Service not initialized")
        self.started = True

    async def stop(self):
        self.stopped = True

    async def health_check(self):
        return {"healthy": self.started and not self.stopped, "initialized": self.initialized}


class TestServiceInterfaces:
    """Test service interface implementations."""

    @pytest.mark.asyncio
    async def test_session_service_interface_compliance(self):
        """Test that session service interface works correctly."""
        service = MockSessionService()

        # Test session creation
        session = await service.create_session(
            topic="Test session",
            participants=["agent1", "agent2"],
            max_turns=10
        )
        assert session is not None
        assert session.topic == "Test session"
        assert len(session.participants) == 2

        # Test session retrieval
        found_session = await service.get_session("valid-session")
        assert found_session is not None

        not_found = await service.get_session("invalid-session")
        assert not_found is None

        # Test context retrieval
        context = await service.get_session_context("valid-session", limit=5)
        assert isinstance(context, list)
        assert len(context) >= 0

    @pytest.mark.asyncio
    async def test_policy_validator_interface_compliance(self):
        """Test that policy validator interface works correctly."""
        validator = MockPolicyValidator()

        # Test session validation
        result = await validator.validate_session_creation("default", {
            "topic": "test",
            "participants": ["agent1", "agent2"]
        })
        assert isinstance(result, dict)
        assert "allowed" in result
        assert result["allowed"] is True

        # Test strict policy
        strict_result = await validator.validate_session_creation("strict", {})
        assert strict_result["allowed"] is False
        assert len(strict_result["violations"]) > 0

        # Test turn validation
        from src.tab.models.conversation_session import ConversationSession
        session = ConversationSession(participants=["agent1", "agent2"], topic="test")

        from src.tab.models.turn_message import TurnMessage, MessageRole
        turn = TurnMessage(
            session_id=session.session_id,
            from_agent="agent1",
            to_agent="agent2",
            role=MessageRole.ASSISTANT,
            content="test message"
        )

        turn_result = await validator.validate_turn_addition("default", session, turn)
        assert isinstance(turn_result, dict)
        assert "allowed" in turn_result

    @pytest.mark.asyncio
    async def test_service_lifecycle_interface_compliance(self):
        """Test that service lifecycle interface works correctly."""
        service = MockServiceLifecycle()

        # Test initialization
        assert not service.initialized
        await service.initialize()
        assert service.initialized

        # Test startup
        assert not service.started
        await service.start()
        assert service.started

        # Test health check
        health = await service.health_check()
        assert isinstance(health, dict)
        assert health["healthy"] is True
        assert health["initialized"] is True

        # Test stop
        assert not service.stopped
        await service.stop()
        assert service.stopped

        # Health check after stop
        health_stopped = await service.health_check()
        assert health_stopped["healthy"] is False

    @pytest.mark.asyncio
    async def test_service_lifecycle_error_handling(self):
        """Test error handling in service lifecycle."""
        service = MockServiceLifecycle()

        # Starting without initialization should fail
        with pytest.raises(RuntimeError, match="Service not initialized"):
            await service.start()

        # Initialize and then start should work
        await service.initialize()
        await service.start()
        assert service.started

    @pytest.mark.asyncio
    async def test_interface_parameter_validation(self):
        """Test that interface parameters are properly validated."""
        service = MockSessionService()

        # Test with invalid parameters (should be caught by pydantic validation)
        with pytest.raises(Exception):  # Pydantic validation error
            await service.create_session(
                topic="",  # Empty topic should fail
                participants=["agent1", "agent2"]
            )

        with pytest.raises(Exception):  # Pydantic validation error
            await service.create_session(
                topic="valid topic",
                participants=["single"]  # Need at least 2 participants
            )

    @pytest.mark.asyncio
    async def test_async_interface_compliance(self):
        """Test that all interface methods are properly async."""
        import inspect

        # Check IConversationSessionService methods
        for method_name in ['create_session', 'get_session', 'add_turn_to_session', 'get_session_context']:
            method = getattr(IConversationSessionService, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} should be async"

        # Check IPolicyValidator methods
        for method_name in ['validate_session_creation', 'validate_turn_addition']:
            method = getattr(IPolicyValidator, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} should be async"

        # Check IServiceLifecycle methods
        for method_name in ['initialize', 'start', 'stop', 'health_check']:
            method = getattr(IServiceLifecycle, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} should be async"

    @pytest.mark.asyncio
    async def test_concurrent_interface_operations(self):
        """Test that interface implementations handle concurrent operations."""
        service = MockSessionService()
        validator = MockPolicyValidator()

        # Run multiple operations concurrently
        tasks = [
            service.create_session(f"topic_{i}", [f"agent1_{i}", f"agent2_{i}"])
            for i in range(5)
        ]

        sessions = await asyncio.gather(*tasks)
        assert len(sessions) == 5
        assert all(session is not None for session in sessions)

        # Concurrent validation operations
        validation_tasks = [
            validator.validate_session_creation("default", {"topic": f"test_{i}"})
            for i in range(3)
        ]

        results = await asyncio.gather(*validation_tasks)
        assert len(results) == 3
        assert all(result["allowed"] for result in results)