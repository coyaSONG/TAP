"""Contract test for agent process_request interface."""

import pytest
from typing import Optional, Any, Dict

from pydantic import BaseModel, ValidationError


class ConversationHistoryItem(BaseModel):
    """Conversation history item schema."""

    role: str
    content: str
    from_agent: str
    timestamp: str


class SessionMetadata(BaseModel):
    """Session metadata schema."""

    session_id: str
    topic: str
    turn_number: int


class RequestContext(BaseModel):
    """Request context schema."""

    conversation_history: Optional[list[ConversationHistoryItem]] = None
    working_directory: Optional[str] = None
    allowed_files: Optional[list[str]] = None
    session_metadata: Optional[SessionMetadata] = None


class RequestConstraints(BaseModel):
    """Request constraints schema."""

    max_execution_time_ms: int = 120000
    max_cost_usd: float = 0.1
    allowed_tools: Optional[list[str]] = None
    disallowed_tools: Optional[list[str]] = None
    permission_mode: str = "prompt"


class ProcessRequestRequest(BaseModel):
    """Request schema for process_request agent interface."""

    request_id: str
    content: str
    context: Optional[RequestContext] = None
    constraints: Optional[RequestConstraints] = None


class Evidence(BaseModel):
    """Evidence item schema."""

    type: str
    source: str
    content: str


class ResponseContent(BaseModel):
    """Response content schema."""

    content: str
    reasoning: Optional[str] = None
    confidence: Optional[float] = None
    next_action_suggested: Optional[str] = None
    evidence: Optional[list[Evidence]] = None


class ResponseMetadata(BaseModel):
    """Response metadata schema."""

    execution_time_ms: Optional[int] = None
    cost_usd: Optional[float] = None
    tokens_used: Optional[int] = None
    tools_used: Optional[list[str]] = None
    files_accessed: Optional[list[str]] = None
    error_details: Optional[str] = None


class ConvergenceSignals(BaseModel):
    """Convergence signals schema."""

    solution_proposed: Optional[bool] = None
    consensus_reached: Optional[bool] = None
    requires_verification: Optional[bool] = None
    additional_input_needed: Optional[bool] = None
    confidence_threshold_met: Optional[bool] = None


class ProcessRequestResponse(BaseModel):
    """Response schema for process_request agent interface."""

    request_id: str
    status: str
    response: ResponseContent
    metadata: ResponseMetadata
    convergence_signals: Optional[ConvergenceSignals] = None


