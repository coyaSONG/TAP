"""
Metrics collection for conversation performance and system monitoring.

Provides comprehensive metrics for TAB orchestration, agent performance,
and conversation analytics using OpenTelemetry metrics.
"""

import time
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum

from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram, UpDownCounter, Gauge


class MetricType(Enum):
    """Types of metrics collected by TAB."""
    CONVERSATION = "conversation"
    AGENT = "agent"
    POLICY = "policy"
    SYSTEM = "system"


@dataclass
class ConversationMetrics:
    """Metrics for a conversation session."""
    session_id: str
    turn_count: int
    total_duration_ms: int
    total_cost_usd: float
    convergence_achieved: bool
    error_count: int
    participants: List[str]


@dataclass
class AgentMetrics:
    """Metrics for agent operations."""
    agent_id: str
    operation: str
    duration_ms: int
    cost_usd: float
    success: bool
    tokens_used: Optional[int] = None
    error_type: Optional[str] = None


class MetricsCollector:
    """Collects and manages TAB system metrics."""

    def __init__(self, meter: metrics.Meter):
        self.meter = meter
        self._setup_instruments()

    def _setup_instruments(self) -> None:
        """Setup OpenTelemetry metric instruments."""
        # Conversation metrics
        self.conversation_total = self.meter.create_counter(
            name="tab_conversations_total",
            description="Total number of conversations started",
            unit="1"
        )

        self.conversation_duration = self.meter.create_histogram(
            name="tab_conversation_duration_ms",
            description="Duration of conversation sessions",
            unit="ms"
        )

        self.conversation_turns = self.meter.create_histogram(
            name="tab_conversation_turns",
            description="Number of turns in conversations",
            unit="1"
        )

        self.conversation_cost = self.meter.create_histogram(
            name="tab_conversation_cost_usd",
            description="Cost of conversation sessions",
            unit="USD"
        )

        self.conversation_convergence = self.meter.create_counter(
            name="tab_conversation_convergence_total",
            description="Conversations that achieved convergence",
            unit="1"
        )

        # Agent metrics
        self.agent_requests = self.meter.create_counter(
            name="tab_agent_requests_total",
            description="Total agent requests by agent and operation",
            unit="1"
        )

        self.agent_duration = self.meter.create_histogram(
            name="tab_agent_duration_ms",
            description="Agent operation duration",
            unit="ms"
        )

        self.agent_cost = self.meter.create_histogram(
            name="tab_agent_cost_usd",
            description="Agent operation cost",
            unit="USD"
        )

        self.agent_tokens = self.meter.create_histogram(
            name="tab_agent_tokens_used",
            description="Tokens used by agent operations",
            unit="1"
        )

        self.agent_errors = self.meter.create_counter(
            name="tab_agent_errors_total",
            description="Agent operation errors by type",
            unit="1"
        )

        # System metrics
        self.active_sessions = self.meter.create_up_down_counter(
            name="tab_active_sessions",
            description="Number of active conversation sessions",
            unit="1"
        )

        self.agent_health = self.meter.create_gauge(
            name="tab_agent_health",
            description="Agent health status (1=healthy, 0=unhealthy)",
            unit="1"
        )

        # Policy metrics
        self.policy_evaluations = self.meter.create_counter(
            name="tab_policy_evaluations_total",
            description="Policy evaluation events",
            unit="1"
        )

        self.policy_denials = self.meter.create_counter(
            name="tab_policy_denials_total",
            description="Policy denial events",
            unit="1"
        )

    def record_conversation_started(
        self,
        session_id: str,
        participants: List[str],
        policy_id: str
    ) -> None:
        """Record a new conversation session start."""
        attributes = {
            "participants": ",".join(participants),
            "policy_id": policy_id,
            "participant_count": str(len(participants))
        }

        self.conversation_total.add(1, attributes)
        self.active_sessions.add(1, {"status": "active"})

    def record_conversation_completed(self, metrics: ConversationMetrics) -> None:
        """Record conversation completion metrics."""
        attributes = {
            "participants": ",".join(metrics.participants),
            "convergence": str(metrics.convergence_achieved),
            "participant_count": str(len(metrics.participants))
        }

        self.conversation_duration.record(metrics.total_duration_ms, attributes)
        self.conversation_turns.record(metrics.turn_count, attributes)
        self.conversation_cost.record(metrics.total_cost_usd, attributes)

        if metrics.convergence_achieved:
            self.conversation_convergence.add(1, attributes)

        self.active_sessions.add(-1, {"status": "active"})
        self.active_sessions.add(1, {"status": "completed"})

    def record_conversation_failed(
        self,
        session_id: str,
        error_type: str,
        duration_ms: int,
        participants: List[str]
    ) -> None:
        """Record conversation failure."""
        attributes = {
            "error_type": error_type,
            "participants": ",".join(participants),
            "participant_count": str(len(participants))
        }

        self.conversation_duration.record(duration_ms, attributes)
        self.active_sessions.add(-1, {"status": "active"})
        self.active_sessions.add(1, {"status": "failed"})

    def record_agent_operation(self, metrics: AgentMetrics) -> None:
        """Record agent operation metrics."""
        attributes = {
            "agent_id": metrics.agent_id,
            "operation": metrics.operation,
            "success": str(metrics.success)
        }

        self.agent_requests.add(1, attributes)
        self.agent_duration.record(metrics.duration_ms, attributes)
        self.agent_cost.record(metrics.cost_usd, attributes)

        if metrics.tokens_used is not None:
            self.agent_tokens.record(metrics.tokens_used, attributes)

        if not metrics.success and metrics.error_type:
            error_attributes = {
                "agent_id": metrics.agent_id,
                "operation": metrics.operation,
                "error_type": metrics.error_type
            }
            self.agent_errors.add(1, error_attributes)

    def record_agent_health(self, agent_id: str, healthy: bool) -> None:
        """Record agent health status."""
        attributes = {"agent_id": agent_id}
        health_value = 1.0 if healthy else 0.0
        self.agent_health.set(health_value, attributes)

    def record_policy_evaluation(
        self,
        policy_id: str,
        decision: str,
        agent_id: str,
        operation: str
    ) -> None:
        """Record policy evaluation event."""
        attributes = {
            "policy_id": policy_id,
            "decision": decision,
            "agent_id": agent_id,
            "operation": operation
        }

        self.policy_evaluations.add(1, attributes)

        if decision == "deny":
            self.policy_denials.add(1, attributes)


