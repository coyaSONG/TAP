"""
Unit tests for policy validation logic.

Tests the PolicyEnforcer service to ensure proper policy enforcement,
validation rules, and permission boundary checks.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import Dict, Any

from tab.services.policy_enforcer import PolicyEnforcer
from tab.models.policy_configuration import PolicyConfiguration
from tab.models.turn_message import TurnMessage
from tab.models.agent_adapter import AgentAdapter


@pytest.fixture
def sample_policy_config():
    """Sample policy configuration for testing."""
    return {
        "policy_id": "test_policy",
        "name": "Test Policy",
        "description": "Test policy for validation",
        "permission_mode": "prompt",
        "allowed_tools": ["read", "write", "search"],
        "disallowed_tools": ["delete", "system"],
        "resource_limits": {
            "max_execution_time_ms": 30000,
            "max_cost_usd": 0.1,
            "max_memory_mb": 256
        },
        "file_access_rules": [
            "allow:/workspace/*",
            "deny:/system/*",
            "deny:/etc/*"
        ],
        "network_access_rules": [
            "allow:localhost",
            "deny:*"
        ],
        "sandbox_config": {
            "enabled": True,
            "capability_drop": ["ALL"],
            "read_only": True
        },
        "approval_required": ["write", "network"]
    }


@pytest.fixture
def policy_enforcer(sample_policy_config):
    """PolicyEnforcer instance for testing."""
    policies = {"test_policy": sample_policy_config}
    return PolicyEnforcer(policies)


@pytest.fixture
def sample_turn_message():
    """Sample turn message for testing."""
    return TurnMessage(
        turn_id="turn_001",
        session_id="session_001",
        from_agent="claude_code",
        to_agent="codex_cli",
        role="user",
        content="Please analyze this code",
        timestamp=datetime.now(),
        policy_constraints={"allowed_tools": ["read", "analyze"]},
        metadata={"cost_usd": 0.01}
    )


@pytest.fixture
def sample_agent_adapter():
    """Sample agent adapter for testing."""
    return AgentAdapter(
        agent_id="claude_code",
        agent_type="claude_code",
        name="Claude Code",
        version="1.0.0",
        capabilities=["read", "write", "analyze"],
        connection_config={"type": "cli"},
        status="available",
        last_health_check=datetime.now(),
        session_manager={"type": "local"},
        execution_limits={"max_time_ms": 60000}
    )


class TestPolicyValidation:
    """Test policy validation functionality."""

    @pytest.mark.asyncio
    async def test_validate_policy_success(self, policy_enforcer, sample_policy_config):
        """Test successful policy validation."""
        result = await policy_enforcer.validate_policy("test_policy")

        assert result["valid"] is True
        assert "errors" not in result or len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_validate_nonexistent_policy(self, policy_enforcer):
        """Test validation of nonexistent policy."""
        result = await policy_enforcer.validate_policy("nonexistent_policy")

        assert result["valid"] is False
        assert "Policy 'nonexistent_policy' not found" in result["errors"]

    @pytest.mark.asyncio
    async def test_validate_policy_with_invalid_permission_mode(self, policy_enforcer):
        """Test validation with invalid permission mode."""
        # Modify policy to have invalid permission mode
        policy_enforcer.policies["test_policy"]["permission_mode"] = "invalid_mode"

        result = await policy_enforcer.validate_policy("test_policy")

        assert result["valid"] is False
        assert any("permission_mode" in error for error in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_policy_with_overlapping_tools(self, policy_enforcer):
        """Test validation with overlapping allowed/disallowed tools."""
        # Add overlapping tools
        policy_enforcer.policies["test_policy"]["allowed_tools"] = ["read", "write", "delete"]
        policy_enforcer.policies["test_policy"]["disallowed_tools"] = ["delete", "system"]

        result = await policy_enforcer.validate_policy("test_policy")

        assert result["valid"] is False
        assert any("overlap" in error.lower() for error in result["errors"])


class TestPermissionEnforcement:
    """Test permission enforcement functionality."""

    @pytest.mark.asyncio
    async def test_check_tool_permission_allowed(self, policy_enforcer):
        """Test checking permission for allowed tool."""
        result = await policy_enforcer.check_tool_permission(
            policy_id="test_policy",
            tool_name="read"
        )

        assert result["allowed"] is True
        assert result["reason"] == "Tool 'read' is explicitly allowed"

    @pytest.mark.asyncio
    async def test_check_tool_permission_disallowed(self, policy_enforcer):
        """Test checking permission for disallowed tool."""
        result = await policy_enforcer.check_tool_permission(
            policy_id="test_policy",
            tool_name="delete"
        )

        assert result["allowed"] is False
        assert "disallowed" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_tool_permission_unlisted(self, policy_enforcer):
        """Test checking permission for unlisted tool."""
        result = await policy_enforcer.check_tool_permission(
            policy_id="test_policy",
            tool_name="unknown_tool"
        )

        # Should follow policy's permission_mode (prompt in this case)
        assert result["allowed"] is False  # prompt mode requires explicit approval
        assert "prompt" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_file_access_allowed(self, policy_enforcer):
        """Test checking file access for allowed path."""
        result = await policy_enforcer.check_file_access(
            policy_id="test_policy",
            file_path="/workspace/file.txt",
            access_type="read"
        )

        assert result["allowed"] is True
        assert "workspace" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_file_access_denied(self, policy_enforcer):
        """Test checking file access for denied path."""
        result = await policy_enforcer.check_file_access(
            policy_id="test_policy",
            file_path="/system/config",
            access_type="read"
        )

        assert result["allowed"] is False
        assert "denied" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_resource_limits(self, policy_enforcer):
        """Test resource limit validation."""
        result = await policy_enforcer.check_resource_limits(
            policy_id="test_policy",
            requested_resources={
                "execution_time_ms": 20000,
                "cost_usd": 0.05,
                "memory_mb": 128
            }
        )

        assert result["allowed"] is True
        assert "within limits" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_resource_limits_exceeded(self, policy_enforcer):
        """Test resource limit validation when limits exceeded."""
        result = await policy_enforcer.check_resource_limits(
            policy_id="test_policy",
            requested_resources={
                "execution_time_ms": 60000,  # Exceeds 30000 limit
                "cost_usd": 0.05,
                "memory_mb": 128
            }
        )

        assert result["allowed"] is False
        assert "exceeds limit" in result["reason"].lower()


class TestTurnMessageValidation:
    """Test turn message validation against policies."""

    @pytest.mark.asyncio
    async def test_validate_turn_message_success(self, policy_enforcer, sample_turn_message):
        """Test successful turn message validation."""
        result = await policy_enforcer.validate_turn_message(
            message=sample_turn_message,
            policy_id="test_policy"
        )

        assert result["valid"] is True
        assert "violations" not in result or len(result["violations"]) == 0

    @pytest.mark.asyncio
    async def test_validate_turn_message_with_violations(self, policy_enforcer, sample_turn_message):
        """Test turn message validation with policy violations."""
        # Modify message to include disallowed tool
        sample_turn_message.policy_constraints["tools_used"] = ["delete"]

        result = await policy_enforcer.validate_turn_message(
            message=sample_turn_message,
            policy_id="test_policy"
        )

        assert result["valid"] is False
        assert len(result["violations"]) > 0
        assert any("delete" in violation for violation in result["violations"])

    @pytest.mark.asyncio
    async def test_validate_turn_message_cost_limit(self, policy_enforcer, sample_turn_message):
        """Test turn message validation for cost limits."""
        # Set cost exceeding policy limit
        sample_turn_message.metadata["cost_usd"] = 0.2  # Exceeds 0.1 limit

        result = await policy_enforcer.validate_turn_message(
            message=sample_turn_message,
            policy_id="test_policy"
        )

        assert result["valid"] is False
        assert any("cost" in violation.lower() for violation in result["violations"])


class TestAgentPermissions:
    """Test agent-specific permission enforcement."""

    @pytest.mark.asyncio
    async def test_validate_agent_capabilities(self, policy_enforcer, sample_agent_adapter):
        """Test agent capability validation against policy."""
        result = await policy_enforcer.validate_agent_capabilities(
            agent=sample_agent_adapter,
            policy_id="test_policy"
        )

        assert result["valid"] is True
        assert "violations" not in result or len(result["violations"]) == 0

    @pytest.mark.asyncio
    async def test_validate_agent_with_disallowed_capability(self, policy_enforcer, sample_agent_adapter):
        """Test agent validation with disallowed capability."""
        # Add disallowed capability to agent
        sample_agent_adapter.capabilities.append("delete")

        result = await policy_enforcer.validate_agent_capabilities(
            agent=sample_agent_adapter,
            policy_id="test_policy"
        )

        assert result["valid"] is False
        assert any("delete" in violation for violation in result["violations"])

    @pytest.mark.asyncio
    async def test_get_agent_permissions(self, policy_enforcer, sample_agent_adapter):
        """Test getting effective permissions for agent."""
        permissions = await policy_enforcer.get_agent_permissions(
            agent_id="claude_code",
            policy_id="test_policy"
        )

        assert "allowed_tools" in permissions
        assert "disallowed_tools" in permissions
        assert "file_access_rules" in permissions
        assert "resource_limits" in permissions


class TestPolicyListing:
    """Test policy listing and retrieval functionality."""

    @pytest.mark.asyncio
    async def test_list_policies(self, policy_enforcer):
        """Test listing all available policies."""
        policies = await policy_enforcer.list_policies()

        assert len(policies) == 1
        assert policies[0]["policy_id"] == "test_policy"
        assert policies[0]["name"] == "Test Policy"

    @pytest.mark.asyncio
    async def test_get_policy(self, policy_enforcer):
        """Test getting specific policy configuration."""
        policy = await policy_enforcer.get_policy(policy_id="test_policy")

        assert policy["policy_id"] == "test_policy"
        assert policy["name"] == "Test Policy"
        assert policy["permission_mode"] == "prompt"

    @pytest.mark.asyncio
    async def test_get_nonexistent_policy(self, policy_enforcer):
        """Test getting nonexistent policy."""
        with pytest.raises(KeyError):
            await policy_enforcer.get_policy(policy_id="nonexistent")


class TestSandboxValidation:
    """Test sandbox configuration validation."""

    @pytest.mark.asyncio
    async def test_validate_sandbox_config(self, policy_enforcer):
        """Test sandbox configuration validation."""
        result = await policy_enforcer.validate_sandbox_config(policy_id="test_policy")

        assert result["valid"] is True
        assert result["sandbox_enabled"] is True

    @pytest.mark.asyncio
    async def test_get_sandbox_requirements(self, policy_enforcer):
        """Test getting sandbox requirements for policy."""
        requirements = await policy_enforcer.get_sandbox_requirements(policy_id="test_policy")

        assert requirements["enabled"] is True
        assert "ALL" in requirements["capability_drop"]
        assert requirements["read_only"] is True


class TestPolicyEnforcement:
    """Test comprehensive policy enforcement scenarios."""

    @pytest.mark.asyncio
    async def test_enforce_policy_comprehensive(self, policy_enforcer, sample_turn_message, sample_agent_adapter):
        """Test comprehensive policy enforcement."""
        result = await policy_enforcer.enforce_policy(
            message=sample_turn_message,
            agent=sample_agent_adapter,
            policy_id="test_policy",
            requested_action={
                "tool": "read",
                "file_path": "/workspace/file.txt",
                "resources": {"execution_time_ms": 15000, "cost_usd": 0.02}
            }
        )

        assert result["allowed"] is True
        assert result["enforcement_result"]["valid"] is True

    @pytest.mark.asyncio
    async def test_enforce_policy_with_violations(self, policy_enforcer, sample_turn_message, sample_agent_adapter):
        """Test policy enforcement with multiple violations."""
        result = await policy_enforcer.enforce_policy(
            message=sample_turn_message,
            agent=sample_agent_adapter,
            policy_id="test_policy",
            requested_action={
                "tool": "delete",  # Disallowed
                "file_path": "/system/config",  # Denied path
                "resources": {"execution_time_ms": 60000, "cost_usd": 0.2}  # Exceeds limits
            }
        )

        assert result["allowed"] is False
        assert len(result["enforcement_result"]["violations"]) >= 3

    @pytest.mark.asyncio
    async def test_enforce_policy_approval_required(self, policy_enforcer, sample_turn_message, sample_agent_adapter):
        """Test policy enforcement for actions requiring approval."""
        result = await policy_enforcer.enforce_policy(
            message=sample_turn_message,
            agent=sample_agent_adapter,
            policy_id="test_policy",
            requested_action={
                "tool": "write",  # Requires approval
                "file_path": "/workspace/output.txt",
                "resources": {"execution_time_ms": 15000, "cost_usd": 0.02}
            }
        )

        assert result["approval_required"] is True
        assert "write" in result["approval_reason"]