"""ConversationSession model with state transitions and validation."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class SessionStatus(str, Enum):
    """Valid session status values."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ConversationSession(BaseModel):
    """Represents a complete multi-turn dialogue between agents.

    Includes turn history, state management, and metadata tracking
    with proper state transitions and validation rules.
    """

    session_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the conversation session"
    )

    participants: List[str] = Field(
        ...,
        min_items=2,
        description="List of agent identifiers participating in conversation"
    )

    topic: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Initial question or task description"
    )

    status: SessionStatus = Field(
        default=SessionStatus.ACTIVE,
        description="Current session status"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Session creation timestamp"
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last activity timestamp"
    )

    turn_history: List[Any] = Field(
        default_factory=list,
        description="Ordered list of TurnMessage objects"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Session-level metadata (costs, performance metrics)"
    )

    policy_config: Optional[str] = Field(
        default="default",
        description="Applied PolicyConfiguration ID for this session"
    )

    max_turns: int = Field(
        default=8,
        ge=1,
        le=20,
        description="Maximum number of turns allowed"
    )

    budget_usd: float = Field(
        default=1.0,
        ge=0.01,
        le=10.0,
        description="Maximum cost budget in USD"
    )

    total_cost_usd: float = Field(
        default=0.0,
        ge=0.0,
        description="Total cost accumulated so far"
    )

    current_turn: int = Field(
        default=0,
        ge=0,
        description="Current turn number"
    )

    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True

    @field_validator('participants')
    @classmethod
    def validate_participants(cls, v):
        """Validate participants list."""
        if len(v) < 2:
            raise ValueError("Must have at least 2 participants")

        # Check for valid agent types
        valid_agents = ["claude_code", "codex_cli"]
        for participant in v:
            if participant not in valid_agents:
                raise ValueError(f"Invalid agent type: {participant}. Must be one of {valid_agents}")

        # Check for duplicates
        if len(set(v)) != len(v):
            raise ValueError("Duplicate participants not allowed")

        return v

    @model_validator(mode='after')
    def validate_constraints(self):
        """Validate all model constraints."""
        # Ensure updated_at is not before created_at
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be before created_at")

        # Validate budget and cost constraints
        if self.total_cost_usd > self.budget_usd:
            raise ValueError("Total cost cannot exceed budget")

        return self

    def can_add_turn(self) -> bool:
        """Check if a new turn can be added."""
        return (
            self.status == SessionStatus.ACTIVE and
            self.current_turn < self.max_turns and
            self.total_cost_usd < self.budget_usd
        )

    def transition_to(self, new_status: SessionStatus, reason: Optional[str] = None) -> bool:
        """Transition to a new status with validation."""
        # Define valid transitions
        valid_transitions = {
            SessionStatus.ACTIVE: [SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.TIMEOUT],
            SessionStatus.COMPLETED: [],  # Terminal state
            SessionStatus.FAILED: [],     # Terminal state
            SessionStatus.TIMEOUT: []     # Terminal state
        }

        if new_status not in valid_transitions.get(self.status, []):
            return False

        # Update status and timestamp
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)

        # Add reason to metadata if provided
        if reason:
            if 'status_transitions' not in self.metadata:
                self.metadata['status_transitions'] = []
            self.metadata['status_transitions'].append({
                'from': self.status.value,
                'to': new_status.value,
                'reason': reason,
                'timestamp': self.updated_at.isoformat()
            })

        return True