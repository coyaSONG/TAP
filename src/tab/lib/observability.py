"""
OpenTelemetry configuration with OTLP exporters for TAB system.

Provides comprehensive observability with traces, metrics, and logs for
conversation orchestration and agent interactions.
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor


logger = logging.getLogger(__name__)


class ObservabilityConfig:
    """Configuration for OpenTelemetry setup."""

    def __init__(self, config: Dict[str, Any]):
        self.service_name = config.get("service_name", "tab-orchestrator")
        self.service_version = config.get("service_version", "1.0.0")
        self.environment = config.get("environment", "development")

        # OTLP endpoints
        self.otlp_endpoint = config.get("otlp_endpoint", os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"))
        self.metrics_endpoint = config.get("metrics_endpoint", self.otlp_endpoint)
        self.traces_endpoint = config.get("traces_endpoint", self.otlp_endpoint)

        # Export settings
        self.export_timeout = config.get("export_timeout", 30)
        self.batch_export_timeout = config.get("batch_export_timeout", 30)
        self.max_export_batch_size = config.get("max_export_batch_size", 512)

        # Sampling
        self.trace_sampling_ratio = config.get("trace_sampling_ratio", 1.0)

        # Additional attributes
        self.resource_attributes = config.get("resource_attributes", {})


class TelemetryManager:
    """Manages OpenTelemetry setup and lifecycle for TAB."""

    def __init__(self, config: ObservabilityConfig):
        self.config = config
        self._initialized = False
        self._tracer: Optional[trace.Tracer] = None
        self._meter: Optional[metrics.Meter] = None

    def initialize(self) -> None:
        """Initialize OpenTelemetry with OTLP exporters."""
        if self._initialized:
            logger.warning("Telemetry already initialized")
            return

        try:
            self._setup_resource()
            self._setup_tracing()
            self._setup_metrics()
            self._setup_instrumentation()

            self._initialized = True
            logger.info(f"OpenTelemetry initialized for service: {self.config.service_name}")

        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry: {e}")
            raise

    def _setup_resource(self) -> None:
        """Setup resource attributes for all telemetry."""
        resource_attrs = {
            "service.name": self.config.service_name,
            "service.version": self.config.service_version,
            "deployment.environment": self.config.environment,
            **self.config.resource_attributes
        }

        self._resource = Resource.create(resource_attrs)

    def _setup_tracing(self) -> None:
        """Setup distributed tracing with OTLP export."""
        # Create trace exporter
        trace_exporter = OTLPSpanExporter(
            endpoint=self.config.traces_endpoint,
            timeout=self.config.export_timeout
        )

        # Create span processor
        span_processor = BatchSpanProcessor(
            trace_exporter,
            max_export_batch_size=self.config.max_export_batch_size,
            export_timeout_millis=self.config.batch_export_timeout * 1000
        )

        # Setup tracer provider
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBasedSampler
        tracer_provider = TracerProvider(
            resource=self._resource,
            sampler=TraceIdRatioBasedSampler(self.config.trace_sampling_ratio)
        )
        tracer_provider.add_span_processor(span_processor)

        # Set global tracer provider
        trace.set_tracer_provider(tracer_provider)
        self._tracer = trace.get_tracer(__name__)

    def _setup_metrics(self) -> None:
        """Setup metrics collection with OTLP export."""
        # Create metrics exporter
        metric_exporter = OTLPMetricExporter(
            endpoint=self.config.metrics_endpoint,
            timeout=self.config.export_timeout
        )

        # Create metrics reader
        metric_reader = PeriodicExportingMetricReader(
            exporter=metric_exporter,
            export_interval_millis=10000  # 10 seconds
        )

        # Setup meter provider
        meter_provider = MeterProvider(
            resource=self._resource,
            metric_readers=[metric_reader]
        )

        # Set global meter provider
        metrics.set_meter_provider(meter_provider)
        self._meter = metrics.get_meter(__name__)

    def _setup_instrumentation(self) -> None:
        """Setup automatic instrumentation for common libraries."""
        # Instrument asyncio for async operation tracing
        AsyncioInstrumentor().instrument()

        # Instrument logging for log correlation
        LoggingInstrumentor().instrument(set_logging_format=True)

        logger.info("Automatic instrumentation configured")

    def get_tracer(self) -> trace.Tracer:
        """Get the configured tracer instance."""
        if not self._initialized:
            raise RuntimeError("Telemetry not initialized")
        return self._tracer

    def get_meter(self) -> metrics.Meter:
        """Get the configured meter instance."""
        if not self._initialized:
            raise RuntimeError("Telemetry not initialized")
        return self._meter

    def shutdown(self) -> None:
        """Gracefully shutdown telemetry and flush pending data."""
        if not self._initialized:
            return

        try:
            # Shutdown tracer provider
            if hasattr(trace.get_tracer_provider(), 'shutdown'):
                trace.get_tracer_provider().shutdown()

            # Shutdown meter provider
            if hasattr(metrics.get_meter_provider(), 'shutdown'):
                metrics.get_meter_provider().shutdown()

            logger.info("OpenTelemetry shutdown completed")

        except Exception as e:
            logger.error(f"Error during telemetry shutdown: {e}")
        finally:
            self._initialized = False


# Global telemetry manager instance
_telemetry_manager: Optional[TelemetryManager] = None


def initialize_telemetry(config: Dict[str, Any]) -> TelemetryManager:
    """Initialize global telemetry manager."""
    global _telemetry_manager

    observability_config = ObservabilityConfig(config)
    _telemetry_manager = TelemetryManager(observability_config)
    _telemetry_manager.initialize()

    return _telemetry_manager


def get_tracer() -> trace.Tracer:
    """Get the global tracer instance."""
    if _telemetry_manager is None:
        raise RuntimeError("Telemetry not initialized. Call initialize_telemetry() first.")
    return _telemetry_manager.get_tracer()


def get_meter() -> metrics.Meter:
    """Get the global meter instance."""
    if _telemetry_manager is None:
        raise RuntimeError("Telemetry not initialized. Call initialize_telemetry() first.")
    return _telemetry_manager.get_meter()


def shutdown_telemetry() -> None:
    """Shutdown global telemetry manager."""
    global _telemetry_manager
    if _telemetry_manager:
        _telemetry_manager.shutdown()
        _telemetry_manager = None


def create_conversation_span(session_id: str, operation: str) -> trace.Span:
    """Create a span for conversation operations."""
    tracer = get_tracer()
    span = tracer.start_span(
        name=f"conversation.{operation}",
        attributes={
            "conversation.session_id": session_id,
            "conversation.operation": operation
        }
    )
    return span


def create_agent_span(agent_id: str, operation: str, session_id: Optional[str] = None) -> trace.Span:
    """Create a span for agent operations."""
    tracer = get_tracer()
    attributes = {
        "agent.id": agent_id,
        "agent.operation": operation
    }

    if session_id:
        attributes["conversation.session_id"] = session_id

    span = tracer.start_span(
        name=f"agent.{operation}",
        attributes=attributes
    )
    return span


# T030: Enhanced conversation-specific spans and metrics
class ConversationMetrics:
    """Metrics collector for conversation-level observability."""

    def __init__(self):
        self.meter = get_meter()

        # Conversation metrics
        self.conversation_duration = self.meter.create_histogram(
            name="tab_conversation_duration_seconds",
            description="Duration of conversation sessions",
            unit="s"
        )

        self.conversation_turns = self.meter.create_histogram(
            name="tab_conversation_turns_total",
            description="Number of turns in conversation sessions",
            unit="1"
        )

        self.conversation_cost = self.meter.create_histogram(
            name="tab_conversation_cost_usd",
            description="Cost of conversation sessions in USD",
            unit="usd"
        )

        # Agent interaction metrics
        self.agent_response_time = self.meter.create_histogram(
            name="tab_agent_response_time_seconds",
            description="Response time for agent calls",
            unit="s"
        )

        self.agent_success_rate = self.meter.create_counter(
            name="tab_agent_calls_total",
            description="Total agent calls with success/failure status",
            unit="1"
        )

        # Policy enforcement metrics
        self.policy_violations = self.meter.create_counter(
            name="tab_policy_violations_total",
            description="Total policy violations by type",
            unit="1"
        )

        self.approval_requests = self.meter.create_counter(
            name="tab_approval_requests_total",
            description="Total approval requests by result",
            unit="1"
        )

    def record_conversation_completed(self, session_id: str, duration_seconds: float,
                                    turn_count: int, total_cost: float,
                                    policy_id: str, success: bool):
        """Record metrics for completed conversation."""
        labels = {
            "session_id": session_id,
            "policy_id": policy_id,
            "success": str(success).lower()
        }

        self.conversation_duration.record(duration_seconds, labels)
        self.conversation_turns.record(turn_count, labels)
        self.conversation_cost.record(total_cost, labels)

    def record_agent_call(self, agent_id: str, operation: str, duration_seconds: float,
                         success: bool, session_id: Optional[str] = None):
        """Record metrics for agent calls."""
        labels = {
            "agent_id": agent_id,
            "operation": operation,
            "success": str(success).lower()
        }

        if session_id:
            labels["session_id"] = session_id

        self.agent_response_time.record(duration_seconds, labels)
        self.agent_success_rate.add(1, labels)

    def record_policy_violation(self, policy_id: str, violation_type: str,
                               agent_id: str, session_id: Optional[str] = None):
        """Record policy violation metrics."""
        labels = {
            "policy_id": policy_id,
            "violation_type": violation_type,
            "agent_id": agent_id
        }

        if session_id:
            labels["session_id"] = session_id

        self.policy_violations.add(1, labels)

    def record_approval_request(self, action: str, result: str,
                               session_id: Optional[str] = None):
        """Record approval request metrics."""
        labels = {
            "action": action,
            "result": result  # approved, denied, timeout
        }

        if session_id:
            labels["session_id"] = session_id

        self.approval_requests.add(1, labels)


# Global metrics collector instance
_conversation_metrics: Optional[ConversationMetrics] = None


def get_conversation_metrics() -> ConversationMetrics:
    """Get global conversation metrics collector."""
    global _conversation_metrics
    if _conversation_metrics is None:
        _conversation_metrics = ConversationMetrics()
    return _conversation_metrics


def create_turn_span(session_id: str, turn_number: int, from_agent: str,
                    to_agent: str) -> trace.Span:
    """Create a span for a conversation turn with detailed attributes."""
    tracer = get_tracer()
    span = tracer.start_span(
        name="conversation.turn",
        attributes={
            "conversation.session_id": session_id,
            "conversation.turn_number": turn_number,
            "conversation.from_agent": from_agent,
            "conversation.to_agent": to_agent,
            "conversation.direction": f"{from_agent}->{to_agent}"
        }
    )
    return span


def create_policy_enforcement_span(policy_id: str, operation: str,
                                  session_id: Optional[str] = None) -> trace.Span:
    """Create a span for policy enforcement operations."""
    tracer = get_tracer()
    attributes = {
        "policy.id": policy_id,
        "policy.operation": operation
    }

    if session_id:
        attributes["conversation.session_id"] = session_id

    span = tracer.start_span(
        name=f"policy.{operation}",
        attributes=attributes
    )
    return span


def create_approval_span(action: str, session_id: Optional[str] = None) -> trace.Span:
    """Create a span for approval workflow operations."""
    tracer = get_tracer()
    attributes = {
        "approval.action": action
    }

    if session_id:
        attributes["conversation.session_id"] = session_id

    span = tracer.start_span(
        name="approval.request",
        attributes=attributes
    )
    return span


def instrument_conversation_flow(session_id: str, topic: str,
                                policy_id: str) -> trace.Span:
    """Create a root span for the entire conversation flow."""
    tracer = get_tracer()
    span = tracer.start_span(
        name="conversation.flow",
        attributes={
            "conversation.session_id": session_id,
            "conversation.topic": topic,
            "conversation.policy_id": policy_id,
            "conversation.timestamp": str(datetime.now())
        }
    )
    return span