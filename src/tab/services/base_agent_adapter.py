"""Base agent adapter interface with common functionality."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, AsyncIterator
from enum import Enum

from pydantic import BaseModel, Field

from tab.models.turn_message import TurnMessage, MessageRole
from tab.models.agent_adapter import AgentAdapter, AgentStatus


logger = logging.getLogger(__name__)


class ProcessingStatus(str, Enum):
    """Agent processing status."""

    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"
    TIMEOUT = "timeout"


class AgentResponse(BaseModel):
    """Standard response from an agent."""

    request_id: str = Field(..., description="Original request ID")
    status: str = Field(..., description="Response status")
    content: str = Field(..., description="Response content")
    reasoning: Optional[str] = Field(None, description="Agent's reasoning")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score")
    next_action_suggested: Optional[str] = Field(None, description="Suggested next action")
    evidence: List[Dict[str, Any]] = Field(default_factory=list, description="Supporting evidence")

    execution_time_ms: Optional[int] = Field(None, description="Execution time")
    cost_usd: Optional[float] = Field(None, description="Cost incurred")
    tokens_used: Optional[int] = Field(None, description="Tokens consumed")
    tools_used: List[str] = Field(default_factory=list, description="Tools utilized")
    files_accessed: List[str] = Field(default_factory=list, description="Files accessed")
    error_details: Optional[str] = Field(None, description="Error details if failed")

    convergence_signals: Dict[str, bool] = Field(
        default_factory=dict,
        description="Convergence indicators"
    )


class BaseAgentAdapter(ABC):
    """Base class for all agent adapters providing common functionality."""

    def __init__(self, agent_config: AgentAdapter):
        """Initialize the base adapter.

        Args:
            agent_config: Agent configuration from data model
        """
        self.config = agent_config
        self.logger = logging.getLogger(f"{__name__}.{agent_config.agent_id}")
        self._status = ProcessingStatus.IDLE
        self._current_session_id: Optional[str] = None
        self._active_requests: Dict[str, asyncio.Task] = {}
        self._health_status = AgentStatus.AVAILABLE
        self._last_health_check = datetime.now(timezone.utc)

    @property
    def agent_id(self) -> str:
        """Get agent identifier."""
        return self.config.agent_id

    @property
    def agent_type(self) -> str:
        """Get agent type."""
        return self.config.agent_type

    @property
    def status(self) -> ProcessingStatus:
        """Get current processing status."""
        return self._status

    @property
    def health_status(self) -> AgentStatus:
        """Get health status."""
        return self._health_status

    @abstractmethod
    async def process_request(
        self,
        request_id: str,
        content: str,
        context: Dict[str, Any],
        constraints: Dict[str, Any]
    ) -> AgentResponse:
        """Process a request from the orchestrator.

        Args:
            request_id: Unique request identifier
            content: Request content to process
            context: Conversation context and metadata
            constraints: Policy constraints and limits

        Returns:
            AgentResponse with processing results
        """
        pass

    @abstractmethod
    async def health_check(self, deep_check: bool = False) -> Dict[str, Any]:
        """Perform health check on the agent.

        Args:
            deep_check: Whether to perform comprehensive health check

        Returns:
            Health status information
        """
        pass

    async def reset_session(self, session_id: str, preserve_context: bool = False) -> Dict[str, Any]:
        """Reset or clear agent session state.

        Args:
            session_id: Session to reset, or 'all' for global reset
            preserve_context: Whether to preserve conversation context

        Returns:
            Reset operation results
        """
        sessions_reset = 0

        if session_id == "all":
            # Cancel all active requests
            for req_id, task in self._active_requests.items():
                if not task.done():
                    task.cancel()
                    sessions_reset += 1

            self._active_requests.clear()
            self._current_session_id = None
            self._status = ProcessingStatus.IDLE
            sessions_reset += 1
        else:
            # Reset specific session
            if self._current_session_id == session_id:
                self._current_session_id = None
                self._status = ProcessingStatus.IDLE
                sessions_reset = 1

        return {
            "status": "success",
            "sessions_reset": sessions_reset,
            "context_preserved": preserve_context
        }

    async def _execute_with_timeout(
        self,
        coro,
        timeout_seconds: int,
        request_id: str
    ) -> Any:
        """Execute a coroutine with timeout handling.

        Args:
            coro: Coroutine to execute
            timeout_seconds: Timeout in seconds
            request_id: Request identifier for tracking

        Returns:
            Coroutine result

        Raises:
            asyncio.TimeoutError: If execution times out
        """
        try:
            result = await asyncio.wait_for(coro, timeout=timeout_seconds)
            return result
        except asyncio.TimeoutError:
            self.logger.warning(f"Request {request_id} timed out after {timeout_seconds}s")
            self._status = ProcessingStatus.TIMEOUT
            raise
        except Exception as e:
            self.logger.error(f"Request {request_id} failed: {str(e)}")
            self._status = ProcessingStatus.ERROR
            raise

    def _validate_constraints(self, constraints: Dict[str, Any]) -> List[str]:
        """Validate policy constraints for the request.

        Args:
            constraints: Policy constraints to validate

        Returns:
            List of constraint violations
        """
        violations = []

        # Check execution time limits
        max_time = constraints.get('max_execution_time_ms', 120000)
        if max_time < 1000:
            violations.append("Execution time limit too low (minimum 1000ms)")

        # Check cost limits
        max_cost = constraints.get('max_cost_usd', 0.1)
        if max_cost < 0.001:
            violations.append("Cost limit too low (minimum $0.001)")

        # Check tool restrictions
        allowed_tools = constraints.get('allowed_tools', [])
        disallowed_tools = constraints.get('disallowed_tools', [])

        # Ensure no overlap between allowed and disallowed
        if allowed_tools and disallowed_tools:
            overlap = set(allowed_tools) & set(disallowed_tools)
            if overlap:
                violations.append(f"Tools cannot be both allowed and disallowed: {overlap}")

        return violations

    def _extract_convergence_signals(self, content: str, metadata: Dict[str, Any]) -> Dict[str, bool]:
        """Extract convergence signals from response content.

        Args:
            content: Response content to analyze
            metadata: Additional metadata

        Returns:
            Dictionary of convergence signals
        """
        content_lower = content.lower()

        signals = {
            'solution_proposed': any(
                keyword in content_lower
                for keyword in ['solution', 'proposal', 'recommend', 'suggest', 'fix']
            ),
            'consensus_reached': any(
                keyword in content_lower
                for keyword in ['agree', 'consensus', 'confirmed', 'verified', 'correct']
            ),
            'requires_verification': any(
                keyword in content_lower
                for keyword in ['verify', 'check', 'validate', 'test', 'confirm']
            ),
            'additional_input_needed': any(
                keyword in content_lower
                for keyword in ['need more', 'clarification', 'unclear', 'additional', 'help']
            ),
            'confidence_threshold_met': metadata.get('confidence', 0.0) >= 0.8
        }

        return signals

    async def _update_health_status(self) -> None:
        """Update health status based on current state."""
        try:
            health_result = await self.health_check(deep_check=False)
            if health_result.get('status') == 'healthy':
                self._health_status = AgentStatus.AVAILABLE
            elif health_result.get('status') == 'degraded':
                self._health_status = AgentStatus.BUSY
            else:
                self._health_status = AgentStatus.FAILED
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            self._health_status = AgentStatus.FAILED

        self._last_health_check = datetime.now(timezone.utc)

    def get_agent_info(self) -> Dict[str, Any]:
        """Get comprehensive agent information.

        Returns:
            Agent information dictionary
        """
        return {
            'agent_id': self.config.agent_id,
            'name': self.config.name,
            'type': self.config.agent_type,
            'version': self.config.version,
            'status': self._health_status.value,
            'last_health_check': self._last_health_check.isoformat(),
            'capabilities': self.config.capabilities,
            'active_requests': len(self._active_requests),
            'current_session': self._current_session_id,
            'processing_status': self._status.value
        }

    async def start(self) -> None:
        """Start the agent adapter."""
        self.logger.info(f"Starting agent adapter {self.agent_id}")
        await self._update_health_status()
        self.logger.info(f"Agent adapter {self.agent_id} started with status {self._health_status}")

    async def stop(self) -> None:
        """Stop the agent adapter and cleanup resources."""
        self.logger.info(f"Stopping agent adapter {self.agent_id}")

        # Cancel all active requests
        for req_id, task in self._active_requests.items():
            if not task.done():
                self.logger.info(f"Cancelling active request {req_id}")
                task.cancel()

        # Wait for all tasks to complete
        if self._active_requests:
            await asyncio.gather(*self._active_requests.values(), return_exceptions=True)

        self._active_requests.clear()
        self._status = ProcessingStatus.IDLE
        self._health_status = AgentStatus.MAINTENANCE

        self.logger.info(f"Agent adapter {self.agent_id} stopped")

    def __repr__(self) -> str:
        """String representation of the adapter."""
        return (
            f"{self.__class__.__name__}("
            f"agent_id='{self.agent_id}', "
            f"type='{self.agent_type}', "
            f"status='{self._status}', "
            f"health='{self._health_status}'"
            f")"
        )