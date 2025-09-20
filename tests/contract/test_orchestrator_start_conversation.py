"""Contract test for start_conversation MCP tool."""

import json
import pytest
from typing import Any, Dict

from pydantic import BaseModel, ValidationError


class StartConversationRequest(BaseModel):
    """Request schema for start_conversation MCP tool."""

    topic: str
    participants: list[str]
    policy_id: str = "default"
    max_turns: int = 8
    budget_usd: float = 1.0


class StartConversationResponse(BaseModel):
    """Response schema for start_conversation MCP tool."""

    session_id: str
    status: str
    participants: list[str]
    policy_applied: str
    created_at: str


class TestStartConversationContract:
    """Contract tests for start_conversation MCP tool."""

    def test_valid_request_schema(self):
        """Test that valid requests conform to schema."""
        valid_request = {
            "topic": "Analyze potential race conditions in the user authentication module",
            "participants": ["claude_code", "codex_cli"],
            "policy_id": "development_safe",
            "max_turns": 6,
            "budget_usd": 0.50
        }

        # This should not raise ValidationError
        request = StartConversationRequest(**valid_request)

        assert request.topic == valid_request["topic"]
        assert request.participants == valid_request["participants"]
        assert request.policy_id == valid_request["policy_id"]
        assert request.max_turns == valid_request["max_turns"]
        assert request.budget_usd == valid_request["budget_usd"]

    def test_minimal_valid_request(self):
        """Test request with only required fields."""
        minimal_request = {
            "topic": "Test topic",
            "participants": ["claude_code", "codex_cli"]
        }

        request = StartConversationRequest(**minimal_request)

        assert request.topic == "Test topic"
        assert request.participants == ["claude_code", "codex_cli"]
        assert request.policy_id == "default"  # Default value
        assert request.max_turns == 8  # Default value
        assert request.budget_usd == 1.0  # Default value

    def test_invalid_topic_empty(self):
        """Test that empty topic is rejected."""
        invalid_request = {
            "topic": "",
            "participants": ["claude_code", "codex_cli"]
        }

        with pytest.raises(ValidationError) as exc_info:
            StartConversationRequest(**invalid_request)

        assert "String should have at least 1 character" in str(exc_info.value)

    def test_invalid_topic_too_long(self):
        """Test that topic exceeding max length is rejected."""
        invalid_request = {
            "topic": "x" * 1001,  # Exceeds 1000 char limit
            "participants": ["claude_code", "codex_cli"]
        }

        with pytest.raises(ValidationError) as exc_info:
            StartConversationRequest(**invalid_request)

        assert "String should have at most 1000 characters" in str(exc_info.value)

    def test_invalid_participants_empty(self):
        """Test that empty participants list is rejected."""
        invalid_request = {
            "topic": "Test topic",
            "participants": []
        }

        with pytest.raises(ValidationError) as exc_info:
            StartConversationRequest(**invalid_request)

        assert "List should have at least 2 items" in str(exc_info.value)

    def test_invalid_participants_one_agent(self):
        """Test that single participant is rejected."""
        invalid_request = {
            "topic": "Test topic",
            "participants": ["claude_code"]
        }

        with pytest.raises(ValidationError) as exc_info:
            StartConversationRequest(**invalid_request)

        assert "List should have at least 2 items" in str(exc_info.value)

    def test_invalid_participants_too_many(self):
        """Test that too many participants is rejected."""
        invalid_request = {
            "topic": "Test topic",
            "participants": ["claude_code", "codex_cli", "agent3", "agent4", "agent5", "agent6"]
        }

        with pytest.raises(ValidationError) as exc_info:
            StartConversationRequest(**invalid_request)

        assert "List should have at most 5 items" in str(exc_info.value)

    def test_invalid_participants_unknown_agent(self):
        """Test that unknown agent types are rejected."""
        invalid_request = {
            "topic": "Test topic",
            "participants": ["claude_code", "unknown_agent"]
        }

        with pytest.raises(ValidationError) as exc_info:
            StartConversationRequest(**invalid_request)

        error_str = str(exc_info.value)
        assert "Input should be 'claude_code' or 'codex_cli'" in error_str

    def test_invalid_max_turns_negative(self):
        """Test that negative max_turns is rejected."""
        invalid_request = {
            "topic": "Test topic",
            "participants": ["claude_code", "codex_cli"],
            "max_turns": 0
        }

        with pytest.raises(ValidationError) as exc_info:
            StartConversationRequest(**invalid_request)

        assert "Input should be greater than or equal to 1" in str(exc_info.value)

    def test_invalid_max_turns_too_high(self):
        """Test that max_turns exceeding limit is rejected."""
        invalid_request = {
            "topic": "Test topic",
            "participants": ["claude_code", "codex_cli"],
            "max_turns": 21
        }

        with pytest.raises(ValidationError) as exc_info:
            StartConversationRequest(**invalid_request)

        assert "Input should be less than or equal to 20" in str(exc_info.value)

    def test_invalid_budget_too_low(self):
        """Test that budget below minimum is rejected."""
        invalid_request = {
            "topic": "Test topic",
            "participants": ["claude_code", "codex_cli"],
            "budget_usd": 0.005
        }

        with pytest.raises(ValidationError) as exc_info:
            StartConversationRequest(**invalid_request)

        assert "Input should be greater than or equal to 0.01" in str(exc_info.value)

    def test_invalid_budget_too_high(self):
        """Test that budget above maximum is rejected."""
        invalid_request = {
            "topic": "Test topic",
            "participants": ["claude_code", "codex_cli"],
            "budget_usd": 15.0
        }

        with pytest.raises(ValidationError) as exc_info:
            StartConversationRequest(**invalid_request)

        assert "Input should be less than or equal to 10.0" in str(exc_info.value)

    def test_valid_response_schema(self):
        """Test that valid responses conform to schema."""
        valid_response = {
            "session_id": "session_123456",
            "status": "active",
            "participants": ["claude_code", "codex_cli"],
            "policy_applied": "development_safe",
            "created_at": "2025-09-21T10:30:00Z"
        }

        response = StartConversationResponse(**valid_response)

        assert response.session_id == valid_response["session_id"]
        assert response.status == valid_response["status"]
        assert response.participants == valid_response["participants"]
        assert response.policy_applied == valid_response["policy_applied"]
        assert response.created_at == valid_response["created_at"]

    def test_invalid_response_status(self):
        """Test that invalid status values are rejected."""
        invalid_response = {
            "session_id": "session_123456",
            "status": "invalid_status",
            "participants": ["claude_code", "codex_cli"],
            "policy_applied": "development_safe",
            "created_at": "2025-09-21T10:30:00Z"
        }

        with pytest.raises(ValidationError) as exc_info:
            StartConversationResponse(**invalid_response)

        error_str = str(exc_info.value)
        assert "Input should be 'active' or 'failed'" in error_str

    @pytest.mark.integration
    def test_mcp_tool_not_implemented(self):
        """Test that the MCP tool is not yet implemented."""
        # This test should fail until the actual MCP tool is implemented
        # It serves as a reminder that implementation is needed

        # Attempt to import the actual implementation
        with pytest.raises(ImportError):
            from tab.services.mcp_orchestrator_server import start_conversation

        # This test will fail, indicating implementation is needed
        assert False, "start_conversation MCP tool not yet implemented"

    def test_json_serialization(self):
        """Test that request/response can be serialized to/from JSON."""
        request_data = {
            "topic": "Test topic",
            "participants": ["claude_code", "codex_cli"],
            "policy_id": "development_safe",
            "max_turns": 5,
            "budget_usd": 0.75
        }

        # Test request serialization
        request = StartConversationRequest(**request_data)
        request_json = request.model_dump_json()
        parsed_request = StartConversationRequest.model_validate_json(request_json)

        assert parsed_request.topic == request_data["topic"]
        assert parsed_request.participants == request_data["participants"]

        # Test response serialization
        response_data = {
            "session_id": "session_abc123",
            "status": "active",
            "participants": ["claude_code", "codex_cli"],
            "policy_applied": "development_safe",
            "created_at": "2025-09-21T10:30:00Z"
        }

        response = StartConversationResponse(**response_data)
        response_json = response.model_dump_json()
        parsed_response = StartConversationResponse.model_validate_json(response_json)

        assert parsed_response.session_id == response_data["session_id"]
        assert parsed_response.status == response_data["status"]