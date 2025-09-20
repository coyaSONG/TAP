"""ConversationSession model with state transitions."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class SessionStatus(str, Enum):
    """Session status enumeration."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ConversationSession(BaseModel):
    """
    Represents a complete multi-turn dialogue between agents.

    Includes turn history, state, and metadata for orchestration and audit purposes.
    """

    session_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the conversation session")
    participants: List[str] = Field(..., min_items=2, max_items=5, description="List of agent identifiers participating in conversation")
    topic: str = Field(..., min_length=1, max_length=1000, description="Initial question or task description")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE, description="Current session status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Session creation timestamp")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last activity timestamp")
    turn_history: List[str] = Field(default_factory=list, description="Ordered list of TurnMessage IDs")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Session-level metadata (costs, performance metrics)")
    policy_config_id: str = Field(default="default", description="Applied PolicyConfiguration ID for this session")

    # Budget and constraints
    max_turns: int = Field(default=8, ge=1, le=20, description="Maximum conversation turns allowed")
    budget_usd: float = Field(default=1.0, ge=0.01, le=10.0, description="Maximum cost budget in USD")
    budget_remaining_usd: float = Field(default=1.0, ge=0.0, description="Remaining cost budget")
    turns_remaining: int = Field(default=8, ge=0, description="Remaining turn budget")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @validator('participants')
    def validate_participants(cls, v):
        """Validate participants list."""
        if len(v) < 2:
            raise ValueError("Must have at least 2 participants")

        # Check for valid agent types
        valid_agents = ["claude_code", "codex_cli"]
        for agent in v:
            if agent not in valid_agents:
                raise ValueError(f"Unknown agent type: {agent}")

        # Check for duplicates
        if len(set(v)) != len(v):
            raise ValueError("Participants must be unique")

        return v

    @validator('updated_at', always=True)
    def validate_updated_at(cls, v, values):
        """Ensure updated_at is not before created_at."""
        if 'created_at' in values and v < values['created_at']:
            raise ValueError("updated_at cannot be before created_at")
        return v

    @validator('turn_history')
    def validate_turn_history_order(cls, v):
        """Validate turn history maintains chronological order."""
        # This is a placeholder for turn ID validation
        # In practice, we would validate that turn IDs exist and are in order
        return v

    @validator('budget_remaining_usd', always=True)
    def validate_budget_remaining(cls, v, values):
        """Ensure remaining budget doesn't exceed initial budget."""
        if 'budget_usd' in values and v > values['budget_usd']:
            raise ValueError("Remaining budget cannot exceed initial budget")
        return v

    @validator('turns_remaining', always=True)
    def validate_turns_remaining(cls, v, values):
        """Ensure remaining turns doesn't exceed max turns."""
        if 'max_turns' in values and v > values['max_turns']:
            raise ValueError("Remaining turns cannot exceed max turns")
        return v

    def transition_status(self, new_status: SessionStatus, reason: Optional[str] = None) -> bool:
        """
        Transition session status following defined state machine.

        Args:
            new_status: Target status to transition to
            reason: Optional reason for the transition

        Returns:
            True if transition was successful, False otherwise
        """
        valid_transitions = {
            SessionStatus.ACTIVE: [SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.TIMEOUT],
            SessionStatus.COMPLETED: [],  # Terminal state
            SessionStatus.FAILED: [],     # Terminal state
            SessionStatus.TIMEOUT: [],    # Terminal state
        }

        if new_status not in valid_transitions.get(self.status, []):
            return False

        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)

        # Record transition in metadata
        if 'status_transitions' not in self.metadata:
            self.metadata['status_transitions'] = []

        self.metadata['status_transitions'].append({
            'from_status': self.status.value if hasattr(self.status, 'value') else str(self.status),
            'to_status': new_status.value if hasattr(new_status, 'value') else str(new_status),
            'timestamp': self.updated_at.isoformat(),
            'reason': reason
        })

        return True

    def add_turn(self, turn_id: str) -> bool:
        """
        Add a turn to the session history.

        Args:
            turn_id: ID of the turn to add

        Returns:
            True if turn was added successfully, False if budget/turn limits exceeded
        """
        if self.status != SessionStatus.ACTIVE:
            return False

        if self.turns_remaining <= 0:
            # Try to transition to timeout if no turns remaining
            self.transition_status(SessionStatus.TIMEOUT, "Turn limit exceeded")
            return False

        self.turn_history.append(turn_id)
        self.turns_remaining -= 1
        self.updated_at = datetime.now(timezone.utc)

        return True

    def update_budget(self, cost_usd: float) -> bool:
        """
        Update remaining budget after an operation.

        Args:
            cost_usd: Cost of the operation in USD

        Returns:
            True if budget was updated successfully, False if budget exceeded
        """
        if cost_usd < 0:
            raise ValueError("Cost cannot be negative")

        new_remaining = self.budget_remaining_usd - cost_usd

        if new_remaining < 0:
            # Try to transition to failed if budget exceeded
            self.transition_status(SessionStatus.FAILED, "Budget exceeded")
            return False

        self.budget_remaining_usd = new_remaining
        self.updated_at = datetime.now(timezone.utc)

        # Update cost tracking in metadata
        if 'total_cost_usd' not in self.metadata:
            self.metadata['total_cost_usd'] = 0.0

        self.metadata['total_cost_usd'] += cost_usd

        return True

    def get_current_turn_number(self) -> int:
        """Get the current turn number (1-indexed)."""
        return len(self.turn_history) + 1

    def is_budget_warning(self, threshold: float = 0.8) -> bool:
        """
        Check if budget is below warning threshold.

        Args:
            threshold: Warning threshold as percentage of original budget (0.0-1.0)

        Returns:
            True if budget is below warning threshold
        """
        return self.budget_remaining_usd < (self.budget_usd * threshold)

    def can_continue(self) -> bool:
        """Check if session can continue (has budget and turns remaining)."""
        return (
            self.status == SessionStatus.ACTIVE and
            self.budget_remaining_usd > 0 and
            self.turns_remaining > 0
        )

    def to_summary(self) -> Dict[str, Any]:
        """Generate a summary of the session for reporting."""
        return {
            "session_id": self.session_id,
            "topic": self.topic,
            "status": self.status,
            "participants": self.participants,
            "turn_count": len(self.turn_history),
            "cost_usd": self.metadata.get('total_cost_usd', 0.0),
            "budget_remaining_usd": self.budget_remaining_usd,
            "turns_remaining": self.turns_remaining,
            "duration_minutes": self._calculate_duration_minutes(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    def _calculate_duration_minutes(self) -> float:
        """Calculate session duration in minutes."""
        duration = self.updated_at - self.created_at
        return duration.total_seconds() / 60.0