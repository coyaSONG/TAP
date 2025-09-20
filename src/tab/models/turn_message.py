"""TurnMessage model with validation rules."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class MessageRole(str, Enum):
    """Message role enumeration."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AttachmentType(str, Enum):
    """File attachment type enumeration."""

    FILE = "file"
    CODE_SNIPPET = "code_snippet"
    IMAGE = "image"
    DOCUMENT = "document"


class MessageAttachment(BaseModel):
    """File attachment or reference."""

    path: str = Field(..., description="File path or reference")
    type: AttachmentType = Field(..., description="Type of attachment")
    size: Optional[int] = Field(None, ge=0, description="Size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type of the attachment")
    checksum: Optional[str] = Field(None, description="File checksum for integrity")

    @validator('path')
    def validate_path(cls, v):
        """Validate file path."""
        if not v.strip():
            raise ValueError("Path cannot be empty")
        return v.strip()


class PolicyConstraint(BaseModel):
    """Policy constraint applied to a turn."""

    constraint_type: str = Field(..., description="Type of constraint")
    value: Union[str, int, float, bool] = Field(..., description="Constraint value")
    enforced: bool = Field(default=True, description="Whether constraint was enforced")
    violation_reason: Optional[str] = Field(None, description="Reason for violation if any")


class TurnMessage(BaseModel):
    """
    Individual communication unit containing agent identity, content, role designation, and policy constraints.

    Represents a single turn in a multi-agent conversation with complete audit trail.
    """

    turn_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for this conversation turn")
    session_id: str = Field(..., description="Reference to parent ConversationSession")
    from_agent: str = Field(..., description="Identifier of the sending agent")
    to_agent: str = Field(..., description="Identifier of the receiving agent")
    role: MessageRole = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., min_length=1, max_length=10000, description="Message content (text, structured data, files)")
    attachments: List[MessageAttachment] = Field(default_factory=list, max_items=10, description="Optional file attachments or references")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When the message was created")
    policy_constraints: List[PolicyConstraint] = Field(default_factory=list, description="Applied policy constraints for this turn")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Turn-specific metadata (cost, duration, tokens)")

    # Performance and cost tracking
    processing_time_ms: Optional[int] = Field(None, ge=0, description="Time taken to process this turn")
    cost_usd: Optional[float] = Field(None, ge=0.0, description="Cost incurred for this turn")
    tokens_used: Optional[int] = Field(None, ge=0, description="Number of tokens consumed")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @validator('from_agent')
    def validate_from_agent(cls, v):
        """Validate sending agent."""
        if not v.strip():
            raise ValueError("from_agent cannot be empty")

        # Allow orchestrator as a valid sender
        valid_agents = ["claude_code", "codex_cli", "orchestrator"]
        if v not in valid_agents:
            raise ValueError(f"Unknown agent type: {v}")

        return v

    @validator('to_agent')
    def validate_to_agent(cls, v):
        """Validate receiving agent."""
        if not v.strip():
            raise ValueError("to_agent cannot be empty")

        # Allow auto-routing and orchestrator as valid targets
        valid_agents = ["claude_code", "codex_cli", "orchestrator", "auto"]
        if v not in valid_agents:
            raise ValueError(f"Unknown agent type: {v}")

        return v

    @validator('to_agent')
    def validate_different_agents(cls, v, values):
        """Ensure from_agent and to_agent are different."""
        if 'from_agent' in values and v == values['from_agent']:
            raise ValueError("from_agent and to_agent must be different")
        return v

    @validator('content')
    def validate_content(cls, v):
        """Validate message content."""
        content = v.strip()
        if not content:
            raise ValueError("Content cannot be empty")
        return content

    @validator('role')
    def validate_role_agent_consistency(cls, v, values):
        """Validate role is consistent with agent type."""
        if 'from_agent' in values:
            # System messages should only come from orchestrator
            if v == MessageRole.SYSTEM and values['from_agent'] != 'orchestrator':
                raise ValueError("System messages can only be sent by orchestrator")

            # User messages typically come from orchestrator (representing user input)
            # Assistant messages come from actual agents
            if v == MessageRole.USER and values['from_agent'] not in ['orchestrator']:
                raise ValueError("User messages should come from orchestrator")

        return v

    @validator('attachments')
    def validate_attachments(cls, v):
        """Validate attachments list."""
        if len(v) > 10:
            raise ValueError("Maximum 10 attachments allowed")

        # Check for duplicate paths
        paths = [att.path for att in v]
        if len(set(paths)) != len(paths):
            raise ValueError("Duplicate attachment paths not allowed")

        return v

    def add_policy_constraint(self, constraint_type: str, value: Union[str, int, float, bool], enforced: bool = True, violation_reason: Optional[str] = None) -> None:
        """
        Add a policy constraint to this turn.

        Args:
            constraint_type: Type of constraint (e.g., 'max_cost', 'allowed_tools')
            value: The constraint value
            enforced: Whether the constraint was successfully enforced
            violation_reason: Reason for violation if constraint was not enforced
        """
        constraint = PolicyConstraint(
            constraint_type=constraint_type,
            value=value,
            enforced=enforced,
            violation_reason=violation_reason
        )
        self.policy_constraints.append(constraint)

    def update_performance_metrics(self, processing_time_ms: int, cost_usd: float, tokens_used: int) -> None:
        """
        Update performance metrics for this turn.

        Args:
            processing_time_ms: Processing time in milliseconds
            cost_usd: Cost in USD
            tokens_used: Number of tokens consumed
        """
        if processing_time_ms < 0:
            raise ValueError("Processing time cannot be negative")
        if cost_usd < 0:
            raise ValueError("Cost cannot be negative")
        if tokens_used < 0:
            raise ValueError("Tokens used cannot be negative")

        self.processing_time_ms = processing_time_ms
        self.cost_usd = cost_usd
        self.tokens_used = tokens_used

        # Also store in metadata for backward compatibility
        self.metadata.update({
            'processing_time_ms': processing_time_ms,
            'cost_usd': cost_usd,
            'tokens_used': tokens_used
        })

    def add_attachment(self, path: str, attachment_type: AttachmentType, size: Optional[int] = None, mime_type: Optional[str] = None) -> bool:
        """
        Add an attachment to this message.

        Args:
            path: File path or reference
            attachment_type: Type of attachment
            size: Size in bytes
            mime_type: MIME type

        Returns:
            True if attachment was added successfully, False if limit exceeded
        """
        if len(self.attachments) >= 10:
            return False

        # Check for duplicate paths
        if any(att.path == path for att in self.attachments):
            return False

        attachment = MessageAttachment(
            path=path,
            type=attachment_type,
            size=size,
            mime_type=mime_type
        )

        self.attachments.append(attachment)
        return True

    def get_constraint_violations(self) -> List[PolicyConstraint]:
        """Get list of policy constraints that were violated."""
        return [constraint for constraint in self.policy_constraints if not constraint.enforced]

    def has_violations(self) -> bool:
        """Check if this turn has any policy violations."""
        return len(self.get_constraint_violations()) > 0

    def to_chat_format(self) -> Dict[str, Any]:
        """Convert to standard chat message format for agent consumption."""
        return {
            "role": self.role,
            "content": self.content,
            "from_agent": self.from_agent,
            "timestamp": self.timestamp.isoformat(),
            "attachments": [
                {
                    "path": att.path,
                    "type": att.type,
                    "size": att.size
                }
                for att in self.attachments
            ] if self.attachments else None
        }

    def to_audit_record(self) -> Dict[str, Any]:
        """Convert to audit record format for compliance logging."""
        return {
            "turn_id": self.turn_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "role": self.role,
            "content_length": len(self.content),
            "attachment_count": len(self.attachments),
            "policy_constraints": [
                {
                    "type": constraint.constraint_type,
                    "enforced": constraint.enforced,
                    "violation": constraint.violation_reason
                }
                for constraint in self.policy_constraints
            ],
            "performance": {
                "processing_time_ms": self.processing_time_ms,
                "cost_usd": self.cost_usd,
                "tokens_used": self.tokens_used
            },
            "violations": len(self.get_constraint_violations())
        }