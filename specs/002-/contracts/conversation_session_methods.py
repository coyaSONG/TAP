"""API contracts for ConversationSession method extensions.

These contracts define the expected behavior and signatures for the missing
ConversationSession methods. Used for contract testing and implementation validation.
"""

from typing import Dict, Any, List, Optional, Protocol
from src.tab.models.turn_message import TurnMessage


class ConversationSessionMethodsProtocol(Protocol):
    """Protocol defining the required method signatures for ConversationSession extensions."""

    def add_turn_message(self, turn: TurnMessage) -> bool:
        """Add a new turn to the conversation with validation.

        Args:
            turn: Validated TurnMessage instance to add

        Returns:
            True if turn was added successfully, False if constraints violated

        Raises:
            ValidationError: If turn data is invalid
            ValueError: If session constraints are violated
        """
        ...

    def get_conversation_context(
        self,
        agent_filter: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve recent conversation context for agent consumption.

        Args:
            agent_filter: Optional agent ID to filter turns by
            limit: Maximum number of recent turns to return

        Returns:
            List of turn messages in standard chat format

        Raises:
            ValueError: If limit is invalid or agent_filter is unknown
        """
        ...

    def check_convergence_signals(self) -> Dict[str, Any]:
        """Analyze conversation for completion indicators.

        Returns:
            Structured convergence assessment with recommendations

        The return structure includes:
        - should_continue: bool indicating if conversation should continue
        - confidence: float (0.0-1.0) confidence in the assessment
        - signals: dict of detected convergence indicators
        - recommendations: list of suggested actions
        - metadata: analysis metadata and statistics
        """
        ...


# Expected return type schemas for validation

ADD_TURN_MESSAGE_RESPONSE_SCHEMA = {
    "type": "boolean",
    "description": "Success indicator for turn addition"
}

GET_CONVERSATION_CONTEXT_RESPONSE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["role", "content", "from_agent", "timestamp"],
        "properties": {
            "role": {
                "type": "string",
                "enum": ["user", "assistant", "system"]
            },
            "content": {
                "type": "string",
                "minLength": 1
            },
            "from_agent": {
                "type": "string",
                "minLength": 1
            },
            "timestamp": {
                "type": "string",
                "format": "date-time"
            },
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

CHECK_CONVERGENCE_SIGNALS_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["should_continue", "confidence", "signals", "recommendations", "metadata"],
    "properties": {
        "should_continue": {"type": "boolean"},
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0
        },
        "signals": {
            "type": "object",
            "required": ["repetitive_content", "explicit_completion", "resource_exhaustion", "quality_degradation"],
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
            "required": ["turns_analyzed", "avg_turn_length"],
            "properties": {
                "turns_analyzed": {"type": "integer", "minimum": 0},
                "avg_turn_length": {"type": "number", "minimum": 0},
                "completion_keywords": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        }
    }
}


# Example valid responses for testing

EXAMPLE_CONVERSATION_CONTEXT = [
    {
        "role": "assistant",
        "content": "I'll help you implement the missing methods.",
        "from_agent": "claude_code",
        "timestamp": "2025-09-22T10:30:00Z",
        "attachments": None
    },
    {
        "role": "user",
        "content": "Please add the add_turn_message method.",
        "from_agent": "codex_cli",
        "timestamp": "2025-09-22T10:29:00Z",
        "attachments": None
    }
]

EXAMPLE_CONVERGENCE_SIGNALS = {
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
        "avg_turn_length": 125.5,
        "completion_keywords": []
    }
}