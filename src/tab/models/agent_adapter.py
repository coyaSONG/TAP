"""AgentAdapter model with capability definitions."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class AgentType(str, Enum):
    """Agent type enumeration."""

    CLAUDE_CODE = "claude_code"
    CODEX_CLI = "codex_cli"
    GENERIC = "generic"


class AgentStatus(str, Enum):
    """Agent status enumeration."""

    AVAILABLE = "available"
    BUSY = "busy"
    FAILED = "failed"
    MAINTENANCE = "maintenance"


class ConnectionType(str, Enum):
    """Connection type enumeration."""

    MCP = "mcp"
    CLI = "cli"
    API = "api"
    SUBPROCESS = "subprocess"


class ConnectionConfig(BaseModel):
    """Connection configuration for agent communication."""

    type: ConnectionType = Field(..., description="Type of connection")
    endpoint: Optional[str] = Field(None, description="Connection endpoint (URL, path, etc.)")
    timeout_seconds: int = Field(default=30, ge=1, le=300, description="Connection timeout")
    retry_attempts: int = Field(default=3, ge=0, le=10, description="Number of retry attempts")
    auth_config: Dict[str, Any] = Field(default_factory=dict, description="Authentication configuration")


class ExecutionLimits(BaseModel):
    """Resource and time limits for agent execution."""

    max_execution_time_seconds: int = Field(default=120, ge=1, le=600, description="Maximum execution time")
    max_cost_usd: float = Field(default=0.5, ge=0.001, le=10.0, description="Maximum cost per request")
    max_memory_mb: int = Field(default=512, ge=64, le=4096, description="Maximum memory usage")
    max_concurrent_requests: int = Field(default=3, ge=1, le=10, description="Maximum concurrent requests")


class AgentCapability(BaseModel):
    """Individual agent capability definition."""

    name: str = Field(..., description="Capability name")
    description: str = Field(..., description="Capability description")
    tools_required: List[str] = Field(default_factory=list, description="Tools required for this capability")
    resource_cost: float = Field(default=0.1, ge=0.0, description="Relative resource cost")
    confidence_level: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence level for this capability")


class SessionManagerConfig(BaseModel):
    """Session management configuration."""

    enable_session_resumption: bool = Field(default=True, description="Enable session resumption")
    session_timeout_minutes: int = Field(default=60, ge=5, le=480, description="Session timeout")
    max_concurrent_sessions: int = Field(default=5, ge=1, le=20, description="Maximum concurrent sessions")
    context_preservation: bool = Field(default=True, description="Preserve conversation context")


class AgentAdapter(BaseModel):
    """
    Interface wrapper for each CLI tool providing standardized communication protocol.

    Manages agent lifecycle, capabilities, and connection configuration.
    """

    agent_id: str = Field(..., description="Unique identifier for the agent")
    agent_type: AgentType = Field(..., description="Type of agent")
    name: str = Field(..., description="Human-readable agent name")
    version: str = Field(..., description="Agent version or CLI version")
    capabilities: List[AgentCapability] = Field(default_factory=list, description="List of supported operations/tools")
    connection_config: ConnectionConfig = Field(..., description="Connection configuration")
    status: AgentStatus = Field(default=AgentStatus.AVAILABLE, description="Current agent status")
    last_health_check: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of last successful health check")
    session_manager: SessionManagerConfig = Field(default_factory=SessionManagerConfig, description="Session management configuration")
    execution_limits: ExecutionLimits = Field(default_factory=ExecutionLimits, description="Resource and time limits")

    # Health and performance tracking
    uptime_seconds: int = Field(default=0, ge=0, description="Agent uptime in seconds")
    total_requests_processed: int = Field(default=0, ge=0, description="Total requests processed")
    successful_requests: int = Field(default=0, ge=0, description="Successful requests")
    failed_requests: int = Field(default=0, ge=0, description="Failed requests")
    average_response_time_ms: float = Field(default=0.0, ge=0.0, description="Average response time")
    last_error: Optional[str] = Field(None, description="Last error message")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional agent metadata")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @field_validator('agent_id')
    @classmethod
    def validate_agent_id(cls, v):
        """Validate agent ID is unique and non-empty."""
        if not v.strip():
            raise ValueError("agent_id cannot be empty")
        return v.strip()

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate agent name."""
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()

    @field_validator('version')
    @classmethod
    def validate_version(cls, v):
        """Validate version string."""
        if not v.strip():
            raise ValueError("version cannot be empty")
        return v.strip()

    def transition_status(self, new_status: AgentStatus, reason: Optional[str] = None) -> bool:
        """
        Transition agent status following defined state machine.

        Args:
            new_status: Target status
            reason: Optional reason for transition

        Returns:
            True if transition was successful
        """
        valid_transitions = {
            AgentStatus.AVAILABLE: [AgentStatus.BUSY, AgentStatus.FAILED, AgentStatus.MAINTENANCE],
            AgentStatus.BUSY: [AgentStatus.AVAILABLE, AgentStatus.FAILED],
            AgentStatus.FAILED: [AgentStatus.AVAILABLE, AgentStatus.MAINTENANCE],
            AgentStatus.MAINTENANCE: [AgentStatus.AVAILABLE, AgentStatus.FAILED]
        }

        if new_status not in valid_transitions.get(self.status, []):
            return False

        old_status = self.status
        self.status = new_status

        # Record transition in metadata
        if 'status_transitions' not in self.metadata:
            self.metadata['status_transitions'] = []

        self.metadata['status_transitions'].append({
            'from_status': old_status,
            'to_status': new_status,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'reason': reason
        })

        return True

    def update_health_check(self, success: bool, error_message: Optional[str] = None) -> None:
        """
        Update health check status.

        Args:
            success: Whether health check was successful
            error_message: Error message if health check failed
        """
        self.last_health_check = datetime.now(timezone.utc)

        if success:
            if self.status == AgentStatus.FAILED:
                self.transition_status(AgentStatus.AVAILABLE, "Health check recovered")
            self.last_error = None
        else:
            self.last_error = error_message
            if self.status != AgentStatus.MAINTENANCE:
                self.transition_status(AgentStatus.FAILED, f"Health check failed: {error_message}")

    def record_request(self, success: bool, response_time_ms: int, error_message: Optional[str] = None) -> None:
        """
        Record a request for performance tracking.

        Args:
            success: Whether request was successful
            response_time_ms: Response time in milliseconds
            error_message: Error message if request failed
        """
        self.total_requests_processed += 1

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            self.last_error = error_message

        # Update average response time
        if self.total_requests_processed == 1:
            self.average_response_time_ms = float(response_time_ms)
        else:
            # Running average calculation
            self.average_response_time_ms = (
                (self.average_response_time_ms * (self.total_requests_processed - 1) + response_time_ms) /
                self.total_requests_processed
            )

    def add_capability(self, name: str, description: str, tools_required: List[str] = None, resource_cost: float = 0.1, confidence_level: float = 0.8) -> bool:
        """
        Add a new capability to the agent.

        Args:
            name: Capability name
            description: Capability description
            tools_required: Required tools
            resource_cost: Resource cost
            confidence_level: Confidence level

        Returns:
            True if capability was added, False if it already exists
        """
        # Check if capability already exists
        if any(cap.name == name for cap in self.capabilities):
            return False

        capability = AgentCapability(
            name=name,
            description=description,
            tools_required=tools_required or [],
            resource_cost=resource_cost,
            confidence_level=confidence_level
        )

        self.capabilities.append(capability)
        return True

    def has_capability(self, capability_name: str) -> bool:
        """Check if agent has a specific capability."""
        return any(cap.name == capability_name for cap in self.capabilities)

    def get_capability_names(self) -> List[str]:
        """Get list of capability names."""
        return [cap.name for cap in self.capabilities]

    def is_healthy(self) -> bool:
        """Check if agent is healthy and available."""
        return self.status in [AgentStatus.AVAILABLE, AgentStatus.BUSY]

    def get_success_rate(self) -> float:
        """Calculate request success rate."""
        if self.total_requests_processed == 0:
            return 1.0
        return self.successful_requests / self.total_requests_processed

    def to_health_status(self) -> Dict[str, Any]:
        """Generate health status report."""
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "last_health_check": self.last_health_check.isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "success_rate": self.get_success_rate(),
            "average_response_time_ms": self.average_response_time_ms,
            "total_requests": self.total_requests_processed,
            "last_error": self.last_error,
            "capabilities": len(self.capabilities)
        }