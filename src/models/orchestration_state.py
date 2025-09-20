"""OrchestrationState model with flow control."""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class ConversationFlow(str, Enum):
    """Conversation flow state enumeration."""

    WAITING = "waiting"
    PROCESSING = "processing"
    CONVERGING = "converging"
    COMPLETED = "completed"
    FAILED = "failed"


class ConvergenceSignal(BaseModel):
    """Individual convergence signal indicator."""

    signal_type: str = Field(..., description="Type of convergence signal")
    value: Union[bool, float, str] = Field(..., description="Signal value")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence in this signal")
    source_agent: Optional[str] = Field(None, description="Agent that provided this signal")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When signal was detected")


class ContextSummary(BaseModel):
    """Conversation context summary for agent handoff."""

    main_topic: str = Field(..., description="Main conversation topic")
    key_findings: List[str] = Field(default_factory=list, description="Key findings so far")
    outstanding_questions: List[str] = Field(default_factory=list, description="Outstanding questions")
    consensus_points: List[str] = Field(default_factory=list, description="Points of consensus")
    disagreement_points: List[str] = Field(default_factory=list, description="Points of disagreement")
    next_actions: List[str] = Field(default_factory=list, description="Suggested next actions")
    confidence_level: float = Field(default=0.5, ge=0.0, le=1.0, description="Overall confidence in findings")


