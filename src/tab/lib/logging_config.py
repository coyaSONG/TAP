"""
Structured logging configuration with audit trail support for TAB.

Provides JSON-formatted logging with OpenTelemetry correlation and
comprehensive audit logging for security and compliance.
"""

import json
import logging
import logging.config
import sys
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from opentelemetry import trace


class StructuredFormatter(logging.Formatter):
    """JSON formatter with OpenTelemetry trace correlation."""

    def __init__(self, include_trace: bool = True, extra_fields: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.include_trace = include_trace
        self.extra_fields = extra_fields or {}

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Add trace context if available
        if self.include_trace:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                span_context = current_span.get_span_context()
                log_entry.update({
                    "trace_id": format(span_context.trace_id, "032x"),
                    "span_id": format(span_context.span_id, "016x")
                })

        # Add exception information
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in {"name", "msg", "args", "levelname", "levelno", "pathname",
                          "filename", "module", "exc_info", "exc_text", "stack_info",
                          "lineno", "funcName", "created", "msecs", "relativeCreated",
                          "thread", "threadName", "processName", "process", "message"}:
                log_entry[key] = value

        # Add configured extra fields
        log_entry.update(self.extra_fields)

        return json.dumps(log_entry, ensure_ascii=False)


class AuditLogger:
    """Specialized logger for security and audit events."""

    def __init__(self, logger_name: str = "tab.audit"):
        self.logger = logging.getLogger(logger_name)

    def log_session_event(
        self,
        event_type: str,
        session_id: str,
        agent_id: Optional[str] = None,
        action: Optional[str] = None,
        result: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a session-related audit event."""
        self.logger.info(
            f"Session event: {event_type}",
            extra={
                "audit_type": "session",
                "event_type": event_type,
                "session_id": session_id,
                "agent_id": agent_id,
                "action": action,
                "result": result,
                "metadata": metadata or {}
            }
        )

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        policy_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a security-related audit event."""
        self.logger.warning(
            f"Security event: {event_type} - {description}",
            extra={
                "audit_type": "security",
                "event_type": event_type,
                "severity": severity,
                "description": description,
                "agent_id": agent_id,
                "session_id": session_id,
                "policy_id": policy_id,
                "metadata": metadata or {}
            }
        )

    def log_agent_event(
        self,
        event_type: str,
        agent_id: str,
        action: str,
        result: str,
        execution_time_ms: Optional[int] = None,
        cost_usd: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log an agent operation audit event."""
        self.logger.info(
            f"Agent event: {event_type} - {action}",
            extra={
                "audit_type": "agent",
                "event_type": event_type,
                "agent_id": agent_id,
                "action": action,
                "result": result,
                "execution_time_ms": execution_time_ms,
                "cost_usd": cost_usd,
                "metadata": metadata or {}
            }
        )

    def log_policy_event(
        self,
        event_type: str,
        policy_id: str,
        action: str,
        decision: str,
        reason: str,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a policy enforcement audit event."""
        self.logger.info(
            f"Policy event: {event_type} - {action}",
            extra={
                "audit_type": "policy",
                "event_type": event_type,
                "policy_id": policy_id,
                "action": action,
                "decision": decision,
                "reason": reason,
                "agent_id": agent_id,
                "session_id": session_id,
                "metadata": metadata or {}
            }
        )


def setup_logging(config: Dict[str, Any]) -> None:
    """Setup structured logging configuration."""
    log_level = config.get("level", "INFO").upper()
    log_format = config.get("format", "structured")

    # Create logs directory if it doesn't exist
    log_dir = Path(config.get("directory", "~/.tab/logs")).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)

    # Base logging configuration
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "()": StructuredFormatter,
                "include_trace": config.get("include_trace", True),
                "extra_fields": {
                    "service": "tab-orchestrator",
                    "environment": config.get("environment", "development")
                }
            },
            "simple": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "structured" if log_format == "structured" else "simple",
                "stream": sys.stdout
            },
            "application_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": log_level,
                "formatter": "structured",
                "filename": str(log_dir / "orchestrator.log"),
                "maxBytes": config.get("max_file_size", 10 * 1024 * 1024),  # 10MB
                "backupCount": config.get("backup_count", 5)
            },
            "audit_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "structured",
                "filename": str(log_dir / "audit.jsonl"),
                "maxBytes": config.get("max_file_size", 10 * 1024 * 1024),  # 10MB
                "backupCount": config.get("backup_count", 10)
            }
        },
        "loggers": {
            "tab": {
                "level": log_level,
                "handlers": ["console", "application_file"],
                "propagate": False
            },
            "tab.audit": {
                "level": "INFO",
                "handlers": ["audit_file"],
                "propagate": False
            },
            "tab.agents": {
                "level": log_level,
                "handlers": ["console", "application_file"],
                "propagate": False
            },
            "tab.services": {
                "level": log_level,
                "handlers": ["console", "application_file"],
                "propagate": False
            },
            "opentelemetry": {
                "level": "WARNING",
                "handlers": ["console", "application_file"],
                "propagate": False
            }
        },
        "root": {
            "level": log_level,
            "handlers": ["console"]
        }
    }

    # Apply the configuration
    logging.config.dictConfig(logging_config)

    # Test the configuration
    logger = logging.getLogger("tab.logging")
    logger.info("Structured logging initialized", extra={
        "config": {
            "level": log_level,
            "format": log_format,
            "directory": str(log_dir)
        }
    })


def get_audit_logger() -> AuditLogger:
    """Get the configured audit logger instance."""
    return AuditLogger()


def create_agent_file_handler(agent_id: str, log_dir: Path, max_size: int = 10 * 1024 * 1024) -> logging.Handler:
    """Create a dedicated file handler for agent logs."""
    agent_log_dir = log_dir / "agents"
    agent_log_dir.mkdir(exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        filename=str(agent_log_dir / f"{agent_id}.log"),
        maxBytes=max_size,
        backupCount=5
    )
    handler.setFormatter(StructuredFormatter(extra_fields={"agent_id": agent_id}))
    return handler


def setup_agent_logging(agent_id: str, log_dir: Optional[Path] = None) -> logging.Logger:
    """Setup dedicated logging for a specific agent."""
    if log_dir is None:
        log_dir = Path("~/.tab/logs").expanduser()

    logger = logging.getLogger(f"tab.agents.{agent_id}")

    # Add agent-specific file handler if not already present
    agent_handler_exists = any(
        isinstance(handler, logging.handlers.RotatingFileHandler) and
        agent_id in str(handler.baseFilename)
        for handler in logger.handlers
    )

    if not agent_handler_exists:
        agent_handler = create_agent_file_handler(agent_id, log_dir)
        logger.addHandler(agent_handler)

    return logger