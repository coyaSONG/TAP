"""TAB Data Models.

This package contains all data models for the Twin-Agent Bridge system,
including conversation sessions, messages, agent adapters, policies, audit records,
and orchestration state management.
"""

from .conversation_session import ConversationSession, SessionStatus
from .turn_message import (
    TurnMessage,
    MessageRole,
    AttachmentType,
    MessageAttachment,
    PolicyConstraint,
)
from .agent_adapter import (
    AgentAdapter,
    AgentType,
    AgentStatus,
    ConnectionType,
    ConnectionConfig,
    ExecutionLimits,
    AgentCapability,
    SessionManagerConfig,
)
from .policy_configuration import (
    PolicyConfiguration,
    PermissionMode,
    IsolationLevel,
    ResourceLimits,
    FileAccessRules,
    NetworkAccessRules,
    SandboxConfig,
)
from .audit_record import (
    AuditRecord,
    EventType,
    ResultStatus,
    SecurityContext,
    ResourceUsage,
)
from .orchestration_state import (
    OrchestrationState,
    ConversationFlow,
    ConvergenceSignal,
    ContextSummary,
)

__all__ = [
    # ConversationSession
    "ConversationSession",
    "SessionStatus",
    # TurnMessage
    "TurnMessage",
    "MessageRole",
    "AttachmentType",
    "MessageAttachment",
    "PolicyConstraint",
    # AgentAdapter
    "AgentAdapter",
    "AgentType",
    "AgentStatus",
    "ConnectionType",
    "ConnectionConfig",
    "ExecutionLimits",
    "AgentCapability",
    "SessionManagerConfig",
    # PolicyConfiguration
    "PolicyConfiguration",
    "PermissionMode",
    "IsolationLevel",
    "ResourceLimits",
    "FileAccessRules",
    "NetworkAccessRules",
    "SandboxConfig",
    # AuditRecord
    "AuditRecord",
    "EventType",
    "ResultStatus",
    "SecurityContext",
    "ResourceUsage",
    # OrchestrationState
    "OrchestrationState",
    "ConversationFlow",
    "ConvergenceSignal",
    "ContextSummary",
]