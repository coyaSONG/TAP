"""Contract tests for PolicyEnforcer constructor dependency injection.

These tests validate that PolicyEnforcer properly accepts configuration objects
as expected by TABApplication dependency injection container.
"""

import pytest
from typing import Dict, Any
from src.tab.services.policy_enforcer import PolicyEnforcer
from src.tab.models.conversation_session import ConversationSession
from src.tab.models.turn_message import TurnMessage, MessageRole


class TestPolicyEnforcerContract:
    """Contract tests for PolicyEnforcer enhanced constructor."""

    def test_policy_enforcer_accepts_config_parameter(self):
        """Test that PolicyEnforcer constructor accepts config dictionary."""
        config = {
            "default": {
                "policy_id": "default",
                "name": "Default Policy",
                "description": "Default security policy",
                "permission_mode": "prompt",
                "sandbox_enabled": True,
                "resource_limits": {
                    "max_execution_time_ms": 120000,
                    "max_cost_usd": 0.1
                }
            }
        }

        # This should work with enhanced constructor
        policy_enforcer = PolicyEnforcer(config)
        assert policy_enforcer is not None

    def test_policy_enforcer_config_validation(self):
        """Test that PolicyEnforcer validates configuration parameters."""
        invalid_config = {
            "invalid_policy": {
                "permission_mode": "invalid_mode"  # Invalid permission mode
            }
        }

        # Should raise validation error for invalid config
        with pytest.raises((ValueError, TypeError)):
            PolicyEnforcer(invalid_config)

    def test_policy_enforcer_validate_session_creation(self):
        """Test policy validation for session creation."""
        config = {
            "default": {
                "policy_id": "default",
                "name": "Default Policy",
                "permission_mode": "prompt",
                "sandbox_enabled": True
            }
        }
        policy_enforcer = PolicyEnforcer(config)

        session_params = {
            "topic": "Test policy validation",
            "participants": ["claude_code", "codex_cli"],
            "max_turns": 8,
            "budget_usd": 1.0
        }

        # Should return validation result
        result = policy_enforcer.validate_session_creation("default", session_params)
        assert isinstance(result, dict)
        assert "allowed" in result
        assert "violations" in result

    def test_policy_enforcer_validate_turn_addition(self):
        """Test policy validation for turn addition."""
        config = {
            "default": {
                "policy_id": "default",
                "name": "Default Policy",
                "permission_mode": "prompt",
                "sandbox_enabled": True
            }
        }
        policy_enforcer = PolicyEnforcer(config)

        # Create test session
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Test policy validation"
        )

        # Create test turn
        turn = TurnMessage(
            session_id=session.session_id,
            from_agent="claude_code",
            to_agent="codex_cli",
            role=MessageRole.ASSISTANT,
            content="Test message for policy validation"
        )

        # Should return validation result
        result = policy_enforcer.validate_turn_addition("default", session, turn)
        assert isinstance(result, dict)
        assert "allowed" in result
        assert "violations" in result

    def test_policy_enforcer_enforce_turn_message_policy(self):
        """Test turn message policy enforcement."""
        config = {
            "default": {
                "policy_id": "default",
                "name": "Default Policy",
                "permission_mode": "prompt",
                "disallowed_tools": ["dangerous_command"]
            }
        }
        policy_enforcer = PolicyEnforcer(config)

        # Create test turn with potentially dangerous content
        turn = TurnMessage(
            session_id="test-session",
            from_agent="claude_code",
            to_agent="codex_cli",
            role=MessageRole.ASSISTANT,
            content="Execute dangerous_command with parameters"
        )

        # Should detect policy violation
        result = policy_enforcer.enforce_turn_message_policy("default", turn)
        assert isinstance(result, dict)
        assert "allowed" in result
        assert "violations" in result

    def test_policy_enforcer_interface_compliance(self):
        """Test that PolicyEnforcer implements expected interface methods."""
        config = {"default": {"policy_id": "default"}}
        policy_enforcer = PolicyEnforcer(config)

        # Check required methods exist
        assert hasattr(policy_enforcer, 'validate_session_creation')
        assert hasattr(policy_enforcer, 'validate_turn_addition')
        assert hasattr(policy_enforcer, 'enforce_turn_message_policy')

        # Check method signatures
        import inspect
        sig_session = inspect.signature(policy_enforcer.validate_session_creation)
        assert len(sig_session.parameters) == 3  # self, policy_id, session_params

        sig_turn = inspect.signature(policy_enforcer.validate_turn_addition)
        assert len(sig_turn.parameters) == 4  # self, policy_id, session, turn