class TestAgentProcessRequestContract:
    """Contract tests for agent process_request interface."""

    def test_valid_request_minimal(self):
        """Test valid request with only required fields."""
        request_data = {
            "request_id": "req_123",
            "content": "Analyze this code for potential race conditions."
        }

        request = ProcessRequestRequest(**request_data)

        assert request.request_id == "req_123"
        assert request.content == "Analyze this code for potential race conditions."
        assert request.context is None
        assert request.constraints is None

    def test_valid_request_with_context(self):
        """Test valid request with context information."""
        request_data = {
            "request_id": "req_456",
            "content": "Continue the analysis based on previous findings.",
            "context": {
                "conversation_history": [
                    {
                        "role": "user",
                        "content": "Previous analysis request",
                        "from_agent": "orchestrator",
                        "timestamp": "2025-09-21T10:00:00Z"
                    },
                    {
                        "role": "assistant",
                        "content": "Found potential issue in authentication module",
                        "from_agent": "claude_code",
                        "timestamp": "2025-09-21T10:05:00Z"
                    }
                ],
                "working_directory": "/workspace",
                "allowed_files": ["/workspace/src/auth.py", "/workspace/tests/test_auth.py"],
                "session_metadata": {
                    "session_id": "session_abc",
                    "topic": "Security analysis",
                    "turn_number": 3
                }
            }
        }

        request = ProcessRequestRequest(**request_data)

        assert request.request_id == "req_456"
        assert len(request.context.conversation_history) == 2
        assert request.context.working_directory == "/workspace"
        assert len(request.context.allowed_files) == 2
        assert request.context.session_metadata.session_id == "session_abc"

    def test_valid_request_with_constraints(self):
        """Test valid request with execution constraints."""
        request_data = {
            "request_id": "req_789",
            "content": "Run security tests on the authentication module.",
            "constraints": {
                "max_execution_time_ms": 60000,
                "max_cost_usd": 0.25,
                "allowed_tools": ["read_file", "run_test", "analyze_code"],
                "disallowed_tools": ["network_request", "install_package"],
                "permission_mode": "auto"
            }
        }

        request = ProcessRequestRequest(**request_data)

        assert request.constraints.max_execution_time_ms == 60000
        assert request.constraints.max_cost_usd == 0.25
        assert "read_file" in request.constraints.allowed_tools
        assert "network_request" in request.constraints.disallowed_tools
        assert request.constraints.permission_mode == "auto"

    def test_invalid_request_empty_request_id(self):
        """Test that empty request_id is rejected."""
        request_data = {
            "request_id": "",
            "content": "Test content"
        }

        with pytest.raises(ValidationError) as exc_info:
            ProcessRequestRequest(**request_data)

        assert "String should have at least 1 character" in str(exc_info.value)

    def test_invalid_request_empty_content(self):
        """Test that empty content is rejected."""
        request_data = {
            "request_id": "req_123",
            "content": ""
        }

        with pytest.raises(ValidationError) as exc_info:
            ProcessRequestRequest(**request_data)

        assert "String should have at least 1 character" in str(exc_info.value)

    def test_invalid_request_content_too_long(self):
        """Test that content exceeding max length is rejected."""
        request_data = {
            "request_id": "req_123",
            "content": "x" * 50001  # Exceeds 50000 char limit
        }

        with pytest.raises(ValidationError) as exc_info:
            ProcessRequestRequest(**request_data)

        assert "String should have at most 50000 characters" in str(exc_info.value)

    def test_invalid_conversation_history_role(self):
        """Test that invalid conversation history roles are rejected."""
        request_data = {
            "request_id": "req_123",
            "content": "Test content",
            "context": {
                "conversation_history": [
                    {
                        "role": "invalid_role",
                        "content": "Test",
                        "from_agent": "test_agent",
                        "timestamp": "2025-09-21T10:00:00Z"
                    }
                ]
            }
        }

        with pytest.raises(ValidationError) as exc_info:
            ProcessRequestRequest(**request_data)

        error_str = str(exc_info.value)
        assert "Input should be 'user' or 'assistant'" in error_str

    def test_invalid_constraints_negative_time(self):
        """Test that negative execution time is rejected."""
        request_data = {
            "request_id": "req_123",
            "content": "Test content",
            "constraints": {
                "max_execution_time_ms": 500  # Below minimum of 1000
            }
        }

        with pytest.raises(ValidationError) as exc_info:
            ProcessRequestRequest(**request_data)

        assert "Input should be greater than or equal to 1000" in str(exc_info.value)

    def test_invalid_constraints_negative_cost(self):
        """Test that negative cost is rejected."""
        request_data = {
            "request_id": "req_123",
            "content": "Test content",
            "constraints": {
                "max_cost_usd": -0.1
            }
        }

        with pytest.raises(ValidationError) as exc_info:
            ProcessRequestRequest(**request_data)

        assert "Input should be greater than or equal to 0.001" in str(exc_info.value)

    def test_invalid_permission_mode(self):
        """Test that invalid permission modes are rejected."""
        request_data = {
            "request_id": "req_123",
            "content": "Test content",
            "constraints": {
                "permission_mode": "invalid_mode"
            }
        }

        with pytest.raises(ValidationError) as exc_info:
            ProcessRequestRequest(**request_data)

        error_str = str(exc_info.value)
        valid_modes = ["auto", "prompt", "deny"]
        for mode in valid_modes:
            assert mode in error_str

    def test_valid_response_minimal(self):
        """Test valid response with minimal required fields."""
        response_data = {
            "request_id": "req_123",
            "status": "completed",
            "response": {
                "content": "Analysis completed. Found 2 potential race conditions."
            },
            "metadata": {}
        }

        response = ProcessRequestResponse(**response_data)

        assert response.request_id == "req_123"
        assert response.status == "completed"
        assert response.response.content.startswith("Analysis completed")
        assert response.response.reasoning is None

    def test_valid_response_full(self):
        """Test valid response with all fields."""
        response_data = {
            "request_id": "req_456",
            "status": "completed",
            "response": {
                "content": "Comprehensive security analysis completed.",
                "reasoning": "Applied static analysis and pattern matching to identify vulnerabilities.",
                "confidence": 0.85,
                "next_action_suggested": "Run dynamic tests to confirm findings",
                "evidence": [
                    {
                        "type": "code_snippet",
                        "source": "src/auth.py:45",
                        "content": "if user.is_authenticated and user.has_permission:"
                    },
                    {
                        "type": "test_result",
                        "source": "test_auth.py",
                        "content": "Race condition test failed after 100 iterations"
                    }
                ]
            },
            "metadata": {
                "execution_time_ms": 5500,
                "cost_usd": 0.12,
                "tokens_used": 450,
                "tools_used": ["read_file", "analyze_code", "run_test"],
                "files_accessed": ["src/auth.py", "tests/test_auth.py"]
            },
            "convergence_signals": {
                "solution_proposed": True,
                "consensus_reached": False,
                "requires_verification": True,
                "additional_input_needed": False,
                "confidence_threshold_met": True
            }
        }

        response = ProcessRequestResponse(**response_data)

        assert response.response.confidence == 0.85
        assert len(response.response.evidence) == 2
        assert response.metadata.execution_time_ms == 5500
        assert len(response.metadata.tools_used) == 3
        assert response.convergence_signals.solution_proposed is True

    def test_invalid_response_status(self):
        """Test that invalid response status values are rejected."""
        response_data = {
            "request_id": "req_123",
            "status": "invalid_status",
            "response": {"content": "Test"},
            "metadata": {}
        }

        with pytest.raises(ValidationError) as exc_info:
            ProcessRequestResponse(**response_data)

        error_str = str(exc_info.value)
        valid_statuses = ["completed", "failed", "timeout", "permission_denied"]
        for status in valid_statuses:
            assert status in error_str

    def test_invalid_confidence_range(self):
        """Test that confidence outside valid range is rejected."""
        for invalid_confidence in [-0.1, 1.1]:
            response_data = {
                "request_id": "req_123",
                "status": "completed",
                "response": {
                    "content": "Test",
                    "confidence": invalid_confidence
                },
                "metadata": {}
            }

            with pytest.raises(ValidationError) as exc_info:
                ProcessRequestResponse(**response_data)

            if invalid_confidence < 0:
                assert "Input should be greater than or equal to 0" in str(exc_info.value)
            else:
                assert "Input should be less than or equal to 1" in str(exc_info.value)

    @pytest.mark.integration
    def test_agent_interface_not_implemented(self):
        """Test that the agent interface is not yet implemented."""
        with pytest.raises(ImportError):
            from tab.services.base_agent_adapter import BaseAgentAdapter

        assert False, "Agent interface not yet implemented"

    def test_json_serialization(self):
        """Test JSON serialization."""
        request_data = {
            "request_id": "req_test",
            "content": "Test request",
            "context": {
                "working_directory": "/workspace",
                "session_metadata": {
                    "session_id": "session_test",
                    "topic": "Test topic",
                    "turn_number": 1
                }
            },
            "constraints": {
                "max_execution_time_ms": 30000,
                "permission_mode": "auto"
            }
        }

        request = ProcessRequestRequest(**request_data)
        request_json = request.model_dump_json()
        parsed_request = ProcessRequestRequest.model_validate_json(request_json)

        assert parsed_request.request_id == "req_test"
        assert parsed_request.context.working_directory == "/workspace"
        assert parsed_request.constraints.permission_mode == "auto"

        response_data = {
            "request_id": "req_test",
            "status": "completed",
            "response": {
                "content": "Test response",
                "confidence": 0.9
            },
            "metadata": {
                "execution_time_ms": 2000,
                "cost_usd": 0.05
            }
        }

        response = ProcessRequestResponse(**response_data)
        response_json = response.model_dump_json()
        parsed_response = ProcessRequestResponse.model_validate_json(response_json)

        assert parsed_response.request_id == "req_test"
        assert parsed_response.response.confidence == 0.9
        assert parsed_response.metadata.cost_usd == 0.05