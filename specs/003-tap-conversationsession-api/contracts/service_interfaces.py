"""Service Interface Contracts for TAP Agent Dialog Integration.

These contracts define the expected behavior and signatures for service layer
integration components. Used for contract testing and implementation validation.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Protocol
from pydantic import Field, validate_call
from src.tab.models.conversation_session import ConversationSession
from src.tab.models.turn_message import TurnMessage


class SessionManagerContract(Protocol):
    """Contract for SessionManager enhanced constructor and methods."""

    def __init__(self, config: Dict[str, Any]):
        """SessionManager must accept configuration object."""
        ...

    @validate_call
    async def create_session(
        self,
        topic: str = Field(..., min_length=1, max_length=1000),
        participants: List[str] = Field(..., min_length=2),
        policy_id: str = Field(default="default"),
        max_turns: int = Field(default=8, ge=1, le=20),
        budget_usd: float = Field(default=1.0, ge=0.01, le=10.0),
        **kwargs
    ) -> ConversationSession:
        """Create session with enhanced validation."""
        ...

    @validate_call
    async def get_session(
        self,
        session_id: str = Field(..., min_length=1)
    ) -> Optional[ConversationSession]:
        """Retrieve session by ID."""
        ...


class PolicyEnforcerContract(Protocol):
    """Contract for PolicyEnforcer enhanced constructor and validation."""

    def __init__(self, config: Dict[str, Any]):
        """PolicyEnforcer must accept policy configuration dictionary."""
        ...

    def validate_session_creation(
        self,
        policy_id: str,
        session_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate session creation parameters against policy."""
        ...

    def validate_turn_addition(
        self,
        policy_id: str,
        session: ConversationSession,
        turn: TurnMessage
    ) -> Dict[str, Any]:
        """Validate turn addition against policy constraints."""
        ...

    def enforce_turn_message_policy(
        self,
        policy_id: str,
        turn: TurnMessage
    ) -> Dict[str, Any]:
        """Enforce policy on turn message content and metadata."""
        ...


class ConversationOrchestratorContract(Protocol):
    """Contract for ConversationOrchestrator enhanced constructor and API."""

    def __init__(
        self,
        session_manager: SessionManagerContract,
        policy_enforcer: PolicyEnforcerContract,
        agent_configs: Dict[str, Any]
    ):
        """ConversationOrchestrator must accept injected dependencies."""
        ...

    async def start_conversation(
        self,
        topic: str,
        participants: List[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Start conversation with unified API."""
        ...

    async def get_conversation_context(
        self,
        session_id: str,
        agent_filter: Optional[str] = None,
        limit: int = 5  # Unified parameter name (was max_turns)
    ) -> List[Dict[str, Any]]:
        """Get conversation context with unified parameters."""
        ...

    async def process_turn(
        self,
        session_id: str,
        content: str,
        from_agent: str,
        to_agent: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Process conversation turn with validation."""
        ...


class ConversationSessionServiceContract(Protocol):
    """Contract for unified conversation session service interface."""

    @validate_call
    async def create_session(
        self,
        topic: str = Field(..., min_length=1, max_length=1000),
        participants: List[str] = Field(..., min_length=2),
        policy_id: str = Field(default="default"),
        max_turns: int = Field(default=8, ge=1, le=20),
        **kwargs
    ) -> ConversationSession:
        """Create new conversation session."""
        ...

    @validate_call
    async def add_turn_to_session(
        self,
        session_id: str = Field(..., min_length=1),
        turn: TurnMessage
    ) -> bool:
        """Add turn to session with policy validation."""
        ...

    @validate_call
    async def get_session_context(
        self,
        session_id: str = Field(..., min_length=1),
        agent_filter: Optional[str] = None,
        limit: int = Field(default=5, ge=1, le=50)
    ) -> List[Dict[str, Any]]:
        """Get conversation context with filtering."""
        ...

    async def check_session_convergence(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """Check session convergence signals."""
        ...


class AgentRegistryContract(Protocol):
    """Contract for dynamic agent registry service."""

    async def discover_agents(
        self,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Discover and register agents from configuration."""
        ...

    async def get_agent(
        self,
        agent_id: str
    ) -> Optional[Any]:
        """Retrieve registered agent by ID."""
        ...

    async def validate_agent_config(
        self,
        agent_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate agent configuration before registration."""
        ...

    async def health_check_agents(self) -> Dict[str, Any]:
        """Perform health check on all registered agents."""
        ...


# Response schemas for validation

SESSION_CREATION_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["session_id", "status", "participants", "created_at"],
    "properties": {
        "session_id": {"type": "string", "minLength": 1},
        "status": {"type": "string", "enum": ["active", "completed", "failed", "timeout"]},
        "participants": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 2
        },
        "created_at": {"type": "string", "format": "date-time"},
        "topic": {"type": "string", "minLength": 1},
        "max_turns": {"type": "integer", "minimum": 1, "maximum": 20},
        "current_turn": {"type": "integer", "minimum": 0}
    }
}

TURN_ADDITION_RESPONSE_SCHEMA = {
    "type": "boolean",
    "description": "Success indicator for turn addition"
}

CONTEXT_RETRIEVAL_RESPONSE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["role", "content", "from_agent", "timestamp"],
        "properties": {
            "role": {
                "type": "string",
                "enum": ["user", "assistant", "system"]
            },
            "content": {"type": "string", "minLength": 1},
            "from_agent": {"type": "string", "minLength": 1},
            "timestamp": {"type": "string", "format": "date-time"},
            "attachments": {
                "type": ["array", "null"],
                "items": {
                    "type": "object",
                    "required": ["path", "type"],
                    "properties": {
                        "path": {"type": "string"},
                        "type": {"type": "string"},
                        "size": {"type": ["integer", "null"]}
                    }
                }
            }
        }
    }
}

