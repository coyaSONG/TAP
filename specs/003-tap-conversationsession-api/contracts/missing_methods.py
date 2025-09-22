"""Contract definitions for missing ConversationSession methods.

These contracts define the expected behavior for methods that are missing
from the current ConversationSession implementation, causing runtime errors.
"""

from typing import Dict, Any, Protocol
from src.tab.models.conversation_session import ConversationSession


class ConversationSessionMissingMethodsContract(Protocol):
    """Contract for missing ConversationSession methods."""

    def should_auto_complete(self) -> bool:
        """Determine if conversation should auto-complete based on convergence.

        Returns:
            bool: True if conversation should be automatically completed

        Implementation Logic:
        - Check convergence signals via check_convergence_signals()
        - Return True if explicit_completion detected
        - Return True if resource_exhaustion with high confidence (>0.8)
        - Return True if repetitive_content with low progress
        - Otherwise return False

        Raises:
            RuntimeError: If convergence analysis fails
        """
        ...

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get comprehensive conversation summary statistics.

        Returns:
            Dict containing:
            - total_turns: int - Number of turns in conversation
            - total_cost: float - Total cost accumulated (if applicable)
            - avg_turn_length: float - Average length of turn content
            - participants_activity: Dict[str, int] - Turn count per participant
            - duration_minutes: float - Conversation duration in minutes
            - convergence_confidence: float - Current convergence confidence (0.0-1.0)
            - topic: str - Conversation topic
            - status: str - Current session status

        Raises:
            ValueError: If session data is invalid
        """
        ...

    def get_session_status(self) -> Dict[str, Any]:
        """Get detailed current session status information.

        Returns:
            Dict containing:
            - status: str - Current SessionStatus value
            - turn_progress: Dict[str, int] - {"current": X, "max": Y}
            - budget_progress: Dict[str, float] - {"used": X, "total": Y} (if applicable)
            - health_indicators: List[str] - Status indicators and warnings
            - next_actions: List[str] - Suggested next actions
            - last_activity: str - ISO timestamp of last activity
            - active_since: str - ISO timestamp when session became active

        Raises:
            RuntimeError: If session state is inconsistent
        """
        ...


# Response schemas for validation

SHOULD_AUTO_COMPLETE_RESPONSE_SCHEMA = {
    "type": "boolean",
    "description": "Whether conversation should be automatically completed"
}

SUMMARY_STATS_RESPONSE_SCHEMA = {
    "type": "object",
    "required": [
        "total_turns", "total_cost", "avg_turn_length",
        "participants_activity", "duration_minutes", "convergence_confidence",
        "topic", "status"
    ],
    "properties": {
        "total_turns": {"type": "integer", "minimum": 0},
        "total_cost": {"type": "number", "minimum": 0},
        "avg_turn_length": {"type": "number", "minimum": 0},
        "participants_activity": {
            "type": "object",
            "patternProperties": {
                ".*": {"type": "integer", "minimum": 0}
            }
        },
        "duration_minutes": {"type": "number", "minimum": 0},
        "convergence_confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0
        },
        "topic": {"type": "string", "minLength": 1},
        "status": {
            "type": "string",
            "enum": ["active", "completed", "failed", "timeout"]
        }
    }
}

SESSION_STATUS_RESPONSE_SCHEMA = {
    "type": "object",
    "required": [
        "status", "turn_progress", "budget_progress",
        "health_indicators", "next_actions", "last_activity", "active_since"
    ],
    "properties": {
        "status": {
            "type": "string",
            "enum": ["active", "completed", "failed", "timeout"]
        },
        "turn_progress": {
            "type": "object",
            "required": ["current", "max"],
            "properties": {
                "current": {"type": "integer", "minimum": 0},
                "max": {"type": "integer", "minimum": 1}
            }
        },
        "budget_progress": {
            "type": "object",
            "required": ["used", "total"],
            "properties": {
                "used": {"type": "number", "minimum": 0},
                "total": {"type": "number", "minimum": 0}
            }
        },
        "health_indicators": {
            "type": "array",
            "items": {"type": "string"}
        },
        "next_actions": {
            "type": "array",
            "items": {"type": "string"}
        },
        "last_activity": {"type": "string", "format": "date-time"},
        "active_since": {"type": "string", "format": "date-time"}
    }
}

# Example valid responses

EXAMPLE_SHOULD_AUTO_COMPLETE_TRUE = True

EXAMPLE_SHOULD_AUTO_COMPLETE_FALSE = False

EXAMPLE_SUMMARY_STATS = {
    "total_turns": 6,
    "total_cost": 0.45,
    "avg_turn_length": 287.5,
    "participants_activity": {
        "claude_code": 3,
        "codex_cli": 3
    },
    "duration_minutes": 12.5,
    "convergence_confidence": 0.7,
    "topic": "Implement user authentication system",
    "status": "active"
}

EXAMPLE_SESSION_STATUS = {
    "status": "active",
    "turn_progress": {
        "current": 6,
        "max": 8
    },
    "budget_progress": {
        "used": 0.45,
        "total": 1.0
    },
    "health_indicators": [
        "Normal conversation flow",
        "Both agents responsive",
        "Within budget limits"
    ],
    "next_actions": [
        "Continue conversation",
        "Monitor for completion signals",
        "Check convergence after 2 more turns"
    ],
    "last_activity": "2025-09-22T10:35:42Z",
    "active_since": "2025-09-22T10:30:00Z"
}

# Contract validation helpers

def validate_should_auto_complete_contract(method_impl) -> bool:
    """Validate should_auto_complete method implements contract correctly."""
    import inspect

    # Check method signature
    sig = inspect.signature(method_impl)
    if len(sig.parameters) != 1:  # self only
        return False

    # Check return type annotation
    if sig.return_annotation != bool:
        return False

    return True

def validate_summary_stats_contract(method_impl) -> bool:
    """Validate get_summary_stats method implements contract correctly."""
    import inspect

    # Check method signature
    sig = inspect.signature(method_impl)
    if len(sig.parameters) != 1:  # self only
        return False

    # Check return type annotation
    if sig.return_annotation != Dict[str, Any]:
        return False

    return True

def validate_session_status_contract(method_impl) -> bool:
    """Validate get_session_status method implements contract correctly."""
    import inspect

    # Check method signature
    sig = inspect.signature(method_impl)
    if len(sig.parameters) != 1:  # self only
        return False

    # Check return type annotation
    if sig.return_annotation != Dict[str, Any]:
        return False

    return True