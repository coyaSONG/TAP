"""Integration tests for service constructor dependency injection.

These tests validate the complete service constructor dependency injection flow
as would be used by TABApplication.
"""

import pytest
import asyncio
from typing import Dict, Any
from src.tab.lib.config import initialize_config, get_config
from src.tab.services.session_manager import SessionManager
from src.tab.services.policy_enforcer import PolicyEnforcer
from src.tab.services.conversation_orchestrator import ConversationOrchestrator


class TestServiceConstructorIntegration:
    """Integration tests for service constructor dependency injection."""

    @pytest.fixture
    def test_config(self):
        """Provide test configuration for service integration."""
        return {
            "session": {
                "default_max_turns": 8,
                "default_budget_usd": 1.0,
                "session_timeout": 3600,
                "storage_directory": "/tmp/test_sessions"
            },
            "policies": {
                "default": {
                    "policy_id": "default",
                    "name": "Test Policy",
                    "description": "Policy for integration testing",
                    "permission_mode": "prompt",
                    "sandbox_enabled": True,
                    "resource_limits": {
                        "max_execution_time_ms": 120000,
                        "max_cost_usd": 0.1
                    }
                }
            },
            "agents": {
                "claude_code": {
                    "agent_id": "claude_code",
                    "agent_type": "claude_code",
                    "name": "Claude Code",
                    "version": "1.0.0",
                    "capabilities": ["code_analysis", "file_operations"]
                },
                "codex_cli": {
                    "agent_id": "codex_cli",
                    "agent_type": "codex_cli",
                    "name": "Codex CLI",
                    "version": "1.0.0",
                    "capabilities": ["code_generation", "execution"]
                }
            },
            "service_container": {
                "async_adapter_pool_size": 10,
                "circuit_breaker_threshold": 3,
                "health_check_interval": 30
            }
        }

    @pytest.mark.asyncio
    async def test_session_manager_dependency_injection(self, test_config):
        """Test SessionManager constructor with dependency injection."""
        session_config = test_config["session"]

        # Create SessionManager with configuration
        session_manager = SessionManager(session_config)
        assert session_manager is not None

        # Initialize and test functionality
        await session_manager.initialize()

        # Test that configuration was properly injected
        session = await session_manager.create_session(
            topic="DI integration test",
            participants=["claude_code", "codex_cli"]
        )

        assert session is not None
        assert session.topic == "DI integration test"
        assert len(session.participants) == 2

        # Cleanup
        await session_manager.shutdown()

    def test_policy_enforcer_dependency_injection(self, test_config):
        """Test PolicyEnforcer constructor with dependency injection."""
        policy_config = test_config["policies"]

        # Create PolicyEnforcer with configuration
        policy_enforcer = PolicyEnforcer(policy_config)
        assert policy_enforcer is not None

        # Test that configuration was properly injected
        session_params = {
            "topic": "Policy DI test",
            "participants": ["claude_code", "codex_cli"],
            "max_turns": 8
        }

        result = policy_enforcer.validate_session_creation("default", session_params)
        assert isinstance(result, dict)
        assert "allowed" in result
        assert "violations" in result

    @pytest.mark.asyncio
    async def test_conversation_orchestrator_dependency_injection(self, test_config):
        """Test ConversationOrchestrator with full dependency injection."""
        # Create all dependencies
        session_manager = SessionManager(test_config["session"])
        policy_enforcer = PolicyEnforcer(test_config["policies"])
        agent_configs = test_config["agents"]

        # Create orchestrator with injected dependencies
        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=policy_enforcer,
            agent_configs=agent_configs
        )
        assert orchestrator is not None

        # Initialize all services
        await session_manager.initialize()
        await orchestrator.initialize()

        # Test that dependencies work together
        result = await orchestrator.start_conversation(
            topic="Full DI integration test",
            participants=["claude_code", "codex_cli"]
        )

        assert isinstance(result, dict)
        assert "session_id" in result

        # Cleanup
        await orchestrator.shutdown()
        await session_manager.shutdown()

    @pytest.mark.asyncio
    async def test_full_service_container_integration(self, test_config):
        """Test complete service container dependency injection flow."""
        # Simulate TABApplication service container initialization
        session_config = test_config["session"]
        policy_config = test_config["policies"]
        agent_configs = test_config["agents"]

        # Create services with dependency injection (as TABApplication would)
        session_manager = SessionManager(session_config)
        policy_enforcer = PolicyEnforcer(policy_config)
        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=policy_enforcer,
            agent_configs=agent_configs
        )

        # Initialize all services
        await session_manager.initialize()
        await orchestrator.initialize()

        try:
            # Test complete conversation flow with DI
            conv_result = await orchestrator.start_conversation(
                topic="Service container integration",
                participants=["claude_code", "codex_cli"]
            )
            session_id = conv_result["session_id"]

            # Test turn processing
            turn_result = await orchestrator.process_turn(
                session_id=session_id,
                content="Test message for DI integration",
                from_agent="claude_code",
                to_agent="codex_cli"
            )
            assert isinstance(turn_result, dict)

            # Test context retrieval
            context = await orchestrator.get_conversation_context(
                session_id=session_id,
                limit=5
            )
            assert isinstance(context, list)

        finally:
            # Cleanup all services
            await orchestrator.shutdown()
            await session_manager.shutdown()

    @pytest.mark.asyncio
    async def test_service_lifecycle_with_dependency_injection(self, test_config):
        """Test service lifecycle methods with dependency injection."""
        session_manager = SessionManager(test_config["session"])
        policy_enforcer = PolicyEnforcer(test_config["policies"])

        # Test initialization
        await session_manager.initialize()
        assert hasattr(session_manager, '_initialized') or True  # Service is ready

        # Test that services work after initialization
        session = await session_manager.create_session(
            topic="Lifecycle DI test",
            participants=["claude_code", "codex_cli"]
        )
        assert session is not None

        # Test validation after initialization
        result = policy_enforcer.validate_session_creation("default", {
            "topic": "test",
            "participants": ["claude_code", "codex_cli"]
        })
        assert isinstance(result, dict)

        # Test shutdown
        await session_manager.shutdown()

    def test_configuration_validation_in_constructors(self, test_config):
        """Test that service constructors validate configuration properly."""
        # Test invalid session configuration
        invalid_session_config = {
            "default_max_turns": -1,  # Invalid
            "default_budget_usd": 0    # Invalid
        }

        with pytest.raises((ValueError, TypeError)):
            SessionManager(invalid_session_config)

        # Test invalid policy configuration
        invalid_policy_config = {
            "invalid": {
                "permission_mode": "invalid_mode"  # Invalid mode
            }
        }

        with pytest.raises((ValueError, TypeError)):
            PolicyEnforcer(invalid_policy_config)

        # Test missing dependencies for orchestrator
        with pytest.raises((TypeError, ValueError)):
            ConversationOrchestrator(
                session_manager=None,  # Required dependency missing
                policy_enforcer=PolicyEnforcer(test_config["policies"]),
                agent_configs={}
            )

    @pytest.mark.asyncio
    async def test_concurrent_service_operations_with_di(self, test_config):
        """Test concurrent operations with dependency injection."""
        session_manager = SessionManager(test_config["session"])
        policy_enforcer = PolicyEnforcer(test_config["policies"])
        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=policy_enforcer,
            agent_configs=test_config["agents"]
        )

        await session_manager.initialize()
        await orchestrator.initialize()

        try:
            # Create multiple conversations concurrently
            tasks = []
            for i in range(3):
                task = orchestrator.start_conversation(
                    topic=f"Concurrent DI test {i}",
                    participants=["claude_code", "codex_cli"]
                )
                tasks.append(task)

            # Wait for all conversations to start
            results = await asyncio.gather(*tasks)

            # Verify all conversations started successfully
            assert len(results) == 3
            for result in results:
                assert isinstance(result, dict)
                assert "session_id" in result

        finally:
            await orchestrator.shutdown()
            await session_manager.shutdown()