class OrchestrationState(BaseModel):
    """
    Current conversation context, participant status, and flow control information.

    Manages conversation state, participant coordination, and convergence detection.
    """

    state_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the orchestration state")
    session_id: str = Field(..., description="Reference to associated ConversationSession")
    current_turn: int = Field(default=0, ge=0, description="Current turn number in conversation")
    active_agent: Optional[str] = Field(None, description="Agent currently processing or expected to respond")
    conversation_flow: ConversationFlow = Field(default=ConversationFlow.WAITING, description="Flow control state")

    # Convergence tracking
    convergence_signals: List[ConvergenceSignal] = Field(default_factory=list, description="Indicators of conversation convergence")
    convergence_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="Threshold for convergence detection")
    convergence_detected: bool = Field(default=False, description="Whether convergence has been detected")

    # Timeout and budget management
    timeout_deadline: Optional[datetime] = Field(None, description="When the current operation times out")
    operation_timeout_seconds: int = Field(default=120, ge=1, le=3600, description="Current operation timeout")
    cost_budget_remaining: float = Field(default=1.0, ge=0.0, description="Remaining cost budget for session")
    turn_budget_remaining: int = Field(default=8, ge=0, description="Remaining turn budget for session")

    # Error and retry handling
    error_count: int = Field(default=0, ge=0, description="Number of errors encountered in session")
    retry_count: int = Field(default=0, ge=0, description="Number of retries attempted for current operation")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    last_error: Optional[str] = Field(None, description="Last error message")

    # Context and handoff
    context_summary: Optional[ContextSummary] = Field(None, description="Summary of conversation context for agent handoff")
    participant_states: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Individual participant states")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional orchestration metadata")

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="State creation timestamp")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp")
    last_activity_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last activity timestamp")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @validator('state_id')
    def validate_state_id(cls, v):
        """Validate state ID is not empty."""
        if not v.strip():
            raise ValueError("state_id cannot be empty")
        return v.strip()

    @validator('session_id')
    def validate_session_id(cls, v):
        """Validate session ID is not empty."""
        if not v.strip():
            raise ValueError("session_id cannot be empty")
        return v.strip()

    @validator('active_agent')
    def validate_active_agent(cls, v):
        """Validate active agent if specified."""
        if v is not None:
            valid_agents = ["claude_code", "codex_cli", "orchestrator"]
            if v not in valid_agents:
                raise ValueError(f"Unknown agent type: {v}")
        return v

    @validator('timeout_deadline')
    def validate_timeout_deadline(cls, v):
        """Ensure timeout deadline is in the future."""
        if v is not None:
            now = datetime.now(timezone.utc)
            if v <= now:
                raise ValueError("timeout_deadline must be in the future")
        return v

    @validator('updated_at', 'last_activity_at', always=True)
    def validate_timestamps(cls, v, values, field):
        """Validate timestamp relationships."""
        if 'created_at' in values and v < values['created_at']:
            raise ValueError(f"{field.name} cannot be before created_at")
        return v

    def transition_flow(self, new_flow: ConversationFlow, reason: Optional[str] = None) -> bool:
        """
        Transition conversation flow following defined state machine.

        Args:
            new_flow: Target flow state
            reason: Optional reason for transition

        Returns:
            True if transition was successful
        """
        valid_transitions = {
            ConversationFlow.WAITING: [ConversationFlow.PROCESSING, ConversationFlow.FAILED],
            ConversationFlow.PROCESSING: [ConversationFlow.WAITING, ConversationFlow.CONVERGING, ConversationFlow.FAILED],
            ConversationFlow.CONVERGING: [ConversationFlow.COMPLETED, ConversationFlow.WAITING, ConversationFlow.FAILED],
            ConversationFlow.COMPLETED: [],  # Terminal state
            ConversationFlow.FAILED: []      # Terminal state
        }

        if new_flow not in valid_transitions.get(self.conversation_flow, []):
            return False

        old_flow = self.conversation_flow
        self.conversation_flow = new_flow
        self.updated_at = datetime.now(timezone.utc)

        # Record transition in metadata
        if 'flow_transitions' not in self.metadata:
            self.metadata['flow_transitions'] = []

        self.metadata['flow_transitions'].append({
            'from_flow': old_flow,
            'to_flow': new_flow,
            'timestamp': self.updated_at.isoformat(),
            'reason': reason
        })

        return True

    def set_active_agent(self, agent_id: str, timeout_seconds: Optional[int] = None) -> None:
        """
        Set the active agent and establish timeout.

        Args:
            agent_id: ID of the agent to set as active
            timeout_seconds: Optional timeout override
        """
        self.active_agent = agent_id
        self.updated_at = datetime.now(timezone.utc)
        self.last_activity_at = self.updated_at

        # Set timeout deadline
        timeout = timeout_seconds or self.operation_timeout_seconds
        self.timeout_deadline = self.updated_at + timedelta(seconds=timeout)

        # Update participant state
        if agent_id not in self.participant_states:
            self.participant_states[agent_id] = {}

        self.participant_states[agent_id].update({
            'status': 'active',
            'activated_at': self.updated_at.isoformat(),
            'timeout_deadline': self.timeout_deadline.isoformat()
        })

    def advance_turn(self) -> bool:
        """
        Advance to the next turn.

        Returns:
            True if turn was advanced successfully, False if budget exhausted
        """
        if self.turn_budget_remaining <= 0:
            self.transition_flow(ConversationFlow.FAILED, "Turn budget exhausted")
            return False

        self.current_turn += 1
        self.turn_budget_remaining -= 1
        self.updated_at = datetime.now(timezone.utc)
        self.last_activity_at = self.updated_at

        return True

    def update_budget(self, cost_usd: float) -> bool:
        """
        Update remaining cost budget.

        Args:
            cost_usd: Cost to deduct from budget

        Returns:
            True if budget was updated successfully, False if budget exhausted
        """
        if cost_usd < 0:
            raise ValueError("Cost cannot be negative")

        new_remaining = self.cost_budget_remaining - cost_usd

        if new_remaining < 0:
            self.transition_flow(ConversationFlow.FAILED, "Cost budget exhausted")
            return False

        self.cost_budget_remaining = new_remaining
        self.updated_at = datetime.now(timezone.utc)

        return True

    def add_convergence_signal(self, signal_type: str, value: Union[bool, float, str], confidence: float = 0.5, source_agent: Optional[str] = None) -> None:
        """
        Add a convergence signal.

        Args:
            signal_type: Type of signal
            value: Signal value
            confidence: Confidence in signal
            source_agent: Agent that provided the signal
        """
        signal = ConvergenceSignal(
            signal_type=signal_type,
            value=value,
            confidence=confidence,
            source_agent=source_agent
        )

        self.convergence_signals.append(signal)
        self.updated_at = datetime.now(timezone.utc)

        # Check if convergence threshold is met
        self._evaluate_convergence()

    def _evaluate_convergence(self) -> None:
        """Evaluate whether convergence has been reached."""
        if not self.convergence_signals:
            return

        # Calculate weighted average confidence across all signals
        total_weight = 0.0
        weighted_sum = 0.0

        for signal in self.convergence_signals:
            # Weight boolean signals based on their truth value
            if isinstance(signal.value, bool):
                signal_strength = 1.0 if signal.value else 0.0
            elif isinstance(signal.value, (int, float)):
                signal_strength = float(signal.value)
            else:
                signal_strength = 0.5  # Default for string values

            weight = signal.confidence
            weighted_sum += signal_strength * weight
            total_weight += weight

        if total_weight > 0:
            convergence_score = weighted_sum / total_weight
            self.convergence_detected = convergence_score >= self.convergence_threshold

            # Store convergence score in metadata
            self.metadata['convergence_score'] = convergence_score

            if self.convergence_detected and self.conversation_flow == ConversationFlow.PROCESSING:
                self.transition_flow(ConversationFlow.CONVERGING, f"Convergence detected (score: {convergence_score:.2f})")

    def record_error(self, error_message: str, allow_retry: bool = True) -> bool:
        """
        Record an error and determine if retry is allowed.

        Args:
            error_message: Error description
            allow_retry: Whether retry should be attempted

        Returns:
            True if retry should be attempted, False otherwise
        """
        self.error_count += 1
        self.last_error = error_message
        self.updated_at = datetime.now(timezone.utc)

        if allow_retry and self.retry_count < self.max_retries:
            self.retry_count += 1
            return True
        else:
            self.transition_flow(ConversationFlow.FAILED, f"Max retries exceeded: {error_message}")
            return False

    def reset_retry_count(self) -> None:
        """Reset retry count after successful operation."""
        self.retry_count = 0
        self.last_error = None
        self.updated_at = datetime.now(timezone.utc)

    def is_timeout_exceeded(self) -> bool:
        """Check if current operation has timed out."""
        if self.timeout_deadline is None:
            return False

        return datetime.now(timezone.utc) > self.timeout_deadline

    def update_context_summary(self, summary: ContextSummary) -> None:
        """
        Update conversation context summary.

        Args:
            summary: New context summary
        """
        self.context_summary = summary
        self.updated_at = datetime.now(timezone.utc)

    def can_continue(self) -> bool:
        """Check if conversation can continue."""
        return (
            self.conversation_flow in [ConversationFlow.WAITING, ConversationFlow.PROCESSING, ConversationFlow.CONVERGING] and
            self.cost_budget_remaining > 0 and
            self.turn_budget_remaining > 0 and
            not self.is_timeout_exceeded()
        )

    def get_participant_status(self, agent_id: str) -> Dict[str, Any]:
        """
        Get status of a specific participant.

        Args:
            agent_id: Agent identifier

        Returns:
            Participant status dictionary
        """
        return self.participant_states.get(agent_id, {
            'status': 'inactive',
            'last_seen': None
        })

    def to_status_summary(self) -> Dict[str, Any]:
        """Generate status summary for monitoring."""
        return {
            "state_id": self.state_id,
            "session_id": self.session_id,
            "current_turn": self.current_turn,
            "active_agent": self.active_agent,
            "conversation_flow": self.conversation_flow,
            "convergence_detected": self.convergence_detected,
            "convergence_score": self.metadata.get('convergence_score', 0.0),
            "budget_remaining": {
                "cost_usd": self.cost_budget_remaining,
                "turns": self.turn_budget_remaining
            },
            "timeout_deadline": self.timeout_deadline.isoformat() if self.timeout_deadline else None,
            "error_count": self.error_count,
            "retry_count": self.retry_count,
            "can_continue": self.can_continue(),
            "updated_at": self.updated_at.isoformat()
        }