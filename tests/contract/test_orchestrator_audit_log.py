"""Contract test for export_audit_log MCP tool."""

import pytest
from typing import Optional

from pydantic import BaseModel, ValidationError


class ExportAuditLogRequest(BaseModel):
    """Request schema for export_audit_log MCP tool."""

    session_id: str
    format: str = "json"
    include_security_events: bool = True


class ExportAuditLogResponse(BaseModel):
    """Response schema for export_audit_log MCP tool."""

    audit_data: str
    format: str
    record_count: int
    exported_at: str
    security_events_included: Optional[bool] = None


class TestExportAuditLogContract:
    """Contract tests for export_audit_log MCP tool."""

    def test_valid_request_minimal(self):
        """Test valid request with only required fields."""
        request_data = {
            "session_id": "session_123"
        }

        request = ExportAuditLogRequest(**request_data)

        assert request.session_id == "session_123"
        assert request.format == "json"  # Default value
        assert request.include_security_events is True  # Default value

    def test_valid_request_all_formats(self):
        """Test valid request with all supported formats."""
        formats = ["json", "csv", "jsonl"]

        for fmt in formats:
            request_data = {
                "session_id": "session_123",
                "format": fmt,
                "include_security_events": False
            }

            request = ExportAuditLogRequest(**request_data)

            assert request.session_id == "session_123"
            assert request.format == fmt
            assert request.include_security_events is False

    def test_invalid_session_id_empty(self):
        """Test that empty session_id is rejected."""
        request_data = {
            "session_id": ""
        }

        with pytest.raises(ValidationError) as exc_info:
            ExportAuditLogRequest(**request_data)

        assert "String should have at least 1 character" in str(exc_info.value)

    def test_invalid_format(self):
        """Test that invalid format values are rejected."""
        request_data = {
            "session_id": "session_123",
            "format": "xml"  # Not supported
        }

        with pytest.raises(ValidationError) as exc_info:
            ExportAuditLogRequest(**request_data)

        error_str = str(exc_info.value)
        valid_formats = ["json", "csv", "jsonl"]
        for fmt in valid_formats:
            assert fmt in error_str

    def test_valid_response_json_format(self):
        """Test valid response for JSON format."""
        response_data = {
            "audit_data": '{"records": [{"event": "session_start", "timestamp": "2025-09-21T10:00:00Z"}]}',
            "format": "json",
            "record_count": 15,
            "exported_at": "2025-09-21T10:30:00Z",
            "security_events_included": True
        }

        response = ExportAuditLogResponse(**response_data)

        assert response.audit_data.startswith('{"records":')
        assert response.format == "json"
        assert response.record_count == 15
        assert response.security_events_included is True

    def test_valid_response_csv_format(self):
        """Test valid response for CSV format."""
        csv_data = """timestamp,event_type,agent_id,action,result
2025-09-21T10:00:00Z,session_start,orchestrator,create_session,success
2025-09-21T10:01:00Z,message_send,claude_code,analyze_code,success"""

        response_data = {
            "audit_data": csv_data,
            "format": "csv",
            "record_count": 2,
            "exported_at": "2025-09-21T10:30:00Z",
            "security_events_included": False
        }

        response = ExportAuditLogResponse(**response_data)

        assert "timestamp,event_type" in response.audit_data
        assert response.format == "csv"
        assert response.record_count == 2
        assert response.security_events_included is False

    def test_valid_response_jsonl_format(self):
        """Test valid response for JSONL format."""
        jsonl_data = '''{"timestamp": "2025-09-21T10:00:00Z", "event": "session_start"}
{"timestamp": "2025-09-21T10:01:00Z", "event": "message_send"}'''

        response_data = {
            "audit_data": jsonl_data,
            "format": "jsonl",
            "record_count": 2,
            "exported_at": "2025-09-21T10:30:00Z"
        }

        response = ExportAuditLogResponse(**response_data)

        assert '"event": "session_start"' in response.audit_data
        assert response.format == "jsonl"
        assert response.security_events_included is None

    def test_invalid_response_negative_record_count(self):
        """Test that negative record count is rejected."""
        response_data = {
            "audit_data": "{}",
            "format": "json",
            "record_count": -1,
            "exported_at": "2025-09-21T10:30:00Z"
        }

        with pytest.raises(ValidationError) as exc_info:
            ExportAuditLogResponse(**response_data)

        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_invalid_response_empty_audit_data(self):
        """Test that empty audit_data is rejected."""
        response_data = {
            "audit_data": "",
            "format": "json",
            "record_count": 0,
            "exported_at": "2025-09-21T10:30:00Z"
        }

        with pytest.raises(ValidationError) as exc_info:
            ExportAuditLogResponse(**response_data)

        assert "String should have at least 1 character" in str(exc_info.value)

    def test_response_format_consistency(self):
        """Test that response format matches request format."""
        formats = ["json", "csv", "jsonl"]

        for fmt in formats:
            response_data = {
                "audit_data": "sample_data",
                "format": fmt,
                "record_count": 1,
                "exported_at": "2025-09-21T10:30:00Z"
            }

            response = ExportAuditLogResponse(**response_data)
            assert response.format == fmt

    def test_security_events_included_optional(self):
        """Test that security_events_included is optional in response."""
        response_data = {
            "audit_data": "{}",
            "format": "json",
            "record_count": 0,
            "exported_at": "2025-09-21T10:30:00Z"
        }

        response = ExportAuditLogResponse(**response_data)
        assert response.security_events_included is None

        response_data["security_events_included"] = True
        response = ExportAuditLogResponse(**response_data)
        assert response.security_events_included is True

    @pytest.mark.integration
    def test_mcp_tool_not_implemented(self):
        """Test that the MCP tool is not yet implemented."""
        with pytest.raises(ImportError):
            from tab.services.mcp_orchestrator_server import export_audit_log

        assert False, "export_audit_log MCP tool not yet implemented"

    def test_json_serialization(self):
        """Test JSON serialization."""
        request_data = {
            "session_id": "session_test",
            "format": "jsonl",
            "include_security_events": False
        }

        request = ExportAuditLogRequest(**request_data)
        request_json = request.model_dump_json()
        parsed_request = ExportAuditLogRequest.model_validate_json(request_json)

        assert parsed_request.session_id == "session_test"
        assert parsed_request.format == "jsonl"
        assert parsed_request.include_security_events is False

        response_data = {
            "audit_data": '{"test": "data"}',
            "format": "json",
            "record_count": 5,
            "exported_at": "2025-09-21T10:30:00Z",
            "security_events_included": True
        }

        response = ExportAuditLogResponse(**response_data)
        response_json = response.model_dump_json()
        parsed_response = ExportAuditLogResponse.model_validate_json(response_json)

        assert parsed_response.audit_data == '{"test": "data"}'
        assert parsed_response.record_count == 5
        assert parsed_response.security_events_included is True

    def test_large_audit_data(self):
        """Test handling of large audit data strings."""
        large_data = "x" * 10000  # 10KB of data

        response_data = {
            "audit_data": large_data,
            "format": "json",
            "record_count": 1000,
            "exported_at": "2025-09-21T10:30:00Z"
        }

        response = ExportAuditLogResponse(**response_data)
        assert len(response.audit_data) == 10000
        assert response.record_count == 1000

    def test_zero_record_count_valid(self):
        """Test that zero record count is valid for empty sessions."""
        response_data = {
            "audit_data": "[]",  # Empty JSON array
            "format": "json",
            "record_count": 0,
            "exported_at": "2025-09-21T10:30:00Z"
        }

        response = ExportAuditLogResponse(**response_data)
        assert response.record_count == 0
        assert response.audit_data == "[]"