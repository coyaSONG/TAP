"""
OpenTelemetry configuration with OTLP exporters for TAB system.

Provides comprehensive observability with traces, metrics, and logs for
conversation orchestration and agent interactions.
"""

import logging
import os
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
        tracer_provider = TracerProvider(
            resource=self._resource,
            sampler=trace.TraceIdRatioBasedSampler(self.config.trace_sampling_ratio)
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