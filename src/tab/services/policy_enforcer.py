"""Policy enforcement service with security validation."""

import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone

from tab.models.policy_configuration import PolicyConfiguration, PermissionMode, ResourceLimits
from tab.models.audit_record import AuditRecord, EventType
from tab.models.turn_message import TurnMessage


logger = logging.getLogger(__name__)


class PolicyEnforcer:
    """Service for enforcing security policies and permission controls."""

    def __init__(self):
        """Initialize the policy enforcer."""
        self.logger = logging.getLogger(__name__)
        self._policies: Dict[str, PolicyConfiguration] = {}
        self._audit_records: List[AuditRecord] = []
        self._load_default_policies()

    def _load_default_policies(self) -> None:
        """Load default policy configurations."""
        # Default development policy
        default_policy = PolicyConfiguration(
            policy_id="default",
            name="Default Development Policy",
            description="Standard policy for development environments",
            allowed_tools=["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
            disallowed_tools=[],
            permission_mode=PermissionMode.PROMPT,
            resource_limits=ResourceLimits(
                max_execution_time_seconds=120,
                max_cost_usd=1.0,
                max_memory_mb=512,
                max_file_size_mb=10
            ),
            file_access_rules={
                "allowed_paths": ["/workspace", "/tmp"],
                "readonly_paths": ["/usr", "/etc", "/bin"],
                "forbidden_paths": ["/proc", "/sys", "/dev"]
            },
            network_access_rules={
                "allowed": False,
                "allowed_hosts": [],
                "allowed_ports": []
            }
        )

        # Read-only strict policy
        readonly_policy = PolicyConfiguration(
            policy_id="read_only_strict",
            name="Read-Only Strict Policy",
            description="Strict read-only access with minimal permissions",
            allowed_tools=["Read", "Grep", "Glob"],
            disallowed_tools=["Write", "Edit", "Bash", "MultiEdit"],
            permission_mode=PermissionMode.DENY,
            resource_limits=ResourceLimits(
                max_execution_time_seconds=60,
                max_cost_usd=0.1,
                max_memory_mb=256,
                max_file_size_mb=5
            ),
            file_access_rules={
                "allowed_paths": ["/workspace"],
                "readonly_paths": ["/workspace", "/usr", "/etc"],
                "forbidden_paths": ["/proc", "/sys", "/dev", "/tmp"]
            },
            network_access_rules={
                "allowed": False,
                "allowed_hosts": [],
                "allowed_ports": []
            }
        )

        # Development safe policy
        dev_safe_policy = PolicyConfiguration(
            policy_id="development_safe",
            name="Development Safe Policy",
            description="Safe development policy with controlled access",
            allowed_tools=["Read", "Write", "Edit", "Grep", "Glob", "MultiEdit"],
            disallowed_tools=["Bash"],
            permission_mode=PermissionMode.AUTO,
            resource_limits=ResourceLimits(
                max_execution_time_seconds=180,
                max_cost_usd=0.5,
                max_memory_mb=1024,
                max_file_size_mb=20
            ),
            file_access_rules={
                "allowed_paths": ["/workspace", "/tmp"],
                "readonly_paths": ["/usr", "/etc"],
                "forbidden_paths": ["/proc", "/sys", "/dev"]
            },
            network_access_rules={
                "allowed": True,
                "allowed_hosts": ["api.example.com", "docs.example.com"],
                "allowed_ports": [80, 443]
            }
        )

        self._policies = {
            "default": default_policy,
            "read_only_strict": readonly_policy,
            "development_safe": dev_safe_policy
        }

    def get_policy(self, policy_id: str) -> Optional[PolicyConfiguration]:
        """Get policy configuration by ID.

        Args:
            policy_id: Policy identifier

        Returns:
            PolicyConfiguration if found, None otherwise
        """
        return self._policies.get(policy_id)

    def validate_tool_usage(
        self,
        policy_id: str,
        tool_name: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate if tool usage is allowed by policy.

        Args:
            policy_id: Policy to enforce
            tool_name: Tool being used
            session_id: Optional session identifier

        Returns:
            Validation result with allowed status and details
        """
        policy = self.get_policy(policy_id)
        if not policy:
            self._create_audit_record(
                session_id, EventType.SECURITY, "policy_not_found",
                "failed", {"policy_id": policy_id, "tool_name": tool_name}
            )
            return {
                "allowed": False,
                "reason": f"Policy {policy_id} not found",
                "action_required": "block"
            }

        # Check if tool is explicitly disallowed
        if tool_name in policy.disallowed_tools:
            self._create_audit_record(
                session_id, EventType.SECURITY, "tool_disallowed",
                "blocked", {"policy_id": policy_id, "tool_name": tool_name}
            )
            return {
                "allowed": False,
                "reason": f"Tool {tool_name} is explicitly disallowed",
                "action_required": "block"
            }

        # Check if tool is in allowed list (if list exists)
        if policy.allowed_tools and tool_name not in policy.allowed_tools:
            self._create_audit_record(
                session_id, EventType.SECURITY, "tool_not_allowed",
                "blocked", {"policy_id": policy_id, "tool_name": tool_name}
            )
            return {
                "allowed": False,
                "reason": f"Tool {tool_name} is not in allowed tools list",
                "action_required": "block"
            }

        # Tool is allowed
        self._create_audit_record(
            session_id, EventType.ACTION, "tool_allowed",
            "success", {"policy_id": policy_id, "tool_name": tool_name}
        )

        return {
            "allowed": True,
            "reason": "Tool usage permitted by policy",
            "action_required": "none"
        }

    def validate_file_access(
        self,
        policy_id: str,
        file_path: str,
        access_type: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate file access against policy rules.

        Args:
            policy_id: Policy to enforce
            file_path: File path being accessed
            access_type: Type of access (read, write, execute)
            session_id: Optional session identifier

        Returns:
            Validation result with allowed status and details
        """
        policy = self.get_policy(policy_id)
        if not policy:
            return {
                "allowed": False,
                "reason": f"Policy {policy_id} not found",
                "action_required": "block"
            }

        file_rules = policy.file_access_rules

        # Check forbidden paths first
        forbidden_paths = file_rules.get("forbidden_paths", [])
        for forbidden_path in forbidden_paths:
            if file_path.startswith(forbidden_path):
                self._create_audit_record(
                    session_id, EventType.SECURITY, "file_access_forbidden",
                    "blocked", {
                        "policy_id": policy_id,
                        "file_path": file_path,
                        "access_type": access_type,
                        "forbidden_path": forbidden_path
                    }
                )
                return {
                    "allowed": False,
                    "reason": f"File path {file_path} is in forbidden area {forbidden_path}",
                    "action_required": "block"
                }

        # Check if write access to read-only paths
        if access_type in ["write", "execute"]:
            readonly_paths = file_rules.get("readonly_paths", [])
            for readonly_path in readonly_paths:
                if file_path.startswith(readonly_path):
                    self._create_audit_record(
                        session_id, EventType.SECURITY, "file_access_readonly_violation",
                        "blocked", {
                            "policy_id": policy_id,
                            "file_path": file_path,
                            "access_type": access_type,
                            "readonly_path": readonly_path
                        }
                    )
                    return {
                        "allowed": False,
                        "reason": f"Write/execute access denied to read-only path {readonly_path}",
                        "action_required": "block"
                    }

        # Check allowed paths
        allowed_paths = file_rules.get("allowed_paths", [])
        if allowed_paths:
            path_allowed = False
            for allowed_path in allowed_paths:
                if file_path.startswith(allowed_path):
                    path_allowed = True
                    break

            if not path_allowed:
                self._create_audit_record(
                    session_id, EventType.SECURITY, "file_access_not_allowed",
                    "blocked", {
                        "policy_id": policy_id,
                        "file_path": file_path,
                        "access_type": access_type,
                        "allowed_paths": allowed_paths
                    }
                )
                return {
                    "allowed": False,
                    "reason": f"File path {file_path} is not in allowed paths",
                    "action_required": "block"
                }

        # File access is allowed
        self._create_audit_record(
            session_id, EventType.ACTION, "file_access_allowed",
            "success", {
                "policy_id": policy_id,
                "file_path": file_path,
                "access_type": access_type
            }
        )

        return {
            "allowed": True,
            "reason": "File access permitted by policy",
            "action_required": "none"
        }

    def validate_resource_limits(
        self,
        policy_id: str,
        resource_usage: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate resource usage against policy limits.

        Args:
            policy_id: Policy to enforce
            resource_usage: Current resource usage metrics
            session_id: Optional session identifier

        Returns:
            Validation result with allowed status and details
        """
        policy = self.get_policy(policy_id)
        if not policy:
            return {
                "allowed": False,
                "reason": f"Policy {policy_id} not found",
                "action_required": "block"
            }

        limits = policy.resource_limits
        violations = []

        # Check execution time
        execution_time = resource_usage.get("execution_time_seconds", 0)
        if execution_time > limits.max_execution_time_seconds:
            violations.append(f"Execution time {execution_time}s exceeds limit {limits.max_execution_time_seconds}s")

        # Check cost
        cost_usd = resource_usage.get("cost_usd", 0.0)
        if cost_usd > limits.max_cost_usd:
            violations.append(f"Cost ${cost_usd} exceeds limit ${limits.max_cost_usd}")

        # Check memory
        memory_mb = resource_usage.get("memory_mb", 0)
        if memory_mb > limits.max_memory_mb:
            violations.append(f"Memory {memory_mb}MB exceeds limit {limits.max_memory_mb}MB")

        # Check file size
        file_size_mb = resource_usage.get("file_size_mb", 0)
        if file_size_mb > limits.max_file_size_mb:
            violations.append(f"File size {file_size_mb}MB exceeds limit {limits.max_file_size_mb}MB")

        if violations:
            self._create_audit_record(
                session_id, EventType.SECURITY, "resource_limit_violation",
                "blocked", {
                    "policy_id": policy_id,
                    "violations": violations,
                    "resource_usage": resource_usage
                }
            )
            return {
                "allowed": False,
                "reason": f"Resource limit violations: {'; '.join(violations)}",
                "action_required": "block",
                "violations": violations
            }

        return {
            "allowed": True,
            "reason": "Resource usage within policy limits",
            "action_required": "none"
        }

    def validate_network_access(
        self,
        policy_id: str,
        host: str,
        port: int,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate network access against policy rules.

        Args:
            policy_id: Policy to enforce
            host: Target host
            port: Target port
            session_id: Optional session identifier

        Returns:
            Validation result with allowed status and details
        """
        policy = self.get_policy(policy_id)
        if not policy:
            return {
                "allowed": False,
                "reason": f"Policy {policy_id} not found",
                "action_required": "block"
            }

        network_rules = policy.network_access_rules

        # Check if network access is allowed at all
        if not network_rules.get("allowed", False):
            self._create_audit_record(
                session_id, EventType.SECURITY, "network_access_disabled",
                "blocked", {
                    "policy_id": policy_id,
                    "host": host,
                    "port": port
                }
            )
            return {
                "allowed": False,
                "reason": "Network access is disabled by policy",
                "action_required": "block"
            }

        # Check allowed hosts
        allowed_hosts = network_rules.get("allowed_hosts", [])
        if allowed_hosts and host not in allowed_hosts:
            self._create_audit_record(
                session_id, EventType.SECURITY, "network_host_not_allowed",
                "blocked", {
                    "policy_id": policy_id,
                    "host": host,
                    "port": port,
                    "allowed_hosts": allowed_hosts
                }
            )
            return {
                "allowed": False,
                "reason": f"Host {host} is not in allowed hosts list",
                "action_required": "block"
            }

        # Check allowed ports
        allowed_ports = network_rules.get("allowed_ports", [])
        if allowed_ports and port not in allowed_ports:
            self._create_audit_record(
                session_id, EventType.SECURITY, "network_port_not_allowed",
                "blocked", {
                    "policy_id": policy_id,
                    "host": host,
                    "port": port,
                    "allowed_ports": allowed_ports
                }
            )
            return {
                "allowed": False,
                "reason": f"Port {port} is not in allowed ports list",
                "action_required": "block"
            }

        # Network access is allowed
        self._create_audit_record(
            session_id, EventType.ACTION, "network_access_allowed",
            "success", {
                "policy_id": policy_id,
                "host": host,
                "port": port
            }
        )

        return {
            "allowed": True,
            "reason": "Network access permitted by policy",
            "action_required": "none"
        }

    def enforce_turn_message_policy(
        self,
        policy_id: str,
        turn_message: TurnMessage
    ) -> Dict[str, Any]:
        """Enforce policy constraints on a turn message.

        Args:
            policy_id: Policy to enforce
            turn_message: Turn message to validate

        Returns:
            Enforcement result with any violations
        """
        policy = self.get_policy(policy_id)
        if not policy:
            return {
                "allowed": False,
                "violations": [f"Policy {policy_id} not found"],
                "action_required": "block"
            }

        violations = []

        # Check content length limits (basic validation)
        if len(turn_message.content) > 50000:  # Max content length
            violations.append("Message content exceeds maximum length")

        # Check attachment limits
        if len(turn_message.attachments) > 10:
            violations.append("Too many attachments")

        # Validate file attachments against policy
        for attachment in turn_message.attachments:
            file_path = attachment.get("path", "")
            if file_path:
                file_validation = self.validate_file_access(
                    policy_id, file_path, "read", turn_message.session_id
                )
                if not file_validation["allowed"]:
                    violations.append(f"Attachment access denied: {file_validation['reason']}")

        # Add policy constraints to turn message
        for violation in violations:
            turn_message.add_policy_constraint(
                "policy_violation",
                violation,
                enforced=False,
                violation_reason=violation
            )

        if violations:
            self._create_audit_record(
                turn_message.session_id, EventType.SECURITY, "turn_message_policy_violation",
                "blocked", {
                    "policy_id": policy_id,
                    "turn_id": turn_message.turn_id,
                    "violations": violations
                }
            )
            return {
                "allowed": False,
                "violations": violations,
                "action_required": "block"
            }

        return {
            "allowed": True,
            "violations": [],
            "action_required": "none"
        }

    def _create_audit_record(
        self,
        session_id: Optional[str],
        event_type: EventType,
        action: str,
        result: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Create an audit record for policy enforcement actions.

        Args:
            session_id: Session identifier
            event_type: Type of event
            action: Action performed
            result: Result of action
            metadata: Additional metadata
        """
        audit_record = AuditRecord(
            session_id=session_id,
            event_type=event_type,
            action=action,
            result=result,
            reason=f"Policy enforcement: {action}",
            metadata=metadata
        )
        self._audit_records.append(audit_record)

    def get_audit_records(
        self,
        session_id: Optional[str] = None,
        event_type: Optional[EventType] = None
    ) -> List[AuditRecord]:
        """Get audit records with optional filtering.

        Args:
            session_id: Filter by session ID
            event_type: Filter by event type

        Returns:
            List of matching audit records
        """
        records = self._audit_records

        if session_id:
            records = [r for r in records if r.session_id == session_id]

        if event_type:
            records = [r for r in records if r.event_type == event_type]

        return records

    def list_policies(self) -> Dict[str, Dict[str, Any]]:
        """List all available policies.

        Returns:
            Dictionary of policy summaries
        """
        return {
            policy_id: {
                "name": policy.name,
                "description": policy.description,
                "permission_mode": policy.permission_mode.value,
                "allowed_tools_count": len(policy.allowed_tools),
                "disallowed_tools_count": len(policy.disallowed_tools)
            }
            for policy_id, policy in self._policies.items()
        }