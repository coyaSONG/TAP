"""Contract test for agent health_check interface."""

import pytest
from typing import Optional

from pydantic import BaseModel, ValidationError


class HealthCheckRequest(BaseModel):
    """Request schema for health_check agent interface."""

    deep_check: bool = False


class ResourceUsage(BaseModel):
    """Resource usage schema."""

    cpu_percent: float
    memory_mb: float
    active_sessions: int


class HealthCheckResponse(BaseModel):
    """Response schema for health_check agent interface."""

    status: str
    version: str
    capabilities: list[str]
    resource_usage: Optional[ResourceUsage] = None
    last_error: Optional[str] = None
    uptime_seconds: Optional[int] = None


class TestAgentHealthCheckContract:
    """Contract tests for agent health_check interface."""

    def test_valid_request_default(self):
        """Test valid request with default values."""
        request_data = {}

        request = HealthCheckRequest(**request_data)

        assert request.deep_check is False

    def test_valid_request_deep_check(self):
        """Test valid request with deep check enabled."""
        request_data = {
            "deep_check": True
        }

        request = HealthCheckRequest(**request_data)

        assert request.deep_check is True

    def test_valid_response_minimal(self):
        """Test valid response with minimal required fields."""
        response_data = {
            "status": "healthy",
            "version": "2.1.0",
            "capabilities": [
                "code_analysis",
                "bug_detection",
                "test_generation"
            ]
        }

        response = HealthCheckResponse(**response_data)

        assert response.status == "healthy"
        assert response.version == "2.1.0"
        assert len(response.capabilities) == 3
        assert "code_analysis" in response.capabilities
        assert response.resource_usage is None
        assert response.last_error is None
        assert response.uptime_seconds is None

    def test_valid_response_with_resource_usage(self):
        """Test valid response including resource usage."""
        response_data = {
            "status": "healthy",
            "version": "1.5.2",
            "capabilities": [
                "code_execution",
                "test_running",
                "build_automation"
            ],
            "resource_usage": {
                "cpu_percent": 15.5,
                "memory_mb": 256.8,
                "active_sessions": 2
            },
            "uptime_seconds": 3600
        }

        response = HealthCheckResponse(**response_data)

        assert response.status == "healthy"
        assert response.resource_usage.cpu_percent == 15.5
        assert response.resource_usage.memory_mb == 256.8
        assert response.resource_usage.active_sessions == 2
        assert response.uptime_seconds == 3600

    def test_valid_response_degraded_with_error(self):
        """Test valid response for degraded status with error."""
        response_data = {
            "status": "degraded",
            "version": "2.0.1",
            "capabilities": [
                "code_analysis"
            ],
            "resource_usage": {
                "cpu_percent": 85.2,
                "memory_mb": 1024.0,
                "active_sessions": 5
            },
            "last_error": "Memory usage approaching limit",
            "uptime_seconds": 86400
        }

        response = HealthCheckResponse(**response_data)

        assert response.status == "degraded"
        assert response.last_error == "Memory usage approaching limit"
        assert response.resource_usage.cpu_percent == 85.2
        assert len(response.capabilities) == 1

    def test_valid_response_unhealthy(self):
        """Test valid response for unhealthy status."""
        response_data = {
            "status": "unhealthy",
            "version": "1.8.0",
            "capabilities": [],
            "last_error": "Connection to underlying service failed",
            "uptime_seconds": 120
        }

        response = HealthCheckResponse(**response_data)

        assert response.status == "unhealthy"
        assert len(response.capabilities) == 0
        assert response.last_error.startswith("Connection to underlying")

    def test_invalid_status_value(self):
        """Test that invalid status values are rejected."""
        response_data = {
            "status": "invalid_status",
            "version": "1.0.0",
            "capabilities": ["test"]
        }

        with pytest.raises(ValidationError) as exc_info:
            HealthCheckResponse(**response_data)

        error_str = str(exc_info.value)
        valid_statuses = ["healthy", "degraded", "unhealthy"]
        for status in valid_statuses:
            assert status in error_str

    def test_invalid_empty_version(self):
        """Test that empty version is rejected."""
        response_data = {
            "status": "healthy",
            "version": "",
            "capabilities": ["test"]
        }

        with pytest.raises(ValidationError) as exc_info:
            HealthCheckResponse(**response_data)

        assert "String should have at least 1 character" in str(exc_info.value)

    def test_invalid_negative_cpu_percent(self):
        """Test that negative CPU percentage is rejected."""
        response_data = {
            "status": "healthy",
            "version": "1.0.0",
            "capabilities": ["test"],
            "resource_usage": {
                "cpu_percent": -5.0,
                "memory_mb": 100.0,
                "active_sessions": 1
            }
        }

        with pytest.raises(ValidationError) as exc_info:
            HealthCheckResponse(**response_data)

        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_invalid_negative_memory(self):
        """Test that negative memory usage is rejected."""
        response_data = {
            "status": "healthy",
            "version": "1.0.0",
            "capabilities": ["test"],
            "resource_usage": {
                "cpu_percent": 10.0,
                "memory_mb": -50.0,
                "active_sessions": 1
            }
        }

        with pytest.raises(ValidationError) as exc_info:
            HealthCheckResponse(**response_data)

        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_invalid_negative_active_sessions(self):
        """Test that negative active sessions is rejected."""
        response_data = {
            "status": "healthy",
            "version": "1.0.0",
            "capabilities": ["test"],
            "resource_usage": {
                "cpu_percent": 10.0,
                "memory_mb": 100.0,
                "active_sessions": -1
            }
        }

        with pytest.raises(ValidationError) as exc_info:
            HealthCheckResponse(**response_data)

        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_invalid_negative_uptime(self):
        """Test that negative uptime is rejected."""
        response_data = {
            "status": "healthy",
            "version": "1.0.0",
            "capabilities": ["test"],
            "uptime_seconds": -100
        }

        with pytest.raises(ValidationError) as exc_info:
            HealthCheckResponse(**response_data)

        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_status_capabilities_correlation(self):
        """Test different status levels with appropriate capabilities."""
        # Healthy agent should have capabilities
        healthy_response = {
            "status": "healthy",
            "version": "1.0.0",
            "capabilities": ["code_analysis", "test_generation"]
        }

        response = HealthCheckResponse(**healthy_response)
        assert len(response.capabilities) > 0

        # Unhealthy agent may have no capabilities
        unhealthy_response = {
            "status": "unhealthy",
            "version": "1.0.0",
            "capabilities": []
        }

        response = HealthCheckResponse(**unhealthy_response)
        assert len(response.capabilities) == 0

    def test_resource_usage_high_values(self):
        """Test resource usage with high but valid values."""
        response_data = {
            "status": "degraded",
            "version": "1.0.0",
            "capabilities": ["limited_capability"],
            "resource_usage": {
                "cpu_percent": 99.9,
                "memory_mb": 8192.0,
                "active_sessions": 100
            }
        }

        response = HealthCheckResponse(**response_data)
        assert response.resource_usage.cpu_percent == 99.9
        assert response.resource_usage.memory_mb == 8192.0
        assert response.resource_usage.active_sessions == 100

    @pytest.mark.integration
    def test_agent_health_check_not_implemented(self):
        """Test that the agent health check is not yet implemented."""
        with pytest.raises(ImportError):
            from tab.services.base_agent_adapter import BaseAgentAdapter

        assert False, "Agent health_check interface not yet implemented"

    def test_json_serialization(self):
        """Test JSON serialization."""
        request_data = {
            "deep_check": True
        }

        request = HealthCheckRequest(**request_data)
        request_json = request.model_dump_json()
        parsed_request = HealthCheckRequest.model_validate_json(request_json)

        assert parsed_request.deep_check is True

        response_data = {
            "status": "healthy",
            "version": "2.0.0",
            "capabilities": ["analysis", "testing"],
            "resource_usage": {
                "cpu_percent": 25.5,
                "memory_mb": 512.0,
                "active_sessions": 3
            },
            "uptime_seconds": 7200
        }

        response = HealthCheckResponse(**response_data)
        response_json = response.model_dump_json()
        parsed_response = HealthCheckResponse.model_validate_json(response_json)

        assert parsed_response.status == "healthy"
        assert parsed_response.version == "2.0.0"
        assert len(parsed_response.capabilities) == 2
        assert parsed_response.resource_usage.cpu_percent == 25.5
        assert parsed_response.uptime_seconds == 7200

    def test_optional_fields_truly_optional(self):
        """Test that optional fields can be omitted."""
        minimal_response = {
            "status": "healthy",
            "version": "1.0.0",
            "capabilities": ["test"]
        }

        response = HealthCheckResponse(**minimal_response)
        assert response.resource_usage is None
        assert response.last_error is None
        assert response.uptime_seconds is None

    def test_capabilities_can_be_empty(self):
        """Test that capabilities list can be empty."""
        response_data = {
            "status": "unhealthy",
            "version": "1.0.0",
            "capabilities": []
        }

        response = HealthCheckResponse(**response_data)
        assert len(response.capabilities) == 0