CONVERGENCE_CHECK_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["should_continue", "confidence", "signals", "recommendations"],
    "properties": {
        "should_continue": {"type": "boolean"},
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0
        },
        "signals": {
            "type": "object",
            "required": ["repetitive_content", "explicit_completion", "resource_exhaustion"],
            "properties": {
                "repetitive_content": {"type": "boolean"},
                "explicit_completion": {"type": "boolean"},
                "resource_exhaustion": {"type": "boolean"},
                "quality_degradation": {"type": "boolean"}
            }
        },
        "recommendations": {
            "type": "array",
            "items": {"type": "string"}
        },
        "metadata": {
            "type": "object",
            "properties": {
                "turns_analyzed": {"type": "integer", "minimum": 0},
                "avg_turn_length": {"type": "number", "minimum": 0}
            }
        }
    }
}

POLICY_VALIDATION_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["allowed", "violations"],
    "properties": {
        "allowed": {"type": "boolean"},
        "violations": {
            "type": "array",
            "items": {"type": "string"}
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"}
        },
        "policy_id": {"type": "string"},
        "validation_time": {"type": "string", "format": "date-time"}
    }
}

SERVICE_HEALTH_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["status", "checks"],
    "properties": {
        "status": {
            "type": "string",
            "enum": ["healthy", "degraded", "unhealthy"]
        },
        "checks": {
            "type": "object",
            "patternProperties": {
                ".*": {
                    "type": "object",
                    "required": ["status"],
                    "properties": {
                        "status": {"type": "string"},
                        "message": {"type": "string"},
                        "response_time_ms": {"type": "number"},
                        "details": {"type": "object"}
                    }
                }
            }
        },
        "timestamp": {"type": "string", "format": "date-time"}
    }
}

# Example valid responses for testing

EXAMPLE_SESSION_CREATION = {
    "session_id": "sess_123e4567-e89b-12d3-a456-426614174000",
    "status": "active",
    "participants": ["claude_code", "codex_cli"],
    "created_at": "2025-09-22T10:30:00Z",
    "topic": "Implement user authentication system",
    "max_turns": 8,
    "current_turn": 0
}

EXAMPLE_CONTEXT_RETRIEVAL = [
    {
        "role": "assistant",
        "content": "I'll help you implement the user authentication system.",
        "from_agent": "claude_code",
        "timestamp": "2025-09-22T10:30:00Z",
        "attachments": None
    },
    {
        "role": "user",
        "content": "Let's start with the database schema for users.",
        "from_agent": "codex_cli",
        "timestamp": "2025-09-22T10:29:00Z",
        "attachments": None
    }
]

EXAMPLE_CONVERGENCE_CHECK = {
    "should_continue": True,
    "confidence": 0.8,
    "signals": {
        "repetitive_content": False,
        "explicit_completion": False,
        "resource_exhaustion": False,
        "quality_degradation": False
    },
    "recommendations": [
        "Continue conversation - good progress being made",
        "Monitor for completion signals in next 2-3 turns"
    ],
    "metadata": {
        "turns_analyzed": 4,
        "avg_turn_length": 125.5
    }
}

EXAMPLE_POLICY_VALIDATION = {
    "allowed": True,
    "violations": [],
    "warnings": ["Turn content contains external URL"],
    "policy_id": "default",
    "validation_time": "2025-09-22T10:30:00Z"
}

EXAMPLE_SERVICE_HEALTH = {
    "status": "healthy",
    "checks": {
        "session_manager": {
            "status": "healthy",
            "message": "All operations normal",
            "response_time_ms": 12.5,
            "details": {"active_sessions": 3}
        },
        "policy_enforcer": {
            "status": "healthy",
            "message": "Policy validation operational",
            "response_time_ms": 8.2,
            "details": {"policies_loaded": 5}
        }
    },
    "timestamp": "2025-09-22T10:30:00Z"
}