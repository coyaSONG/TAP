"""Contract test for send_message MCP tool."""

import pytest
from typing import Any, Dict, Optional

from pydantic import BaseModel, ValidationError


class MessageAttachment(BaseModel):
    """Attachment schema for messages."""

    path: str
    type: str
    size: Optional[int] = None


class SendMessageRequest(BaseModel):
    """Request schema for send_message MCP tool."""

    session_id: str
    content: str
    to_agent: Optional[str] = None
    attachments: Optional[list[MessageAttachment]] = None


class MessageMetadata(BaseModel):
    """Metadata for message response."""

    cost_usd: float
    duration_ms: int
    tokens_used: int


class MessageResponse(BaseModel):
    """Response content from agent."""

    content: str
    from_agent: str
    metadata: Optional[MessageMetadata] = None


class SendMessageResponse(BaseModel):
    """Response schema for send_message MCP tool."""

    turn_id: str
    response: MessageResponse
    session_status: str
    convergence_detected: Optional[bool] = None


class TestSendMessageContract:
    """Contract tests for send_message MCP tool."""

    def test_valid_request_minimal(self):
        """Test valid request with only required fields."""
        request_data = {
            "session_id": "session_123",
            "content": "Please analyze this code for potential issues."
        }

        request = SendMessageRequest(**request_data)

        assert request.session_id == "session_123"
        assert request.content == "Please analyze this code for potential issues."
        assert request.to_agent is None
        assert request.attachments is None

    def test_valid_request_with_target_agent(self):
        """Test valid request with specific target agent."""
        request_data = {
            "session_id": "session_123",
            "content": "Run the test suite",
            "to_agent": "codex_cli"
        }

        request = SendMessageRequest(**request_data)

        assert request.session_id == "session_123"
        assert request.content == "Run the test suite"
        assert request.to_agent == "codex_cli"

    def test_valid_request_with_attachments(self):
        """Test valid request with file attachments."""
        request_data = {
            "session_id": "session_123",
            "content": "Review these files",
            "attachments": [
                {
                    "path": "/workspace/src/auth.py",
                    "type": "text/python",
                    "size": 1024
                },
                {
                    "path": "/workspace/tests/test_auth.py",
                    "type": "text/python",
                    "size": 512
                }
            ]
        }

        request = SendMessageRequest(**request_data)

        assert request.session_id == "session_123"
        assert len(request.attachments) == 2
        assert request.attachments[0].path == "/workspace/src/auth.py"
        assert request.attachments[0].type == "text/python"
        assert request.attachments[1].size == 512

    def test_invalid_session_id_empty(self):
        """Test that empty session_id is rejected."""
        request_data = {
            "session_id": "",
            "content": "Test message"
        }

        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest(**request_data)

        assert "String should have at least 1 character" in str(exc_info.value)

    def test_invalid_content_empty(self):
        """Test that empty content is rejected."""
        request_data = {
            "session_id": "session_123",
            "content": ""
        }

        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest(**request_data)

        assert "String should have at least 1 character" in str(exc_info.value)

    def test_invalid_content_too_long(self):
        """Test that content exceeding max length is rejected."""
        request_data = {
            "session_id": "session_123",
            "content": "x" * 10001  # Exceeds 10000 char limit
        }

        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest(**request_data)

        assert "String should have at most 10000 characters" in str(exc_info.value)

    def test_invalid_to_agent_value(self):
        """Test that invalid to_agent values are rejected."""
        request_data = {
            "session_id": "session_123",
            "content": "Test message",
            "to_agent": "invalid_agent"
        }

        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest(**request_data)

        error_str = str(exc_info.value)
        assert "Input should be 'claude_code', 'codex_cli' or 'auto'" in error_str

    def test_invalid_too_many_attachments(self):
        """Test that too many attachments are rejected."""
        attachments = [
            {"path": f"/file_{i}.py", "type": "text/python"}
            for i in range(11)  # Exceeds 10 attachment limit
        ]

        request_data = {
            "session_id": "session_123",
            "content": "Test message",
            "attachments": attachments
        }

        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest(**request_data)

        assert "List should have at most 10 items" in str(exc_info.value)

    def test_invalid_attachment_missing_required_fields(self):
        """Test that attachments require path and type."""
        request_data = {
            "session_id": "session_123",
            "content": "Test message",
            "attachments": [
                {
                    "path": "/workspace/file.py"
                    # Missing 'type' field
                }
            ]
        }

        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest(**request_data)

        assert "Field required" in str(exc_info.value)

    def test_valid_response_minimal(self):
        """Test valid response with minimal required fields."""
        response_data = {
            "turn_id": "turn_456",
            "response": {
                "content": "I found 3 potential issues in the authentication module.",
                "from_agent": "claude_code"
            },
            "session_status": "active"
        }

        response = SendMessageResponse(**response_data)

        assert response.turn_id == "turn_456"
        assert response.response.content.startswith("I found 3 potential issues")
        assert response.response.from_agent == "claude_code"
        assert response.session_status == "active"
        assert response.convergence_detected is None

    def test_valid_response_with_metadata(self):
        """Test valid response with metadata."""
        response_data = {
            "turn_id": "turn_789",
            "response": {
                "content": "Tests completed successfully.",
                "from_agent": "codex_cli",
                "metadata": {
                    "cost_usd": 0.15,
                    "duration_ms": 3500,
                    "tokens_used": 250
                }
            },
            "session_status": "completed",
            "convergence_detected": True
        }

        response = SendMessageResponse(**response_data)

        assert response.turn_id == "turn_789"
        assert response.response.from_agent == "codex_cli"
        assert response.response.metadata.cost_usd == 0.15
        assert response.response.metadata.duration_ms == 3500
        assert response.session_status == "completed"
        assert response.convergence_detected is True

    def test_invalid_response_status(self):
        """Test that invalid session_status values are rejected."""
        response_data = {
            "turn_id": "turn_456",
            "response": {
                "content": "Response content",
                "from_agent": "claude_code"
            },
            "session_status": "invalid_status"
        }

        with pytest.raises(ValidationError) as exc_info:
            SendMessageResponse(**response_data)

        error_str = str(exc_info.value)
        expected_statuses = ["active", "completed", "failed", "timeout"]
        for status in expected_statuses:
            assert status in error_str

    def test_invalid_response_empty_content(self):
        """Test that empty response content is rejected."""
        response_data = {
            "turn_id": "turn_456",
            "response": {
                "content": "",
                "from_agent": "claude_code"
            },
            "session_status": "active"
        }

        with pytest.raises(ValidationError) as exc_info:
            SendMessageResponse(**response_data)

        assert "String should have at least 1 character" in str(exc_info.value)

    def test_invalid_metadata_negative_values(self):
        """Test that negative metadata values are rejected."""
        response_data = {
            "turn_id": "turn_456",
            "response": {
                "content": "Response",
                "from_agent": "claude_code",
                "metadata": {
                    "cost_usd": -0.1,  # Invalid negative cost
                    "duration_ms": 1000,
                    "tokens_used": 100
                }
            },
            "session_status": "active"
        }

        with pytest.raises(ValidationError) as exc_info:
            SendMessageResponse(**response_data)

        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    @pytest.mark.integration
    def test_mcp_tool_not_implemented(self):
        """Test that the MCP tool is not yet implemented."""
        # This test should fail until the actual MCP tool is implemented

        with pytest.raises(ImportError):
            from tab.services.mcp_orchestrator_server import send_message

        # This test will fail, indicating implementation is needed
        assert False, "send_message MCP tool not yet implemented"

    def test_json_serialization(self):
        """Test JSON serialization of request and response."""
        # Test request serialization
        request_data = {
            "session_id": "session_test",
            "content": "Analyze this code",
            "to_agent": "claude_code",
            "attachments": [
                {
                    "path": "/test.py",
                    "type": "text/python",
                    "size": 100
                }
            ]
        }

        request = SendMessageRequest(**request_data)
        request_json = request.model_dump_json()
        parsed_request = SendMessageRequest.model_validate_json(request_json)

        assert parsed_request.session_id == request_data["session_id"]
        assert parsed_request.content == request_data["content"]
        assert len(parsed_request.attachments) == 1

        # Test response serialization
        response_data = {
            "turn_id": "turn_test",
            "response": {
                "content": "Analysis complete",
                "from_agent": "claude_code",
                "metadata": {
                    "cost_usd": 0.05,
                    "duration_ms": 2000,
                    "tokens_used": 150
                }
            },
            "session_status": "active",
            "convergence_detected": False
        }

        response = SendMessageResponse(**response_data)
        response_json = response.model_dump_json()
        parsed_response = SendMessageResponse.model_validate_json(response_json)

        assert parsed_response.turn_id == response_data["turn_id"]
        assert parsed_response.response.from_agent == "claude_code"
        assert parsed_response.convergence_detected is False