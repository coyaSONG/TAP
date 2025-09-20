"""Conversation orchestrator service with turn management."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
from uuid import uuid4

from tab.models.conversation_session import ConversationSession, SessionStatus
from tab.models.turn_message import TurnMessage, MessageRole
from tab.models.orchestration_state import OrchestrationState, FlowState
from tab.models.agent_adapter import AgentAdapter, AgentStatus
from tab.services.base_agent_adapter import BaseAgentAdapter, AgentResponse
from tab.services.claude_code_adapter import ClaudeCodeAdapter
from tab.services.codex_adapter import CodexAdapter


logger = logging.getLogger(__name__)


class ConversationOrchestrator:
    """Orchestrates multi-agent conversations with turn management and flow control."""

    def __init__(self):
        """Initialize the conversation orchestrator."""
        self.logger = logging.getLogger(__name__)
        self._sessions: Dict[str, ConversationSession] = {}
        self._orchestration_states: Dict[str, OrchestrationState] = {}
        self._agent_adapters: Dict[str, BaseAgentAdapter] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._shutdown_event = asyncio.Event()

    async def initialize(self) -> None:
        """Initialize the orchestrator and agent adapters."""
        self.logger.info("Initializing conversation orchestrator")

        # Initialize agent adapters (this would normally be configured)
        await self._initialize_agent_adapters()

        self.logger.info("Conversation orchestrator initialized successfully")

    async def _initialize_agent_adapters(self) -> None:
        """Initialize default agent adapters."""
        # This is a simplified initialization - in production this would load from config

        # Claude Code adapter
        claude_config = AgentAdapter(
            agent_id="claude_code",
            agent_type="claude_code",
            name="Claude Code",
            version="1.0.0",
            capabilities=["code_analysis", "file_operations", "debugging", "testing"],
            connection_config={"mode": "headless", "output_format": "stream-json"},
            status=AgentStatus.AVAILABLE,
            session_manager={"max_sessions": 3, "timeout_minutes": 30},
            execution_limits={"max_time_seconds": 120, "max_cost_usd": 0.5}
        )

        # Codex CLI adapter
        codex_config = AgentAdapter(
            agent_id="codex_cli",
            agent_type="codex_cli",
            name="Codex CLI",
            version="1.0.0",
            capabilities=["code_execution", "bug_reproduction", "patch_generation", "analysis"],
            connection_config={"mode": "exec", "approval_mode": "auto"},
            status=AgentStatus.AVAILABLE,
            session_manager={"max_sessions": 2, "timeout_minutes": 45},
            execution_limits={"max_time_seconds": 180, "max_cost_usd": 1.0}
        )

        # Create adapter instances
        self._agent_adapters["claude_code"] = ClaudeCodeAdapter(claude_config)
        self._agent_adapters["codex_cli"] = CodexAdapter(codex_config)

        # Start all adapters
        for adapter in self._agent_adapters.values():
            await adapter.start()

    async def start_conversation(
        self,
        topic: str,
        participants: List[str],
        policy_id: str = "default",
        max_turns: int = 8,
        budget_usd: float = 1.0,
        **kwargs
    ) -> Dict[str, Any]:
        """Start a new multi-agent conversation session.

        Args:
            topic: Initial question or task description
            participants: List of agent identifiers to participate
            policy_id: Policy configuration to apply
            max_turns: Maximum conversation turns allowed
            budget_usd: Maximum cost budget in USD
            **kwargs: Additional session parameters

        Returns:
            Session creation response
        """
        try:
            # Validate participants
            if not self._validate_participants(participants):
                return {
                    "session_id": str(uuid4()),
                    "status": "failed",
                    "participants": participants,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "error": "Invalid or unavailable participants"
                }

            # Create conversation session
            session = ConversationSession(
                topic=topic,
                participants=participants,
                policy_config=policy_id,
                max_turns=max_turns,
                budget_usd=budget_usd,
                **kwargs
            )

            # Create orchestration state
            orchestration_state = OrchestrationState(
                session_id=session.session_id,
                active_agent=participants[0],  # Start with first participant
                conversation_flow=FlowState.WAITING,
                cost_budget_remaining=budget_usd,
                turn_budget_remaining=max_turns
            )

            # Store session and state
            self._sessions[session.session_id] = session
            self._orchestration_states[session.session_id] = orchestration_state

            self.logger.info(
                f"Started conversation {session.session_id} with participants {participants}"
            )

            return {
                "session_id": session.session_id,
                "status": "active",
                "participants": participants,
                "policy_applied": policy_id,
                "created_at": session.created_at.isoformat()
            }

        except Exception as e:
            self.logger.error(f"Failed to start conversation: {str(e)}")
            return {
                "session_id": str(uuid4()),
                "status": "failed",
                "participants": participants,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }

    async def send_message(
        self,
        session_id: str,
        content: str,
        to_agent: str = "auto",
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Send a message in an active conversation.

        Args:
            session_id: Target conversation session
            content: Message content to send
            to_agent: Target agent identifier or "auto"
            attachments: Optional file attachments

        Returns:
            Turn response with agent output
        """
        if session_id not in self._sessions:
            return {
                "turn_id": str(uuid4()),
                "response": {"content": "Session not found", "from_agent": "orchestrator"},
                "session_status": "failed",
                "convergence_detected": False
            }

        session = self._sessions[session_id]
        orchestration_state = self._orchestration_states[session_id]

        if session.status != SessionStatus.ACTIVE:
            return {
                "turn_id": str(uuid4()),
                "response": {"content": "Session not active", "from_agent": "orchestrator"},
                "session_status": session.status.value,
                "convergence_detected": False
            }

        try:
            # Determine target agent
            if to_agent == "auto":
                to_agent = self._select_next_agent(session, orchestration_state)

            # Validate agent availability
            if to_agent not in self._agent_adapters:
                raise ValueError(f"Unknown agent: {to_agent}")

            if self._agent_adapters[to_agent].health_status != AgentStatus.AVAILABLE:
                raise ValueError(f"Agent {to_agent} not available")

            # Create user message from orchestrator
            user_message = TurnMessage(
                session_id=session_id,
                from_agent="orchestrator",
                to_agent=to_agent,
                role=MessageRole.USER,
                content=content,
                attachments=attachments or []
            )

            # Add to session
            session.add_turn_message(user_message)
            orchestration_state.current_turn += 1
            orchestration_state.active_agent = to_agent
            orchestration_state.conversation_flow = FlowState.PROCESSING

            # Process with agent
            agent_response = await self._process_with_agent(
                to_agent,
                content,
                session,
                orchestration_state
            )

            # Create agent response message
            agent_message = TurnMessage(
                session_id=session_id,
                from_agent=to_agent,
                to_agent="orchestrator",
                role=MessageRole.ASSISTANT,
                content=agent_response.content,
                metadata={
                    "cost_usd": agent_response.cost_usd or 0.0,
                    "duration_ms": agent_response.execution_time_ms or 0,
                    "tokens_used": agent_response.tokens_used or 0,
                    "confidence": agent_response.confidence or 0.0,
                    "tools_used": agent_response.tools_used,
                    "reasoning": agent_response.reasoning
                }
            )

            # Update performance metrics
            if agent_response.cost_usd:
                agent_message.update_performance_metrics(
                    agent_response.execution_time_ms or 0,
                    agent_response.cost_usd,
                    agent_response.tokens_used or 0
                )

            # Add agent response to session
            session.add_turn_message(agent_message)

            # Update orchestration state
            orchestration_state.cost_budget_remaining -= agent_response.cost_usd or 0.0
            orchestration_state.turn_budget_remaining -= 1
            orchestration_state.conversation_flow = FlowState.WAITING

            # Check convergence
            convergence_detected = self._check_convergence(session, agent_response)
            if convergence_detected:
                orchestration_state.conversation_flow = FlowState.CONVERGING

            # Update session status if needed
            self._update_session_status(session, orchestration_state)

            return {
                "turn_id": agent_message.turn_id,
                "response": {
                    "content": agent_response.content,
                    "from_agent": to_agent,
                    "metadata": agent_message.metadata
                },
                "session_status": session.status.value,
                "convergence_detected": convergence_detected
            }

        except Exception as e:
            self.logger.error(f"Failed to process message in session {session_id}: {str(e)}")

            # Mark session as failed
            session.transition_to(SessionStatus.FAILED, str(e))
            orchestration_state.conversation_flow = FlowState.FAILED

            return {
                "turn_id": str(uuid4()),
                "response": {
                    "content": f"Processing failed: {str(e)}",
                    "from_agent": "orchestrator"
                },
                "session_status": "failed",
                "convergence_detected": False
            }

    async def get_session_status(
        self,
        session_id: str,
        include_history: bool = False
    ) -> Dict[str, Any]:
        """Get current status and history of a conversation session.

        Args:
            session_id: Session identifier to query
            include_history: Whether to include full turn history

        Returns:
            Session status information
        """
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self._sessions[session_id]
        orchestration_state = self._orchestration_states[session_id]

        response = {
            "session_id": session_id,
            "status": session.status.value,
            "participants": session.participants,
            "current_turn": session.current_turn,
            "total_cost_usd": session.total_cost_usd,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "budget_remaining": {
                "cost_usd": orchestration_state.cost_budget_remaining,
                "turns": orchestration_state.turn_budget_remaining
            }
        }

        if include_history:
            response["turn_history"] = [
                {
                    "turn_id": turn.turn_id,
                    "from_agent": turn.from_agent,
                    "to_agent": turn.to_agent,
                    "content": turn.content,
                    "timestamp": turn.timestamp.isoformat(),
                    "metadata": turn.metadata
                }
                for turn in session.turn_history
            ]

        return response

    def _validate_participants(self, participants: List[str]) -> bool:
        """Validate that all participants are available.

        Args:
            participants: List of agent identifiers

        Returns:
            True if all participants are valid and available
        """
        for participant in participants:
            if participant not in self._agent_adapters:
                self.logger.warning(f"Unknown agent: {participant}")
                return False

            adapter = self._agent_adapters[participant]
            if adapter.health_status != AgentStatus.AVAILABLE:
                self.logger.warning(f"Agent {participant} not available: {adapter.health_status}")
                return False

        return True

    def _select_next_agent(
        self,
        session: ConversationSession,
        orchestration_state: OrchestrationState
    ) -> str:
        """Select the next agent to handle the conversation.

        Args:
            session: Conversation session
            orchestration_state: Current orchestration state

        Returns:
            Agent identifier
        """
        # Simple round-robin for now
        current_index = session.participants.index(orchestration_state.active_agent)
        next_index = (current_index + 1) % len(session.participants)
        return session.participants[next_index]

    async def _process_with_agent(
        self,
        agent_id: str,
        content: str,
        session: ConversationSession,
        orchestration_state: OrchestrationState
    ) -> AgentResponse:
        """Process content with specified agent.

        Args:
            agent_id: Agent to process with
            content: Content to process
            session: Conversation session
            orchestration_state: Current state

        Returns:
            Agent response
        """
        adapter = self._agent_adapters[agent_id]

        # Build context for agent
        context = {
            "conversation_history": session.get_conversation_context(max_turns=5),
            "session_metadata": {
                "session_id": session.session_id,
                "topic": session.topic,
                "turn_number": orchestration_state.current_turn
            }
        }

        # Build constraints
        constraints = {
            "max_execution_time_ms": 120000,  # 2 minutes
            "max_cost_usd": min(0.5, orchestration_state.cost_budget_remaining),
            "permission_mode": "auto"  # This would come from policy
        }

        # Generate request ID
        request_id = f"{session.session_id}-turn-{orchestration_state.current_turn}"

        # Process with agent
        return await adapter.process_request(
            request_id=request_id,
            content=content,
            context=context,
            constraints=constraints
        )

    def _check_convergence(
        self,
        session: ConversationSession,
        agent_response: AgentResponse
    ) -> bool:
        """Check if conversation has converged.

        Args:
            session: Conversation session
            agent_response: Latest agent response

        Returns:
            True if convergence detected
        """
        # Check convergence signals from agent
        convergence_signals = agent_response.convergence_signals or {}

        # Session-level convergence check
        session_signals = session.check_convergence_signals()

        # Combine signals
        combined_signals = {**session_signals, **convergence_signals}

        # Simple convergence logic
        return (
            combined_signals.get('solution_proposed', False) and
            combined_signals.get('consensus_reached', False) and
            not combined_signals.get('additional_input_needed', False)
        )

    def _update_session_status(
        self,
        session: ConversationSession,
        orchestration_state: OrchestrationState
    ) -> None:
        """Update session status based on current state.

        Args:
            session: Conversation session
            orchestration_state: Current orchestration state
        """
        # Check for completion conditions
        if orchestration_state.conversation_flow == FlowState.CONVERGING:
            if session.should_auto_complete():
                session.transition_to(SessionStatus.COMPLETED, "Conversation converged")
                orchestration_state.conversation_flow = FlowState.COMPLETED

        # Check for budget/turn limits
        elif (orchestration_state.cost_budget_remaining <= 0 or
              orchestration_state.turn_budget_remaining <= 0):
            session.transition_to(SessionStatus.TIMEOUT, "Budget/turn limit exceeded")
            orchestration_state.conversation_flow = FlowState.TIMEOUT

    async def list_agents(self, include_capabilities: bool = False) -> Dict[str, Any]:
        """List available agents and their current status.

        Args:
            include_capabilities: Whether to include agent capabilities

        Returns:
            Agents list response
        """
        agents = []

        for agent_id, adapter in self._agent_adapters.items():
            agent_info = adapter.get_agent_info()

            if not include_capabilities:
                agent_info.pop('capabilities', None)

            agents.append(agent_info)

        return {"agents": agents}

    async def shutdown(self) -> None:
        """Shutdown the orchestrator and cleanup resources."""
        self.logger.info("Shutting down conversation orchestrator")

        # Signal shutdown
        self._shutdown_event.set()

        # Cancel active tasks
        for task in self._active_tasks.values():
            if not task.done():
                task.cancel()

        # Wait for tasks to complete
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)

        # Stop all agent adapters
        for adapter in self._agent_adapters.values():
            await adapter.stop()

        self.logger.info("Conversation orchestrator shut down")