class ConversationTimer:
    """Context manager for timing conversation operations."""

    def __init__(self, metrics_collector: MetricsCollector, session_id: str):
        self.metrics_collector = metrics_collector
        self.session_id = session_id
        self.start_time: Optional[float] = None

    def __enter__(self) -> "ConversationTimer":
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.start_time is not None:
            duration_ms = int((time.time() - self.start_time) * 1000)
            # Duration will be recorded by the specific completion method


class AgentTimer:
    """Context manager for timing agent operations."""

    def __init__(
        self,
        metrics_collector: MetricsCollector,
        agent_id: str,
        operation: str
    ):
        self.metrics_collector = metrics_collector
        self.agent_id = agent_id
        self.operation = operation
        self.start_time: Optional[float] = None
        self.cost_usd: float = 0.0
        self.tokens_used: Optional[int] = None
        self.success: bool = True
        self.error_type: Optional[str] = None

    def __enter__(self) -> "AgentTimer":
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.start_time is not None:
            duration_ms = int((time.time() - self.start_time) * 1000)

            if exc_type is not None:
                self.success = False
                self.error_type = exc_type.__name__ if exc_type else "Unknown"

            agent_metrics = AgentMetrics(
                agent_id=self.agent_id,
                operation=self.operation,
                duration_ms=duration_ms,
                cost_usd=self.cost_usd,
                success=self.success,
                tokens_used=self.tokens_used,
                error_type=self.error_type
            )

            self.metrics_collector.record_agent_operation(agent_metrics)

    def set_cost(self, cost_usd: float) -> None:
        """Set the operation cost."""
        self.cost_usd = cost_usd

    def set_tokens(self, tokens_used: int) -> None:
        """Set the tokens used."""
        self.tokens_used = tokens_used


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def initialize_metrics(meter: metrics.Meter) -> MetricsCollector:
    """Initialize global metrics collector."""
    global _metrics_collector
    _metrics_collector = MetricsCollector(meter)
    return _metrics_collector


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    if _metrics_collector is None:
        raise RuntimeError("Metrics not initialized. Call initialize_metrics() first.")
    return _metrics_collector


@contextmanager
def time_conversation(session_id: str):
    """Context manager for timing conversation operations."""
    collector = get_metrics_collector()
    with ConversationTimer(collector, session_id) as timer:
        yield timer


@contextmanager
def time_agent_operation(agent_id: str, operation: str):
    """Context manager for timing agent operations."""
    collector = get_metrics_collector()
    with AgentTimer(collector, agent_id, operation) as timer:
        yield timer


def record_conversation_metrics(metrics: ConversationMetrics) -> None:
    """Record conversation completion metrics."""
    collector = get_metrics_collector()
    collector.record_conversation_completed(metrics)


def record_agent_health(agent_id: str, healthy: bool) -> None:
    """Record agent health status."""
    collector = get_metrics_collector()
    collector.record_agent_health(agent_id, healthy)


def record_policy_decision(
    policy_id: str,
    decision: str,
    agent_id: str,
    operation: str
) -> None:
    """Record policy evaluation decision."""
    collector = get_metrics_collector()
    collector.record_policy_evaluation(policy_id, decision, agent_id, operation)