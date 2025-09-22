"""Service configuration models for enhanced dependency injection.

Provides configuration models for service container management,
dependency injection, and service lifecycle configuration.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, validator


class ServiceContainerConfig(BaseModel):
    """Configuration for service dependency injection container."""

    # Service-specific configurations
    session_manager: Dict[str, Any] = Field(default_factory=dict)
    policy_enforcer: Dict[str, Any] = Field(default_factory=dict)
    conversation_orchestrator: Dict[str, Any] = Field(default_factory=dict)

    # Service interface settings
    async_adapter_pool_size: int = Field(default=20, ge=1, le=100)
    circuit_breaker_threshold: int = Field(default=5, ge=1)
    health_check_interval: int = Field(default=60, ge=10)

    # Observability settings
    trace_service_calls: bool = Field(default=True)
    log_service_errors: bool = Field(default=True)
    metrics_collection: bool = Field(default=True)

    # Startup and lifecycle configuration
    service_startup_timeout: int = Field(default=30, ge=5)
    graceful_shutdown_timeout: int = Field(default=10, ge=1)
    dependency_injection_validation: bool = Field(default=True)


class ServiceRegistration(BaseModel):
    """Model for service registration in container."""

    service_id: str = Field(..., min_length=1)
    interface_type: str = Field(..., min_length=1)
    implementation_class: str = Field(..., min_length=1)
    config_section: str = Field(..., min_length=1)
    singleton: bool = Field(default=True)
    initialization_order: int = Field(default=100, ge=1)
    health_check_enabled: bool = Field(default=True)
    dependencies: List[str] = Field(default_factory=list)

    @validator('dependencies')
    def validate_no_circular_dependencies(cls, v, values):
        """Basic validation to prevent obvious circular dependencies."""
        service_id = values.get('service_id')
        if service_id and service_id in v:
            raise ValueError(f"Service {service_id} cannot depend on itself")
        return v


class ServiceHealthStatus(BaseModel):
    """Model for service health status tracking."""

    service_id: str
    status: str = Field(..., pattern="^(healthy|unhealthy|unknown|initializing)$")
    last_check: datetime = Field(default_factory=datetime.utcnow)
    error_count: int = Field(default=0, ge=0)
    uptime_seconds: float = Field(default=0.0, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ServiceLifecycleConfig(BaseModel):
    """Configuration for service lifecycle management."""

    auto_restart: bool = Field(default=False)
    restart_delay_seconds: int = Field(default=5, ge=1)
    max_restart_attempts: int = Field(default=3, ge=0)
    health_check_enabled: bool = Field(default=True)
    startup_checks: List[str] = Field(default_factory=list)
    shutdown_hooks: List[str] = Field(default_factory=list)


class DependencyInjectionConfig(BaseModel):
    """Configuration for dependency injection behavior."""

    strict_typing: bool = Field(default=True)
    auto_wire_services: bool = Field(default=True)
    validate_dependencies: bool = Field(default=True)
    lazy_initialization: bool = Field(default=False)
    circular_dependency_detection: bool = Field(default=True)


class ServiceMetricsConfig(BaseModel):
    """Configuration for service performance metrics."""

    enable_metrics: bool = Field(default=True)
    metric_collection_interval: int = Field(default=30, ge=10)
    performance_thresholds: Dict[str, float] = Field(default_factory=dict)
    alert_on_threshold_breach: bool = Field(default=True)

    # Default performance thresholds
    def __init__(self, **data):
        if 'performance_thresholds' not in data:
            data['performance_thresholds'] = {
                "response_time_ms": 1000.0,
                "error_rate_percent": 5.0,
                "memory_usage_mb": 512.0,
                "cpu_usage_percent": 80.0
            }
        super().__init__(**data)


class ServiceContainerState(BaseModel):
    """Model for tracking service container state."""

    container_id: str = Field(default_factory=lambda: f"container_{datetime.utcnow().timestamp()}")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    services_registered: int = Field(default=0, ge=0)
    services_initialized: int = Field(default=0, ge=0)
    services_healthy: int = Field(default=0, ge=0)
    last_health_check: Optional[datetime] = None
    configuration_version: str = Field(default="1.0.0")

    @property
    def is_ready(self) -> bool:
        """Check if container is ready to serve requests."""
        return self.services_initialized == self.services_registered and self.services_healthy == self.services_registered


def create_default_service_container_config() -> ServiceContainerConfig:
    """Create a default service container configuration."""
    return ServiceContainerConfig(
        session_manager={
            "storage_directory": "~/.tab/sessions",
            "auto_cleanup_enabled": True,
            "cleanup_interval_hours": 24
        },
        policy_enforcer={
            "default_policy": "default",
            "strict_validation": True
        },
        conversation_orchestrator={
            "max_concurrent_conversations": 10,
            "turn_timeout_seconds": 120
        },
        async_adapter_pool_size=20,
        circuit_breaker_threshold=5,
        health_check_interval=60,
        trace_service_calls=True,
        log_service_errors=True,
        metrics_collection=True
    )