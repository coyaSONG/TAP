"""Contract test for list_agents MCP tool."""

import pytest
from typing import Optional

from pydantic import BaseModel, ValidationError


class ListAgentsRequest(BaseModel):
    """Request schema for list_agents MCP tool."""

    include_capabilities: bool = False


class Agent(BaseModel):
    """Agent information schema."""

    agent_id: str
    name: str
    type: str
    version: str
    status: str
    last_health_check: str
    capabilities: Optional[list[str]] = None


class ListAgentsResponse(BaseModel):
    """Response schema for list_agents MCP tool."""

    agents: list[Agent]


class TestListAgentsContract:
    """Contract tests for list_agents MCP tool."""

    def test_valid_request_default(self):
        """Test valid request with default values."""
        request_data = {}

        request = ListAgentsRequest(**request_data)

        assert request.include_capabilities is False

    def test_valid_request_with_capabilities(self):
        """Test valid request including capabilities."""
        request_data = {
            "include_capabilities": True
        }

        request = ListAgentsRequest(**request_data)

        assert request.include_capabilities is True

    def test_valid_response_minimal(self):
        """Test valid response without capabilities."""
        response_data = {
            "agents": [
                {
                    "agent_id": "claude_code",
                    "name": "Claude Code",
                    "type": "claude_code",
                    "version": "2.1.0",
                    "status": "available",
                    "last_health_check": "2025-09-21T10:30:00Z"
                },
                {
                    "agent_id": "codex_cli",
                    "name": "Codex CLI",
                    "type": "codex_cli",
                    "version": "1.5.2",
                    "status": "busy",
                    "last_health_check": "2025-09-21T10:29:45Z"
                }
            ]
        }

        response = ListAgentsResponse(**response_data)

        assert len(response.agents) == 2
        assert response.agents[0].agent_id == "claude_code"
        assert response.agents[0].name == "Claude Code"
        assert response.agents[0].status == "available"
        assert response.agents[1].agent_id == "codex_cli"
        assert response.agents[1].status == "busy"
        assert response.agents[0].capabilities is None

    def test_valid_response_with_capabilities(self):
        """Test valid response including capabilities."""
        response_data = {
            "agents": [
                {
                    "agent_id": "claude_code",
                    "name": "Claude Code",
                    "type": "claude_code",
                    "version": "2.1.0",
                    "status": "available",
                    "last_health_check": "2025-09-21T10:30:00Z",
                    "capabilities": [
                        "code_analysis",
                        "bug_detection",
                        "test_generation",
                        "documentation",
                        "refactoring"
                    ]
                },
                {
                    "agent_id": "codex_cli",
                    "name": "Codex CLI",
                    "type": "codex_cli",
                    "version": "1.5.2",
                    "status": "available",
                    "last_health_check": "2025-09-21T10:29:45Z",
                    "capabilities": [
                        "code_execution",
                        "test_running",
                        "build_automation",
                        "deployment",
                        "system_integration"
                    ]
                }
            ]
        }

        response = ListAgentsResponse(**response_data)

        assert len(response.agents) == 2
        assert len(response.agents[0].capabilities) == 5
        assert "code_analysis" in response.agents[0].capabilities
        assert "code_execution" in response.agents[1].capabilities

    def test_valid_response_empty_agents(self):
        """Test valid response with no agents."""
        response_data = {
            "agents": []
        }

        response = ListAgentsResponse(**response_data)

        assert len(response.agents) == 0

    def test_invalid_agent_status(self):
        """Test that invalid agent status values are rejected."""
        response_data = {
            "agents": [
                {
                    "agent_id": "claude_code",
                    "name": "Claude Code",
                    "type": "claude_code",
                    "version": "2.1.0",
                    "status": "invalid_status",
                    "last_health_check": "2025-09-21T10:30:00Z"
                }
            ]
        }

        with pytest.raises(ValidationError) as exc_info:
            ListAgentsResponse(**response_data)

        error_str = str(exc_info.value)
        valid_statuses = ["available", "busy", "failed", "maintenance"]
        for status in valid_statuses:
            assert status in error_str

    def test_invalid_agent_missing_required_fields(self):
        """Test that missing required fields are rejected."""
        response_data = {
            "agents": [
                {
                    "agent_id": "claude_code",
                    "name": "Claude Code",
                    # Missing required fields: type, version, status, last_health_check
                }
            ]
        }

        with pytest.raises(ValidationError) as exc_info:
            ListAgentsResponse(**response_data)

        assert "Field required" in str(exc_info.value)

    def test_invalid_agent_empty_agent_id(self):
        """Test that empty agent_id is rejected."""
        response_data = {
            "agents": [
                {
                    "agent_id": "",
                    "name": "Claude Code",
                    "type": "claude_code",
                    "version": "2.1.0",
                    "status": "available",
                    "last_health_check": "2025-09-21T10:30:00Z"
                }
            ]
        }

        with pytest.raises(ValidationError) as exc_info:
            ListAgentsResponse(**response_data)

        assert "String should have at least 1 character" in str(exc_info.value)

    def test_invalid_agent_empty_name(self):
        """Test that empty name is rejected."""
        response_data = {
            "agents": [
                {
                    "agent_id": "claude_code",
                    "name": "",
                    "type": "claude_code",
                    "version": "2.1.0",
                    "status": "available",
                    "last_health_check": "2025-09-21T10:30:00Z"
                }
            ]
        }

        with pytest.raises(ValidationError) as exc_info:
            ListAgentsResponse(**response_data)

        assert "String should have at least 1 character" in str(exc_info.value)

    def test_agent_status_transitions(self):
        """Test valid agent status values."""
        valid_statuses = ["available", "busy", "failed", "maintenance"]

        for status in valid_statuses:
            response_data = {
                "agents": [
                    {
                        "agent_id": "test_agent",
                        "name": "Test Agent",
                        "type": "test",
                        "version": "1.0.0",
                        "status": status,
                        "last_health_check": "2025-09-21T10:30:00Z"
                    }
                ]
            }

            # Should not raise ValidationError
            response = ListAgentsResponse(**response_data)
            assert response.agents[0].status == status

    @pytest.mark.integration
    def test_mcp_tool_not_implemented(self):
        """Test that the MCP tool is not yet implemented."""
        with pytest.raises(ImportError):
            from tab.services.mcp_orchestrator_server import list_agents

        assert False, "list_agents MCP tool not yet implemented"

    def test_json_serialization(self):
        """Test JSON serialization."""
        request_data = {
            "include_capabilities": True
        }

        request = ListAgentsRequest(**request_data)
        request_json = request.model_dump_json()
        parsed_request = ListAgentsRequest.model_validate_json(request_json)

        assert parsed_request.include_capabilities is True

        response_data = {
            "agents": [
                {
                    "agent_id": "test_agent",
                    "name": "Test Agent",
                    "type": "test",
                    "version": "1.0.0",
                    "status": "available",
                    "last_health_check": "2025-09-21T10:30:00Z",
                    "capabilities": ["test_capability"]
                }
            ]
        }

        response = ListAgentsResponse(**response_data)
        response_json = response.model_dump_json()
        parsed_response = ListAgentsResponse.model_validate_json(response_json)

        assert len(parsed_response.agents) == 1
        assert parsed_response.agents[0].agent_id == "test_agent"
        assert parsed_response.agents[0].capabilities == ["test_capability"]

    def test_agent_capabilities_optional(self):
        """Test that capabilities field is truly optional."""
        agent_without_capabilities = {
            "agent_id": "test_agent",
            "name": "Test Agent",
            "type": "test",
            "version": "1.0.0",
            "status": "available",
            "last_health_check": "2025-09-21T10:30:00Z"
        }

        agent = Agent(**agent_without_capabilities)
        assert agent.capabilities is None

        agent_with_capabilities = {
            "agent_id": "test_agent",
            "name": "Test Agent",
            "type": "test",
            "version": "1.0.0",
            "status": "available",
            "last_health_check": "2025-09-21T10:30:00Z",
            "capabilities": ["cap1", "cap2"]
        }

        agent = Agent(**agent_with_capabilities)
        assert agent.capabilities == ["cap1", "cap2"]