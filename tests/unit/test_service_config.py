"""Unit tests for enhanced configuration models.

Tests the new configuration models to ensure they validate correctly
and maintain backward compatibility.
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from src.tab.models.service_config import (
    ServiceContainerConfig, ServiceRegistration, ServiceHealthStatus,
    ServiceLifecycleConfig, DependencyInjectionConfig, ServiceMetricsConfig,
    ServiceContainerState, create_default_service_container_config
)


class TestServiceContainerConfig:
    """Test ServiceContainerConfig model."""

    def test_default_service_container_config_creation(self):
        """Test creating service container config with defaults."""
        config = ServiceContainerConfig()

        assert config.async_adapter_pool_size == 20
        assert config.circuit_breaker_threshold == 5
        assert config.health_check_interval == 60
        assert config.trace_service_calls is True
        assert config.log_service_errors is True
        assert config.metrics_collection is True

    def test_service_container_config_validation(self):
        """Test validation of service container config."""
        # Valid config
        config = ServiceContainerConfig(
            async_adapter_pool_size=50,
            circuit_breaker_threshold=3,
            health_check_interval=30
        )
        assert config.async_adapter_pool_size == 50

        # Invalid pool size (too high)
        with pytest.raises(ValueError):
            ServiceContainerConfig(async_adapter_pool_size=150)

        # Invalid pool size (too low)
        with pytest.raises(ValueError):
            ServiceContainerConfig(async_adapter_pool_size=0)

        # Invalid health check interval
        with pytest.raises(ValueError):
            ServiceContainerConfig(health_check_interval=5)

    def test_service_container_config_nested_configs(self):
        """Test nested service configurations."""
        config = ServiceContainerConfig(
            session_manager={
                "storage_directory": "/custom/path",
                "auto_cleanup_enabled": False
            },
            policy_enforcer={
                "strict_validation": True,
                "default_policy": "custom"
            }
        )

        assert config.session_manager["storage_directory"] == "/custom/path"
        assert config.session_manager["auto_cleanup_enabled"] is False
        assert config.policy_enforcer["strict_validation"] is True


class TestServiceRegistration:
    """Test ServiceRegistration model."""

    def test_service_registration_creation(self):
        """Test creating service registration."""
        registration = ServiceRegistration(
            service_id="test_service",
            interface_type="ITestService",
            implementation_class="TestServiceImpl",
            config_section="test_config",
            initialization_order=50
        )

        assert registration.service_id == "test_service"
        assert registration.singleton is True  # default
        assert registration.health_check_enabled is True  # default
        assert registration.initialization_order == 50

    def test_service_registration_dependency_validation(self):
        """Test dependency validation in service registration."""
        # Valid dependencies
        registration = ServiceRegistration(
            service_id="service_a",
            interface_type="IServiceA",
            implementation_class="ServiceAImpl",
            config_section="service_a",
            dependencies=["service_b", "service_c"]
        )
        assert len(registration.dependencies) == 2

        # Self-dependency should fail
        with pytest.raises(ValueError, match="cannot depend on itself"):
            ServiceRegistration(
                service_id="service_a",
                interface_type="IServiceA",
                implementation_class="ServiceAImpl",
                config_section="service_a",
                dependencies=["service_a"]  # Self-dependency
            )

    def test_service_registration_validation(self):
        """Test field validation for service registration."""
        # Empty service_id should fail
        with pytest.raises(ValueError):
            ServiceRegistration(
                service_id="",
                interface_type="ITestService",
                implementation_class="TestServiceImpl",
                config_section="test"
            )

        # Negative initialization order should fail
        with pytest.raises(ValueError):
            ServiceRegistration(
                service_id="test",
                interface_type="ITestService",
                implementation_class="TestServiceImpl",
                config_section="test",
                initialization_order=0
            )


class TestServiceHealthStatus:
    """Test ServiceHealthStatus model."""

    def test_service_health_status_creation(self):
        """Test creating service health status."""
        status = ServiceHealthStatus(
            service_id="test_service",
            status="healthy"
        )

        assert status.service_id == "test_service"
        assert status.status == "healthy"
        assert status.error_count == 0
        assert status.uptime_seconds == 0.0
        assert isinstance(status.last_check, datetime)

    def test_service_health_status_validation(self):
        """Test status field validation."""
        # Valid statuses
        for valid_status in ["healthy", "unhealthy", "unknown", "initializing"]:
            status = ServiceHealthStatus(
                service_id="test",
                status=valid_status
            )
            assert status.status == valid_status

        # Invalid status should fail
        with pytest.raises(ValueError):
            ServiceHealthStatus(
                service_id="test",
                status="invalid_status"
            )

    def test_service_health_status_metadata(self):
        """Test metadata handling in health status."""
        metadata = {
            "cpu_usage": 45.2,
            "memory_mb": 128,
            "active_connections": 5
        }

        status = ServiceHealthStatus(
            service_id="test",
            status="healthy",
            metadata=metadata
        )

        assert status.metadata["cpu_usage"] == 45.2
        assert status.metadata["memory_mb"] == 128


class TestServiceMetricsConfig:
    """Test ServiceMetricsConfig model."""

    def test_service_metrics_config_defaults(self):
        """Test default performance thresholds."""
        config = ServiceMetricsConfig()

        assert config.enable_metrics is True
        assert config.metric_collection_interval == 30
        assert "response_time_ms" in config.performance_thresholds
        assert "error_rate_percent" in config.performance_thresholds
        assert "memory_usage_mb" in config.performance_thresholds
        assert "cpu_usage_percent" in config.performance_thresholds

        # Check default threshold values
        assert config.performance_thresholds["response_time_ms"] == 1000.0
        assert config.performance_thresholds["error_rate_percent"] == 5.0

    def test_service_metrics_config_custom_thresholds(self):
        """Test custom performance thresholds."""
        custom_thresholds = {
            "response_time_ms": 500.0,
            "error_rate_percent": 2.0,
            "custom_metric": 100.0
        }

        config = ServiceMetricsConfig(
            performance_thresholds=custom_thresholds
        )

        assert config.performance_thresholds["response_time_ms"] == 500.0
        assert config.performance_thresholds["custom_metric"] == 100.0

    def test_service_metrics_config_validation(self):
        """Test validation of metrics configuration."""
        # Invalid collection interval
        with pytest.raises(ValueError):
            ServiceMetricsConfig(metric_collection_interval=5)  # Too low


class TestServiceContainerState:
    """Test ServiceContainerState model."""

    def test_service_container_state_creation(self):
        """Test creating service container state."""
        state = ServiceContainerState()

        assert state.services_registered == 0
        assert state.services_initialized == 0
        assert state.services_healthy == 0
        assert state.configuration_version == "1.0.0"
        assert isinstance(state.started_at, datetime)

    def test_service_container_state_ready_property(self):
        """Test is_ready property logic."""
        state = ServiceContainerState()

        # Not ready when no services
        assert not state.is_ready

        # Not ready when services registered but not initialized
        state.services_registered = 3
        state.services_initialized = 2
        state.services_healthy = 2
        assert not state.is_ready

        # Not ready when initialized but not healthy
        state.services_initialized = 3
        state.services_healthy = 2
        assert not state.is_ready

        # Ready when all services registered, initialized, and healthy
        state.services_healthy = 3
        assert state.is_ready

    def test_service_container_state_validation(self):
        """Test validation of container state fields."""
        # Negative values should fail
        with pytest.raises(ValueError):
            ServiceContainerState(services_registered=-1)

        with pytest.raises(ValueError):
            ServiceContainerState(services_initialized=-1)

        with pytest.raises(ValueError):
            ServiceContainerState(services_healthy=-1)


class TestCreateDefaultServiceContainerConfig:
    """Test the default service container config factory function."""

    def test_create_default_config(self):
        """Test creating default service container configuration."""
        config = create_default_service_container_config()

        assert isinstance(config, ServiceContainerConfig)
        assert config.async_adapter_pool_size == 20
        assert config.trace_service_calls is True

        # Check nested configurations
        assert "storage_directory" in config.session_manager
        assert config.session_manager["auto_cleanup_enabled"] is True

        assert "default_policy" in config.policy_enforcer
        assert config.policy_enforcer["strict_validation"] is True

        assert "max_concurrent_conversations" in config.conversation_orchestrator

    def test_default_config_validation(self):
        """Test that default config passes validation."""
        config = create_default_service_container_config()

        # Should not raise any validation errors
        assert config.async_adapter_pool_size >= 1
        assert config.circuit_breaker_threshold >= 1
        assert config.health_check_interval >= 10


class TestConfigurationIntegration:
    """Test integration between different configuration models."""

    def test_config_model_compatibility(self):
        """Test that configuration models work together."""
        # Create a complete service configuration
        container_config = ServiceContainerConfig(
            async_adapter_pool_size=30,
            health_check_interval=45
        )

        registration = ServiceRegistration(
            service_id="session_manager",
            interface_type="IConversationSessionService",
            implementation_class="SessionManager",
            config_section="session_manager"
        )

        metrics_config = ServiceMetricsConfig(
            enable_metrics=True,
            metric_collection_interval=60
        )

        lifecycle_config = ServiceLifecycleConfig(
            auto_restart=True,
            max_restart_attempts=3
        )

        # All should be valid and work together
        assert container_config.async_adapter_pool_size == 30
        assert registration.service_id == "session_manager"
        assert metrics_config.enable_metrics is True
        assert lifecycle_config.auto_restart is True

    def test_config_serialization_compatibility(self):
        """Test that configurations can be serialized/deserialized."""
        config = create_default_service_container_config()

        # Should be able to convert to dict and back
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)

        # Should be able to recreate from dict
        recreated_config = ServiceContainerConfig(**config_dict)
        assert recreated_config.async_adapter_pool_size == config.async_adapter_pool_size