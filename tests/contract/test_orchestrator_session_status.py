"""Contract test for get_session_status MCP tool."""

import pytest
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ValidationError


class GetSessionStatusRequest(BaseModel):
    """Request schema for get_session_status MCP tool."""

    session_id: str
    include_history: bool = False


class BudgetRemaining(BaseModel):
    """Budget remaining schema."""

    cost_usd: float
    turns: int


class TurnHistoryItem(BaseModel):
    """Turn history item schema."""

    turn_id: str
    from_agent: str
    to_agent: str
    content: str
    timestamp: str
    metadata: Optional[dict] = None


class GetSessionStatusResponse(BaseModel):
    """Response schema for get_session_status MCP tool."""

    session_id: str
    status: str
    participants: list[str]
    current_turn: int
    total_cost_usd: float
    created_at: str
    updated_at: str
    budget_remaining: Optional[BudgetRemaining] = None
    turn_history: Optional[list[TurnHistoryItem]] = None


class TestGetSessionStatusContract:
    """Contract tests for get_session_status MCP tool."""

    def test_valid_request_minimal(self):
        """Test valid request with only required fields."""
        request_data = {
            "session_id": "session_123"
        }

        request = GetSessionStatusRequest(**request_data)

        assert request.session_id == "session_123"
        assert request.include_history is False  # Default value

    def test_valid_request_with_history(self):
        """Test valid request including history."""
        request_data = {
            "session_id": "session_456",
            "include_history": True
        }

        request = GetSessionStatusRequest(**request_data)

        assert request.session_id == "session_456"
        assert request.include_history is True

    def test_invalid_session_id_empty(self):
        """Test that empty session_id is rejected."""
        request_data = {
            "session_id": ""
        }

        with pytest.raises(ValidationError) as exc_info:
            GetSessionStatusRequest(**request_data)

        assert "String should have at least 1 character" in str(exc_info.value)

    def test_valid_response_minimal(self):
        """Test valid response without optional fields."""
        response_data = {
            "session_id": "session_123",
            "status": "active",
            "participants": ["claude_code", "codex_cli"],
            "current_turn": 3,
            "total_cost_usd": 0.25,
            "created_at": "2025-09-21T10:00:00Z",
            "updated_at": "2025-09-21T10:15:00Z"
        }

        response = GetSessionStatusResponse(**response_data)

        assert response.session_id == "session_123"
        assert response.status == "active"
        assert response.participants == ["claude_code", "codex_cli"]
        assert response.current_turn == 3
        assert response.total_cost_usd == 0.25
        assert response.budget_remaining is None
        assert response.turn_history is None

    def test_valid_response_with_budget(self):
        """Test valid response with budget information."""
        response_data = {
            "session_id": "session_123",
            "status": "active",
            "participants": ["claude_code", "codex_cli"],
            "current_turn": 2,
            "total_cost_usd": 0.15,
            "created_at": "2025-09-21T10:00:00Z",
            "updated_at": "2025-09-21T10:10:00Z",
            "budget_remaining": {
                "cost_usd": 0.85,
                "turns": 6
            }
        }

        response = GetSessionStatusResponse(**response_data)

        assert response.budget_remaining.cost_usd == 0.85
        assert response.budget_remaining.turns == 6

    def test_valid_response_with_history(self):
        """Test valid response with turn history."""
        response_data = {
            "session_id": "session_123",
            "status": "completed",
            "participants": ["claude_code", "codex_cli"],
            "current_turn": 4,
            "total_cost_usd": 0.45,
            "created_at": "2025-09-21T10:00:00Z",
            "updated_at": "2025-09-21T10:20:00Z",
            "turn_history": [
                {
                    "turn_id": "turn_1",
                    "from_agent": "orchestrator",
                    "to_agent": "claude_code",
                    "content": "Analyze this code for race conditions",
                    "timestamp": "2025-09-21T10:00:30Z",
                    "metadata": {"cost_usd": 0.05}
                },
                {
                    "turn_id": "turn_2",
                    "from_agent": "claude_code",
                    "to_agent": "codex_cli",
                    "content": "I found potential race condition in line 45",
                    "timestamp": "2025-09-21T10:05:00Z",
                    "metadata": {"cost_usd": 0.15, "tokens": 120}
                }
            ]
        }

        response = GetSessionStatusResponse(**response_data)

        assert len(response.turn_history) == 2
        assert response.turn_history[0].turn_id == "turn_1"
        assert response.turn_history[0].from_agent == "orchestrator"
        assert response.turn_history[1].from_agent == "claude_code"
        assert response.turn_history[1].metadata["tokens"] == 120

    def test_invalid_status_value(self):
        """Test that invalid status values are rejected."""
        response_data = {
            "session_id": "session_123",
            "status": "invalid_status",
            "participants": ["claude_code"],
            "current_turn": 1,
            "total_cost_usd": 0.1,
            "created_at": "2025-09-21T10:00:00Z",
            "updated_at": "2025-09-21T10:00:00Z"
        }

        with pytest.raises(ValidationError) as exc_info:
            GetSessionStatusResponse(**response_data)

        error_str = str(exc_info.value)
        valid_statuses = ["active", "completed", "failed", "timeout"]
        for status in valid_statuses:
            assert status in error_str

    def test_invalid_negative_current_turn(self):
        """Test that negative current_turn is rejected."""
        response_data = {
            "session_id": "session_123",
            "status": "active",
            "participants": ["claude_code"],
            "current_turn": -1,
            "total_cost_usd": 0.1,
            "created_at": "2025-09-21T10:00:00Z",
            "updated_at": "2025-09-21T10:00:00Z"
        }

        with pytest.raises(ValidationError) as exc_info:
            GetSessionStatusResponse(**response_data)

        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_invalid_negative_cost(self):
        """Test that negative costs are rejected."""
        response_data = {
            "session_id": "session_123",
            "status": "active",
            "participants": ["claude_code"],
            "current_turn": 1,
            "total_cost_usd": -0.1,
            "created_at": "2025-09-21T10:00:00Z",
            "updated_at": "2025-09-21T10:00:00Z"
        }

        with pytest.raises(ValidationError) as exc_info:
            GetSessionStatusResponse(**response_data)

        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_invalid_budget_remaining_negative(self):
        """Test that negative budget values are rejected."""
        response_data = {
            "session_id": "session_123",
            "status": "active",
            "participants": ["claude_code"],
            "current_turn": 1,
            "total_cost_usd": 0.1,
            "created_at": "2025-09-21T10:00:00Z",
            "updated_at": "2025-09-21T10:00:00Z",
            "budget_remaining": {
                "cost_usd": -0.5,
                "turns": 5
            }
        }

        with pytest.raises(ValidationError) as exc_info:
            GetSessionStatusResponse(**response_data)

        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    @pytest.mark.integration
    def test_mcp_tool_not_implemented(self):
        """Test that the MCP tool is not yet implemented."""
        with pytest.raises(ImportError):
            from tab.services.mcp_orchestrator_server import get_session_status

        assert False, "get_session_status MCP tool not yet implemented"

    def test_json_serialization(self):
        """Test JSON serialization."""
        request_data = {
            "session_id": "session_test",
            "include_history": True
        }

        request = GetSessionStatusRequest(**request_data)
        request_json = request.model_dump_json()
        parsed_request = GetSessionStatusRequest.model_validate_json(request_json)

        assert parsed_request.session_id == "session_test"
        assert parsed_request.include_history is True

        response_data = {
            "session_id": "session_test",
            "status": "active",
            "participants": ["claude_code", "codex_cli"],
            "current_turn": 2,
            "total_cost_usd": 0.20,
            "created_at": "2025-09-21T10:00:00Z",
            "updated_at": "2025-09-21T10:10:00Z",
            "budget_remaining": {
                "cost_usd": 0.80,
                "turns": 6
            }
        }

        response = GetSessionStatusResponse(**response_data)
        response_json = response.model_dump_json()
        parsed_response = GetSessionStatusResponse.model_validate_json(response_json)

        assert parsed_response.session_id == "session_test"
        assert parsed_response.current_turn == 2
        assert parsed_response.budget_remaining.cost_usd == 0.80