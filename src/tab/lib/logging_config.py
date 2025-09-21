"""
Structured logging configuration with audit trail support for TAB.

Provides JSON-formatted logging with OpenTelemetry correlation and
comprehensive audit logging for security and compliance.
"""

import json
import logging
import logging.config
import sys
import hmac
import hashlib
import base64
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


# T031: Security audit logging with cryptographic integrity
class CryptographicAuditLogger(AuditLogger):
    """Audit logger with cryptographic integrity protection for security events."""

    def __init__(self, logger_name: str = "tab.secure_audit", signing_key: Optional[str] = None):
        super().__init__(logger_name)
        self.signing_key = signing_key or self._generate_signing_key()
        self.sequence_number = 0
        self.previous_hash = None

    def _generate_signing_key(self) -> str:
        """Generate a random signing key for audit log integrity."""
        import os
        return base64.b64encode(os.urandom(32)).decode('utf-8')

    def _calculate_signature(self, log_data: Dict[str, Any]) -> str:
        """Calculate HMAC signature for log entry."""
        log_string = json.dumps(log_data, sort_keys=True, separators=(',', ':'))
        return hmac.new(
            self.signing_key.encode('utf-8'),
            log_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _calculate_hash(self, log_data: Dict[str, Any]) -> str:
        """Calculate SHA256 hash of log entry for chain integrity."""
        log_string = json.dumps(log_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(log_string.encode('utf-8')).hexdigest()

    def _create_secure_log_entry(self, event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a cryptographically secured log entry."""
        self.sequence_number += 1

        base_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "sequence_number": self.sequence_number,
            "event_type": event_type,
            "previous_hash": self.previous_hash,
            **event_data
        }

        # Calculate hash and signature
        entry_hash = self._calculate_hash(base_entry)
        signature = self._calculate_signature(base_entry)

        # Add integrity fields
        secure_entry = {
            **base_entry,
            "entry_hash": entry_hash,
            "signature": signature,
            "integrity_version": "v1"
        }

        # Update previous hash for next entry
        self.previous_hash = entry_hash

        return secure_entry

    def log_security_event_secure(
        self,
        event_type: str,
        severity: str,
        description: str,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        policy_id: Optional[str] = None,
        threat_indicators: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a security event with cryptographic integrity protection."""
        event_data = {
            "audit_type": "security_secure",
            "severity": severity,
            "description": description,
            "agent_id": agent_id,
            "session_id": session_id,
            "policy_id": policy_id,
            "threat_indicators": threat_indicators or [],
            "metadata": metadata or {}
        }

        secure_entry = self._create_secure_log_entry(event_type, event_data)

        # Log with critical level for security events
        self.logger.critical(
            f"SECURE AUDIT: {event_type} - {description}",
            extra={
                "secure_audit_entry": secure_entry,
                **secure_entry
            }
        )

    def log_policy_violation_secure(
        self,
        policy_id: str,
        violation_type: str,
        agent_id: str,
        action_attempted: str,
        enforcement_result: str,
        session_id: Optional[str] = None,
        risk_score: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a policy violation with cryptographic integrity."""
        event_data = {
            "audit_type": "policy_violation_secure",
            "policy_id": policy_id,
            "violation_type": violation_type,
            "agent_id": agent_id,
            "action_attempted": action_attempted,
            "enforcement_result": enforcement_result,
            "session_id": session_id,
            "risk_score": risk_score,
            "metadata": metadata or {}
        }

        secure_entry = self._create_secure_log_entry("policy_violation", event_data)

        self.logger.error(
            f"POLICY VIOLATION: {violation_type} by {agent_id}",
            extra={
                "secure_audit_entry": secure_entry,
                **secure_entry
            }
        )

    def log_authentication_event_secure(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        success: bool = True,
        failure_reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log authentication events with integrity protection."""
        event_data = {
            "audit_type": "authentication_secure",
            "user_id": user_id,
            "agent_id": agent_id,
            "source_ip": source_ip,
            "success": success,
            "failure_reason": failure_reason,
            "metadata": metadata or {}
        }

        secure_entry = self._create_secure_log_entry(event_type, event_data)

        log_level = "info" if success else "warning"
        getattr(self.logger, log_level)(
            f"AUTH EVENT: {event_type} - {'SUCCESS' if success else 'FAILURE'}",
            extra={
                "secure_audit_entry": secure_entry,
                **secure_entry
            }
        )

    def verify_log_integrity(self, log_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Verify the cryptographic integrity of a sequence of log entries."""
        verification_result = {
            "total_entries": len(log_entries),
            "verified_entries": 0,
            "failed_entries": 0,
            "chain_integrity": True,
            "signature_failures": [],
            "chain_breaks": []
        }

        previous_hash = None

        for i, entry in enumerate(log_entries):
            # Verify signature
            if "signature" in entry and "integrity_version" in entry:
                entry_copy = {k: v for k, v in entry.items() if k not in ["signature", "entry_hash"]}
                expected_signature = self._calculate_signature(entry_copy)

                if entry["signature"] == expected_signature:
                    verification_result["verified_entries"] += 1
                else:
                    verification_result["failed_entries"] += 1
                    verification_result["signature_failures"].append({
                        "entry_index": i,
                        "sequence_number": entry.get("sequence_number"),
                        "timestamp": entry.get("timestamp")
                    })

            # Verify chain integrity
            if previous_hash is not None and entry.get("previous_hash") != previous_hash:
                verification_result["chain_integrity"] = False
                verification_result["chain_breaks"].append({
                    "entry_index": i,
                    "expected_previous_hash": previous_hash,
                    "actual_previous_hash": entry.get("previous_hash")
                })

            previous_hash = entry.get("entry_hash")

        return verification_result


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