"""Abstract interfaces for conversation session service.

Defines the IConversationSessionService interface for standardized
session management across different implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import Field, validate_call
from src.tab.models.conversation_session import ConversationSession
from src.tab.models.turn_message import TurnMessage


class IConversationSessionService(ABC):
    """Abstract interface for conversation session management."""

    @validate_call
    @abstractmethod
    async def create_session(
        self,
        topic: str,
        participants: List[str],
        policy_id: str = "default",
        max_turns: int = 8,
        **kwargs
    ) -> ConversationSession:
        """Create new conversation session with validation."""
        pass

    @validate_call
    @abstractmethod
    async def get_session(
        self,
        session_id: str
    ) -> Optional[ConversationSession]:
        """Retrieve session by ID."""
        pass

    @validate_call
    @abstractmethod
    async def add_turn_to_session(
        self,
        session_id: str,
        turn: TurnMessage
    ) -> bool:
        """Add turn with policy validation."""
        pass

    @validate_call
    @abstractmethod
    async def get_session_context(
        self,
        session_id: str,
        agent_filter: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get conversation context with caching."""
        pass