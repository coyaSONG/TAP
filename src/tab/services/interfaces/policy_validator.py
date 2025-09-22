"""Abstract interfaces for policy validation.

Defines the IPolicyValidator interface for standardized policy enforcement
across different implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from src.tab.models.conversation_session import ConversationSession
from src.tab.models.turn_message import TurnMessage


class IPolicyValidator(ABC):
    """Interface for policy enforcement."""

    @abstractmethod
    async def validate_session_creation(
        self,
        policy_id: str,
        session_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate session creation against policy."""
        pass

    @abstractmethod
    async def validate_turn_addition(
        self,
        policy_id: str,
        session: ConversationSession,
        turn: TurnMessage
    ) -> Dict[str, Any]:
        """Validate turn addition against policy."""
        pass