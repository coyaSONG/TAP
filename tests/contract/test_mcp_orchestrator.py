"""
Contract tests for MCP Orchestrator Server.

These tests validate the MCP server contract implementation against the
specifications in specs/001-prd-md/contracts/mcp-orchestrator.json.

CRITICAL: These tests MUST FAIL until the MCP server is implemented.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# Import will fail until implementation exists - this is expected
try:
    from tab.services.mcp_orchestrator_server import MCPOrchestratorServer
except ImportError:
    MCPOrchestratorServer = None

pytestmark = pytest.mark.contract


class TestMCPOrchestratorContract:
    """Contract tests for MCP Orchestrator server tools."""

    @pytest.fixture
    def mcp_server(self):
        """Create MCP orchestrator server instance."""
        if MCPOrchestratorServer is None:
            pytest.skip("MCPOrchestratorServer not yet implemented")
        return MCPOrchestratorServer()

    @pytest.mark.asyncio
    async def test_start_conversation_tool_contract(self, mcp_server):
        """Test start_conversation tool conforms to contract."""
        # Test input schema validation
        valid_input = {
            "topic": "Analyze race conditions in authentication module",
            "participants": ["claude_code", "codex_cli"],
            "policy_id": "development_safe",
            "max_turns": 6,
            "budget_usd": 0.5
        }

        result = await mcp_server.handle_tool_call("start_conversation", valid_input)

        # Validate output schema
        assert isinstance(result, dict)
        assert "session_id" in result
        assert "status" in result
        assert result["status"] in ["active", "failed"]
        assert "participants" in result
        assert isinstance(result["participants"], list)
        assert "created_at" in result

        # Validate created_at is valid ISO datetime
        datetime.fromisoformat(result["created_at"].replace('Z', '+00:00'))

        # Test required fields
        required_fields = ["session_id", "status", "participants", "created_at"]
        for field in required_fields:
            assert field in result, f"Required field {field} missing from response"

    @pytest.mark.asyncio
    async def test_start_conversation_input_validation(self, mcp_server):
        """Test start_conversation input validation according to schema."""
        # Test missing required fields
        with pytest.raises((ValueError, TypeError, KeyError)):
            await mcp_server.handle_tool_call("start_conversation", {})

        # Test invalid topic length
        with pytest.raises((ValueError, TypeError)):
            await mcp_server.handle_tool_call("start_conversation", {
                "topic": "",  # minLength: 1
                "participants": ["claude_code", "codex_cli"]
            })

        # Test topic too long
        with pytest.raises((ValueError, TypeError)):
            await mcp_server.handle_tool_call("start_conversation", {
                "topic": "x" * 1001,  # maxLength: 1000
                "participants": ["claude_code", "codex_cli"]
            })

        # Test invalid participants
        with pytest.raises((ValueError, TypeError)):
            await mcp_server.handle_tool_call("start_conversation", {
                "topic": "test topic",
                "participants": ["invalid_agent"]  # not in enum
            })

        # Test insufficient participants
        with pytest.raises((ValueError, TypeError)):
            await mcp_server.handle_tool_call("start_conversation", {
                "topic": "test topic",
                "participants": ["claude_code"]  # minItems: 2
            })

        # Test budget constraints
        with pytest.raises((ValueError, TypeError)):
            await mcp_server.handle_tool_call("start_conversation", {
                "topic": "test topic",
                "participants": ["claude_code", "codex_cli"],
                "budget_usd": 0.005  # minimum: 0.01
            })

    @pytest.mark.asyncio
    async def test_send_message_tool_contract(self, mcp_server):
        """Test send_message tool conforms to contract."""
        # First create a session
        session_result = await mcp_server.handle_tool_call("start_conversation", {
            "topic": "Test conversation",
            "participants": ["claude_code", "codex_cli"]
        })
        session_id = session_result["session_id"]

        # Test send_message
        valid_input = {
            "session_id": session_id,
            "content": "Please analyze this code for potential issues",
            "to_agent": "claude_code",
            "attachments": [
                {
                    "path": "/tmp/test.py",
                    "type": "text/python",
                    "size": 1024
                }
            ]
        }

        result = await mcp_server.handle_tool_call("send_message", valid_input)

        # Validate output schema
        assert isinstance(result, dict)
        assert "turn_id" in result
        assert "response" in result
        assert "session_status" in result

        # Validate response object
        response = result["response"]
        assert "content" in response
        assert "from_agent" in response
        assert isinstance(response["content"], str)
        assert isinstance(response["from_agent"], str)

        # Validate session_status enum
        assert result["session_status"] in ["active", "completed", "failed", "timeout"]

        # Check for convergence_detected field
        assert "convergence_detected" in result
        assert isinstance(result["convergence_detected"], bool)

    @pytest.mark.asyncio
    async def test_send_message_input_validation(self, mcp_server):
        """Test send_message input validation."""
        # Test missing required fields
        with pytest.raises((ValueError, TypeError, KeyError)):
            await mcp_server.handle_tool_call("send_message", {})

        # Test empty content
        with pytest.raises((ValueError, TypeError)):
            await mcp_server.handle_tool_call("send_message", {
                "session_id": "test-session",
                "content": ""  # minLength: 1
            })

        # Test content too long
        with pytest.raises((ValueError, TypeError)):
            await mcp_server.handle_tool_call("send_message", {
                "session_id": "test-session",
                "content": "x" * 10001  # maxLength: 10000
            })

        # Test invalid to_agent
        with pytest.raises((ValueError, TypeError)):
            await mcp_server.handle_tool_call("send_message", {
                "session_id": "test-session",
                "content": "test message",
                "to_agent": "invalid_agent"  # not in enum
            })

    @pytest.mark.asyncio
    async def test_get_session_status_tool_contract(self, mcp_server):
        """Test get_session_status tool conforms to contract."""
        # First create a session
        session_result = await mcp_server.handle_tool_call("start_conversation", {
            "topic": "Test conversation",
            "participants": ["claude_code", "codex_cli"]
        })
        session_id = session_result["session_id"]

        # Test get_session_status without history
        result = await mcp_server.handle_tool_call("get_session_status", {
            "session_id": session_id,
            "include_history": False
        })

        # Validate required fields
        required_fields = [
            "session_id", "status", "participants", "current_turn",
            "total_cost_usd", "created_at", "updated_at"
        ]
        for field in required_fields:
            assert field in result, f"Required field {field} missing"

        # Validate types and constraints
        assert result["status"] in ["active", "completed", "failed", "timeout"]
        assert isinstance(result["participants"], list)
        assert isinstance(result["current_turn"], int)
        assert isinstance(result["total_cost_usd"], (int, float))

        # Validate datetime fields
        datetime.fromisoformat(result["created_at"].replace('Z', '+00:00'))
        datetime.fromisoformat(result["updated_at"].replace('Z', '+00:00'))

        # Validate budget_remaining if present
        if "budget_remaining" in result:
            budget = result["budget_remaining"]
            assert "cost_usd" in budget
            assert "turns" in budget

    @pytest.mark.asyncio
    async def test_list_agents_tool_contract(self, mcp_server):
        """Test list_agents tool conforms to contract."""
        result = await mcp_server.handle_tool_call("list_agents", {
            "include_capabilities": True
        })

        # Validate output schema
        assert "agents" in result
        assert isinstance(result["agents"], list)

        if result["agents"]:  # If agents are available
            agent = result["agents"][0]
            required_fields = [
                "agent_id", "name", "type", "version", "status", "last_health_check"
            ]
            for field in required_fields:
                assert field in agent, f"Required field {field} missing from agent"

            # Validate status enum
            assert agent["status"] in ["available", "busy", "failed", "maintenance"]

            # Validate datetime field
            datetime.fromisoformat(agent["last_health_check"].replace('Z', '+00:00'))

            # Check capabilities if requested
            if "capabilities" in agent:
                assert isinstance(agent["capabilities"], list)

    @pytest.mark.asyncio
    async def test_export_audit_log_tool_contract(self, mcp_server):
        """Test export_audit_log tool conforms to contract."""
        # First create a session to have audit data
        session_result = await mcp_server.handle_tool_call("start_conversation", {
            "topic": "Test conversation",
            "participants": ["claude_code", "codex_cli"]
        })
        session_id = session_result["session_id"]

        # Test export_audit_log
        result = await mcp_server.handle_tool_call("export_audit_log", {
            "session_id": session_id,
            "format": "json",
            "include_security_events": True
        })

        # Validate output schema
        required_fields = ["audit_data", "format", "record_count", "exported_at"]
        for field in required_fields:
            assert field in result, f"Required field {field} missing"

        # Validate types
        assert isinstance(result["audit_data"], str)
        assert result["format"] in ["json", "csv", "jsonl"]
        assert isinstance(result["record_count"], int)

        # Validate datetime field
        datetime.fromisoformat(result["exported_at"].replace('Z', '+00:00'))

        # Validate audit_data is valid JSON when format is json
        if result["format"] == "json":
            json.loads(result["audit_data"])  # Should not raise


class TestMCPOrchestratorResources:
    """Contract tests for MCP Orchestrator resources."""

    @pytest.fixture
    def mcp_server(self):
        """Create MCP orchestrator server instance."""
        if MCPOrchestratorServer is None:
            pytest.skip("MCPOrchestratorServer not yet implemented")
        return MCPOrchestratorServer()

    @pytest.mark.asyncio
    async def test_session_resource_contract(self, mcp_server):
        """Test session resource URI contract."""
        # Create a session first
        session_result = await mcp_server.handle_tool_call("start_conversation", {
            "topic": "Test conversation",
            "participants": ["claude_code", "codex_cli"]
        })
        session_id = session_result["session_id"]

        # Test resource access
        resource_uri = f"tab://sessions/{session_id}"
        resource_data = await mcp_server.get_resource(resource_uri)

        # Validate resource returns valid JSON
        assert resource_data is not None
        if isinstance(resource_data, str):
            json.loads(resource_data)  # Should parse as valid JSON

    @pytest.mark.asyncio
    async def test_agent_health_resource_contract(self, mcp_server):
        """Test agent health resource URI contract."""
        resource_uri = "tab://agents/claude_code/health"
        resource_data = await mcp_server.get_resource(resource_uri)

        # Validate resource returns valid JSON
        assert resource_data is not None
        if isinstance(resource_data, str):
            health_data = json.loads(resource_data)
            # Should contain health status information
            assert "status" in health_data

    @pytest.mark.asyncio
    async def test_policy_resource_contract(self, mcp_server):
        """Test policy resource URI contract."""
        resource_uri = "tab://policies/development_safe"
        resource_data = await mcp_server.get_resource(resource_uri)

        # Validate resource returns valid YAML/JSON
        assert resource_data is not None
        if isinstance(resource_data, str):
            # Should be valid YAML or JSON
            try:
                json.loads(resource_data)
            except json.JSONDecodeError:
                # If not JSON, should be valid YAML
                import yaml
                yaml.safe_load(resource_data)


class TestMCPOrchestratorPrompts:
    """Contract tests for MCP Orchestrator prompts."""

    @pytest.fixture
    def mcp_server(self):
        """Create MCP orchestrator server instance."""
        if MCPOrchestratorServer is None:
            pytest.skip("MCPOrchestratorServer not yet implemented")
        return MCPOrchestratorServer()

    @pytest.mark.asyncio
    async def test_conversation_summary_prompt_contract(self, mcp_server):
        """Test conversation_summary prompt contract."""
        # Create a session first
        session_result = await mcp_server.handle_tool_call("start_conversation", {
            "topic": "Test conversation",
            "participants": ["claude_code", "codex_cli"]
        })
        session_id = session_result["session_id"]

        # Test prompt with required argument
        prompt_result = await mcp_server.handle_prompt("conversation_summary", {
            "session_id": session_id,
            "summary_type": "detailed"
        })

        assert prompt_result is not None
        assert isinstance(prompt_result, str)

    @pytest.mark.asyncio
    async def test_convergence_analysis_prompt_contract(self, mcp_server):
        """Test convergence_analysis prompt contract."""
        # Create a session first
        session_result = await mcp_server.handle_tool_call("start_conversation", {
            "topic": "Test conversation",
            "participants": ["claude_code", "codex_cli"]
        })
        session_id = session_result["session_id"]

        # Test prompt with required argument
        prompt_result = await mcp_server.handle_prompt("convergence_analysis", {
            "session_id": session_id
        })

        assert prompt_result is not None
        assert isinstance(prompt_result, str)