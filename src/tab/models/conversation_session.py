"""ConversationSession model with state transitions and validation."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import uuid4
import re

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

        # Check for duplicates
        if len(set(v)) != len(v):
            raise ValueError("Duplicate participants not allowed")

        # Validate agent IDs are non-empty strings
        for participant in v:
            if not isinstance(participant, str) or not participant.strip():
                raise ValueError("All participants must be non-empty strings")

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

    def add_turn_message(self, turn) -> bool:
        """Add a new turn message to the conversation with validation.

        Args:
            turn: TurnMessage instance to add to the conversation

        Returns:
            bool: True if turn was added successfully, False if constraints violated

        Raises:
            ValueError: If session constraints are violated or turn is invalid
        """
        # Import here to avoid circular dependency
        from .turn_message import TurnMessage

        # Validate turn is a TurnMessage instance
        if not isinstance(turn, TurnMessage):
            raise ValueError(f"Expected TurnMessage instance, got {type(turn)}")

        # Validate session can accept new turns
        if not self.can_add_turn():
            return False

        # Validate turn belongs to this session
        if turn.session_id != self.session_id:
            raise ValueError(f"Turn session_id {turn.session_id} does not match session {self.session_id}")

        # Validate turn author is a participant
        if turn.from_agent not in self.participants:
            raise ValueError(f"Turn author {turn.from_agent} is not a participant in this session")

        # Add turn to history
        self.turn_history.append(turn)

        # Update session state
        self.current_turn += 1
        if turn.cost_usd:
            self.total_cost_usd += turn.cost_usd
        self.updated_at = datetime.now(timezone.utc)

        return True

    def get_conversation_context(
        self,
        agent_filter: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve recent conversation context for agent consumption.

        Args:
            agent_filter: Optional agent ID to filter turns by (from_agent or to_agent)
            limit: Maximum number of recent turns to return (default: 5)

        Returns:
            List[Dict[str, Any]]: List of turn messages in standard chat format

        Raises:
            ValueError: If limit is invalid or agent_filter is unknown
        """
        # Import here to avoid circular dependency
        from .turn_message import TurnMessage

        # Validate parameters
        if limit <= 0:
            raise ValueError("Limit must be positive")
        if limit > 50:  # Reasonable upper bound
            raise ValueError("Limit cannot exceed 50 turns for performance reasons")

        if agent_filter and agent_filter not in self.participants + ["orchestrator"]:
            raise ValueError(f"Unknown agent filter: {agent_filter}")

        # Filter turns by agent if specified
        relevant_turns = []
        for turn in self.turn_history:
            if isinstance(turn, TurnMessage):
                if agent_filter is None or turn.from_agent == agent_filter or turn.to_agent == agent_filter:
                    relevant_turns.append(turn)

        # Get the most recent turns (up to limit)
        recent_turns = relevant_turns[-limit:] if relevant_turns else []

        # Convert to standard chat format
        context = []
        for turn in recent_turns:
            if isinstance(turn, TurnMessage):
                context.append(turn.to_chat_format())

        return context

    def check_convergence_signals(self) -> Dict[str, Any]:
        """Analyze conversation for completion indicators.

        Returns:
            Dict[str, Any]: Structured convergence assessment with recommendations
        """
        # Import here to avoid circular dependency
        from .turn_message import TurnMessage

        # Initialize analysis results
        analysis = {
            "should_continue": True,
            "confidence": 0.5,
            "signals": {
                "repetitive_content": False,
                "explicit_completion": False,
                "resource_exhaustion": False,
                "quality_degradation": False
            },
            "recommendations": [],
            "metadata": {
                "turns_analyzed": len(self.turn_history),
                "avg_turn_length": 0.0,
                "completion_keywords": []
            }
        }

        # No turns to analyze
        if not self.turn_history:
            analysis["recommendations"].append("No conversation history to analyze")
            return analysis

        # Filter valid TurnMessage instances
        valid_turns = [turn for turn in self.turn_history if isinstance(turn, TurnMessage)]
        analysis["metadata"]["turns_analyzed"] = len(valid_turns)

        if not valid_turns:
            analysis["recommendations"].append("No valid turn messages found")
            return analysis

        # Calculate average turn length
        total_length = sum(len(turn.content) for turn in valid_turns)
        analysis["metadata"]["avg_turn_length"] = total_length / len(valid_turns)

        # Check for explicit completion keywords
        completion_keywords = [
            "completed", "finished", "done", "solved", "resolved",
            "task complete", "implementation complete", "success",
            "no further action", "ready for review"
        ]

        found_keywords = []
        recent_content = ""

        # Analyze recent turns (last 3)
        recent_turns = valid_turns[-3:] if len(valid_turns) >= 3 else valid_turns
        for turn in recent_turns:
            recent_content += " " + turn.content.lower()

        # Check for completion keywords
        for keyword in completion_keywords:
            if keyword in recent_content:
                found_keywords.append(keyword)
                analysis["signals"]["explicit_completion"] = True

        analysis["metadata"]["completion_keywords"] = found_keywords

        # Check for repetitive content
        if len(recent_turns) >= 3:
            contents = [turn.content.lower().strip() for turn in recent_turns]
            # Simple repetition check - similar content in recent turns
            similarities = 0
            for i in range(len(contents)-1):
                for j in range(i+1, len(contents)):
                    # Check for significant overlap (>70% common words)
                    words1 = set(contents[i].split())
                    words2 = set(contents[j].split())
                    if len(words1) > 0 and len(words2) > 0:
                        overlap = len(words1.intersection(words2))
                        total_unique = len(words1.union(words2))
                        if total_unique > 0 and overlap / total_unique > 0.7:
                            similarities += 1

            if similarities >= 2:
                analysis["signals"]["repetitive_content"] = True

        # Check resource exhaustion
        resource_exhaustion = False
        if self.current_turn >= self.max_turns * 0.9:  # 90% of max turns
            resource_exhaustion = True
        if self.total_cost_usd >= self.budget_usd * 0.9:  # 90% of budget
            resource_exhaustion = True

        analysis["signals"]["resource_exhaustion"] = resource_exhaustion

        # Check quality degradation (very basic heuristic)
        if len(recent_turns) >= 3:
            recent_lengths = [len(turn.content) for turn in recent_turns]
            if all(length < 50 for length in recent_lengths[-2:]):  # Very short recent responses
                analysis["signals"]["quality_degradation"] = True

        # Generate recommendations based on signals
        signals_detected = sum(analysis["signals"].values())

        if analysis["signals"]["explicit_completion"]:
            analysis["should_continue"] = False
            analysis["confidence"] = 0.9
            analysis["recommendations"].append("Conversation appears to be complete based on explicit completion signals")
        elif analysis["signals"]["resource_exhaustion"]:
            analysis["should_continue"] = False
            analysis["confidence"] = 0.8
            analysis["recommendations"].append("Approaching resource limits - consider wrapping up conversation")
        elif analysis["signals"]["repetitive_content"]:
            analysis["should_continue"] = True
            analysis["confidence"] = 0.3
            analysis["recommendations"].append("Detected repetitive content - consider changing approach or ending conversation")
        elif analysis["signals"]["quality_degradation"]:
            analysis["should_continue"] = True
            analysis["confidence"] = 0.4
            analysis["recommendations"].append("Response quality appears to be declining - consider intervention")
        else:
            # No negative signals detected
            analysis["should_continue"] = True
            analysis["confidence"] = 0.8
            analysis["recommendations"].append("Conversation appears to be progressing well")

        # Add turn/budget status
        if self.current_turn < self.max_turns * 0.5:
            analysis["recommendations"].append(f"Turn count healthy: {self.current_turn}/{self.max_turns}")
        else:
            analysis["recommendations"].append(f"Monitor turn usage: {self.current_turn}/{self.max_turns}")

        if self.total_cost_usd < self.budget_usd * 0.5:
            analysis["recommendations"].append(f"Budget healthy: ${self.total_cost_usd:.3f}/${self.budget_usd}")
        else:
            analysis["recommendations"].append(f"Monitor budget usage: ${self.total_cost_usd:.3f}/${self.budget_usd}")

        return analysis

    def should_auto_complete(self) -> bool:
        """Determine if conversation should auto-complete based on convergence signals.

        Returns:
            bool: True if conversation should be automatically completed

        Implementation based on check_convergence_signals() results:
        - explicit_completion signals → True
        - resource_exhaustion + high confidence → True
        - repetitive_content + low progress → True
        - Otherwise → False
        """
        try:
            convergence = self.check_convergence_signals()

            # Explicit completion signals indicate conversation is done
            if convergence["signals"]["explicit_completion"]:
                return True

            # Resource exhaustion with high confidence suggests ending
            if (convergence["signals"]["resource_exhaustion"] and
                convergence["confidence"] > 0.8):
                return True

            # Repetitive content with low confidence suggests stuck conversation
            if (convergence["signals"]["repetitive_content"] and
                convergence["confidence"] < 0.4):
                return True

            # Quality degradation suggests ending conversation
            if convergence["signals"]["quality_degradation"]:
                return True

            return False

        except Exception:
            # If convergence analysis fails, don't auto-complete
            return False

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get comprehensive conversation summary statistics.

        Returns:
            Dict containing:
            - total_turns: int - Number of turns in conversation
            - total_cost: float - Total cost accumulated
            - avg_turn_length: float - Average length of turn content
            - participants_activity: Dict[str, int] - Turn count per participant
            - duration_minutes: float - Conversation duration in minutes
            - convergence_confidence: float - Current convergence confidence (0.0-1.0)
            - topic: str - Conversation topic
            - status: str - Current session status
        """
        from .turn_message import TurnMessage

        # Calculate total turns
        total_turns = len([turn for turn in self.turn_history if isinstance(turn, TurnMessage)])

        # Calculate participant activity
        participants_activity = {participant: 0 for participant in self.participants}
        total_content_length = 0

        for turn in self.turn_history:
            if isinstance(turn, TurnMessage):
                participants_activity[turn.from_agent] = participants_activity.get(turn.from_agent, 0) + 1
                total_content_length += len(turn.content)

        # Calculate average turn length
        avg_turn_length = total_content_length / total_turns if total_turns > 0 else 0.0

        # Calculate duration
        duration_minutes = (self.updated_at - self.created_at).total_seconds() / 60.0

        # Get convergence confidence
        try:
            convergence = self.check_convergence_signals()
            convergence_confidence = convergence["confidence"]
        except Exception:
            convergence_confidence = 0.5

        return {
            "total_turns": total_turns,
            "total_cost": self.total_cost_usd,
            "avg_turn_length": avg_turn_length,
            "participants_activity": participants_activity,
            "duration_minutes": duration_minutes,
            "convergence_confidence": convergence_confidence,
            "topic": self.topic,
            "status": self.status.value
        }

    def get_session_status(self) -> Dict[str, Any]:
        """Get detailed current session status information.

        Returns:
            Dict containing:
            - status: str - Current SessionStatus value
            - turn_progress: Dict[str, int] - {"current": X, "max": Y}
            - budget_progress: Dict[str, float] - {"used": X, "total": Y}
            - health_indicators: List[str] - Status indicators and warnings
            - next_actions: List[str] - Suggested next actions
            - last_activity: str - ISO timestamp of last activity
            - active_since: str - ISO timestamp when session became active
        """
        health_indicators = []
        next_actions = []

        # Analyze session health
        turn_percentage = (self.current_turn / self.max_turns) * 100 if self.max_turns > 0 else 0
        budget_percentage = (self.total_cost_usd / self.budget_usd) * 100 if self.budget_usd > 0 else 0

        # Turn health indicators
        if turn_percentage < 50:
            health_indicators.append("Turn usage healthy")
        elif turn_percentage < 90:
            health_indicators.append("Moderate turn usage")
        else:
            health_indicators.append("High turn usage - approaching limit")

        # Budget health indicators
        if budget_percentage < 50:
            health_indicators.append("Budget usage healthy")
        elif budget_percentage < 90:
            health_indicators.append("Moderate budget usage")
        else:
            health_indicators.append("High budget usage - approaching limit")

        # Participant activity
        if len(self.participants) == len(set(turn.from_agent for turn in self.turn_history if hasattr(turn, 'from_agent'))):
            health_indicators.append("All participants active")
        else:
            health_indicators.append("Some participants inactive")

        # Generate next actions based on status and health
        if self.status == SessionStatus.ACTIVE:
            if turn_percentage > 80 or budget_percentage > 80:
                next_actions.append("Consider wrapping up conversation")
            else:
                next_actions.append("Continue conversation")

            # Check convergence for additional actions
            try:
                convergence = self.check_convergence_signals()
                if not convergence["should_continue"]:
                    next_actions.append("Conversation may be ready for completion")
                else:
                    next_actions.append("Monitor for completion signals")
            except Exception:
                next_actions.append("Check convergence status")

        elif self.status == SessionStatus.COMPLETED:
            next_actions.append("Session completed successfully")
        elif self.status == SessionStatus.FAILED:
            next_actions.append("Review failure reason and consider restart")
        elif self.status == SessionStatus.TIMEOUT:
            next_actions.append("Session timed out - consider extending or restarting")

        return {
            "status": self.status.value,
            "turn_progress": {
                "current": self.current_turn,
                "max": self.max_turns
            },
            "budget_progress": {
                "used": self.total_cost_usd,
                "total": self.budget_usd
            },
            "health_indicators": health_indicators,
            "next_actions": next_actions,
            "last_activity": self.updated_at.isoformat(),
            "active_since": self.created_at.isoformat()
        }