"""AuditRecord model with security context."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    """Audit event type enumeration."""

    ACTION = "action"
    DECISION = "decision"
    ERROR = "error"
    SECURITY = "security"
    PERFORMANCE = "performance"
    POLICY = "policy"
    SESSION = "session"


class ResultStatus(str, Enum):
    """Operation result status enumeration."""

    SUCCESS = "success"
    FAILURE = "failure"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    PARTIAL = "partial"


class SecurityContext(BaseModel):
    """Security-related metadata for audit records."""

    user_agent: Optional[str] = Field(None, description="User agent or client identifier")
    source_ip: Optional[str] = Field(None, description="Source IP address")
    session_token: Optional[str] = Field(None, description="Session token hash")
    policy_applied: str = Field(..., description="Policy configuration applied")
    permission_checks: List[str] = Field(default_factory=list, description="Permission checks performed")
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Calculated risk score")
    threat_indicators: List[str] = Field(default_factory=list, description="Detected threat indicators")


class ResourceUsage(BaseModel):
    """Resource consumption tracking."""

    execution_time_ms: Optional[int] = Field(None, ge=0, description="Execution time in milliseconds")
    cost_usd: Optional[float] = Field(None, ge=0.0, description="Cost in USD")
    tokens_consumed: Optional[int] = Field(None, ge=0, description="Tokens consumed")
    memory_peak_mb: Optional[float] = Field(None, ge=0.0, description="Peak memory usage in MB")
    cpu_time_ms: Optional[int] = Field(None, ge=0, description="CPU time in milliseconds")
    disk_io_bytes: Optional[int] = Field(None, ge=0, description="Disk I/O in bytes")
    network_bytes: Optional[int] = Field(None, ge=0, description="Network traffic in bytes")


class AuditRecord(BaseModel):
    """
    Security and compliance log entry tracking agent actions, decisions, and system events.

    Comprehensive audit trail for compliance, security analysis, and debugging.
    """

    record_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the audit record")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When the event occurred")
    event_type: EventType = Field(..., description="Type of event")
    session_id: Optional[str] = Field(None, description="Reference to related ConversationSession")
    agent_id: Optional[str] = Field(None, description="Agent that performed the action")
    turn_id: Optional[str] = Field(None, description="Related turn ID if applicable")

    # Event details
    action: str = Field(..., description="Specific action or operation performed")
    result: ResultStatus = Field(..., description="Outcome of the action")
    reason: Optional[str] = Field(None, description="Rationale for the action or decision")
    error_details: Optional[str] = Field(None, description="Error details if result was failure")

    # Policy and security context
    policy_applied: str = Field(..., description="PolicyConfiguration that governed the action")
    security_context: SecurityContext = Field(..., description="Security-related metadata")
    resource_usage: Optional[ResourceUsage] = Field(None, description="Resources consumed")

    # Tracing and correlation
    trace_id: Optional[str] = Field(None, description="OpenTelemetry trace identifier for correlation")
    span_id: Optional[str] = Field(None, description="OpenTelemetry span identifier")
    parent_record_id: Optional[str] = Field(None, description="Parent audit record ID for hierarchical events")

    # Additional context
    request_data: Dict[str, Any] = Field(default_factory=dict, description="Request data (sanitized)")
    response_data: Dict[str, Any] = Field(default_factory=dict, description="Response data (sanitized)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional event metadata")

    # Compliance and retention
    compliance_tags: List[str] = Field(default_factory=list, description="Compliance requirement tags")
    retention_period_days: int = Field(default=365, ge=1, le=2555, description="Data retention period in days")  # 7 years max

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @field_validator('record_id')
    def validate_record_id(cls, v):
        """Validate record ID is not empty."""
        if not v.strip():
            raise ValueError("record_id cannot be empty")
        return v.strip()

    @field_validator('timestamp')
    def validate_timestamp_not_future(cls, v):
        """Ensure timestamp is not in the future."""
        now = datetime.now(timezone.utc)
        if v > now:
            raise ValueError("timestamp cannot be in the future")
        return v

    @field_validator('action')
    def validate_action(cls, v):
        """Validate action is not empty."""
        if not v.strip():
            raise ValueError("action cannot be empty")
        return v.strip()

    @field_validator('policy_applied')
    def validate_policy_applied(cls, v):
        """Validate policy_applied is not empty."""
        if not v.strip():
            raise ValueError("policy_applied cannot be empty")
        return v.strip()

    @field_validator('request_data', 'response_data')
    def sanitize_sensitive_data(cls, v):
        """Sanitize sensitive data from request/response."""
        if not isinstance(v, dict):
            return v

        # List of sensitive keys to sanitize
        sensitive_keys = [
            'password', 'token', 'key', 'secret', 'credential',
            'auth', 'authorization', 'cookie', 'session_id'
        ]

        sanitized = {}
        for key, value in v.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                # Recursively sanitize nested dictionaries
                sanitized[key] = cls.sanitize_sensitive_data(value)
            else:
                sanitized[key] = value

        return sanitized

    def add_threat_indicator(self, indicator: str) -> None:
        """
        Add a threat indicator to the security context.

        Args:
            indicator: Threat indicator description
        """
        if indicator not in self.security_context.threat_indicators:
            self.security_context.threat_indicators.append(indicator)

    def update_risk_score(self, score: float) -> None:
        """
        Update the security risk score.

        Args:
            score: Risk score between 0.0 and 1.0
        """
        if not 0.0 <= score <= 1.0:
            raise ValueError("Risk score must be between 0.0 and 1.0")
        self.security_context.risk_score = score

    def add_compliance_tag(self, tag: str) -> None:
        """
        Add a compliance tag.

        Args:
            tag: Compliance requirement tag
        """
        if tag not in self.compliance_tags:
            self.compliance_tags.append(tag)

    def link_to_parent(self, parent_record_id: str) -> None:
        """
        Link this record to a parent record for hierarchical audit trails.

        Args:
            parent_record_id: ID of the parent audit record
        """
        self.parent_record_id = parent_record_id

    def set_tracing_context(self, trace_id: str, span_id: Optional[str] = None) -> None:
        """
        Set OpenTelemetry tracing context for correlation.

        Args:
            trace_id: Trace identifier
            span_id: Span identifier
        """
        self.trace_id = trace_id
        self.span_id = span_id

    def is_security_event(self) -> bool:
        """Check if this is a security-related event."""
        return (
            self.event_type == EventType.SECURITY or
            self.result == ResultStatus.BLOCKED or
            len(self.security_context.threat_indicators) > 0 or
            self.security_context.risk_score > 0.5
        )

    def is_failure_event(self) -> bool:
        """Check if this represents a failure or error."""
        return self.result in [ResultStatus.FAILURE, ResultStatus.TIMEOUT]

    def get_retention_date(self) -> datetime:
        """Calculate the retention expiration date."""
        from datetime import timedelta
        return self.timestamp + timedelta(days=self.retention_period_days)

    def to_log_entry(self) -> Dict[str, Any]:
        """Convert to structured log entry format."""
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp.isoformat(),
            "level": "ERROR" if self.is_failure_event() else "WARN" if self.is_security_event() else "INFO",
            "event_type": self.event_type,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "action": self.action,
            "result": self.result,
            "reason": self.reason,
            "policy": self.policy_applied,
            "risk_score": self.security_context.risk_score,
            "trace_id": self.trace_id,
            "error": self.error_details,
            "resource_cost_usd": self.resource_usage.cost_usd if self.resource_usage else None,
            "execution_time_ms": self.resource_usage.execution_time_ms if self.resource_usage else None
        }

    def to_security_alert(self) -> Optional[Dict[str, Any]]:
        """Convert to security alert format if this is a security event."""
        if not self.is_security_event():
            return None

        return {
            "alert_id": self.record_id,
            "timestamp": self.timestamp.isoformat(),
            "severity": "HIGH" if self.security_context.risk_score > 0.8 else "MEDIUM" if self.security_context.risk_score > 0.5 else "LOW",
            "event_type": self.event_type,
            "action": self.action,
            "result": self.result,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "threat_indicators": self.security_context.threat_indicators,
            "risk_score": self.security_context.risk_score,
            "policy_applied": self.policy_applied,
            "source_ip": self.security_context.source_ip,
            "details": self.reason or self.error_details
        }

    def to_compliance_record(self) -> Dict[str, Any]:
        """Convert to compliance record format."""
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "action": self.action,
            "result": self.result,
            "policy_applied": self.policy_applied,
            "compliance_tags": self.compliance_tags,
            "retention_until": self.get_retention_date().isoformat(),
            "security_validated": self.security_context.policy_applied,
            "data_sanitized": True,  # Always true due to our sanitization
            "audit_trail_complete": self.parent_record_id is not None or self.event_type == EventType.SESSION
        }