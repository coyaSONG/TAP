"""Abstract interfaces for service lifecycle management.

Defines the IServiceLifecycle interface for standardized service
initialization, startup, and shutdown patterns.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class IServiceLifecycle(ABC):
    """Interface for service lifecycle management."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize service resources."""
        pass

    @abstractmethod
    async def start(self) -> None:
        """Start service operations."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop service gracefully."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform service health check."""
        pass