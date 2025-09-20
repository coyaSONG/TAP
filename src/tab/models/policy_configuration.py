"""PolicyConfiguration model with permission rules."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class PermissionMode(str, Enum):
    """Permission approval mode enumeration."""

    AUTO = "auto"
    PROMPT = "prompt"
    DENY = "deny"


class IsolationLevel(str, Enum):
    """Sandbox isolation level enumeration."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAXIMUM = "maximum"


class ResourceLimits(BaseModel):
    """Resource constraints and limits."""

    max_execution_time_seconds: int = Field(default=120, ge=1, le=3600, description="Maximum execution time")
    max_cost_usd: float = Field(default=1.0, ge=0.001, le=100.0, description="Maximum cost budget")
    max_memory_mb: int = Field(default=512, ge=64, le=8192, description="Maximum memory usage")
    max_file_size_mb: int = Field(default=50, ge=1, le=1024, description="Maximum file size")
    max_files_accessed: int = Field(default=100, ge=1, le=10000, description="Maximum files accessed")
    max_network_requests: int = Field(default=0, ge=0, le=1000, description="Maximum network requests")


class FileAccessRules(BaseModel):
    """File system access permissions."""

    allowed_patterns: List[str] = Field(default_factory=list, description="Allowed file patterns (glob)")
    disallowed_patterns: List[str] = Field(default_factory=list, description="Disallowed file patterns (glob)")
    readonly_paths: List[str] = Field(default_factory=list, description="Read-only path restrictions")
    writable_paths: List[str] = Field(default_factory=list, description="Writable path allowlist")
    max_path_depth: int = Field(default=10, ge=1, le=50, description="Maximum directory depth")


class NetworkAccessRules(BaseModel):
    """Network access permissions."""

    enabled: bool = Field(default=False, description="Whether network access is enabled")
    allowed_hosts: List[str] = Field(default_factory=list, description="Allowed hostnames/IPs")
    allowed_ports: List[int] = Field(default_factory=list, description="Allowed port numbers")
    blocked_hosts: List[str] = Field(default_factory=list, description="Explicitly blocked hosts")
    require_approval: bool = Field(default=True, description="Require approval for network requests")


class SandboxConfig(BaseModel):
    """Sandboxing and isolation configuration."""

    enabled: bool = Field(default=True, description="Whether sandboxing is enabled")
    isolation_level: IsolationLevel = Field(default=IsolationLevel.MEDIUM, description="Isolation level")
    read_only_filesystem: bool = Field(default=False, description="Read-only filesystem")
    no_network: bool = Field(default=True, description="Disable network access")
    capabilities_dropped: List[str] = Field(default_factory=list, description="Dropped Linux capabilities")
    user_namespace: bool = Field(default=True, description="Use user namespace isolation")
    temp_directory_only: bool = Field(default=False, description="Restrict to temporary directory only")


class PolicyConfiguration(BaseModel):
    """
    Permission and constraint definitions governing agent behavior and resource access.

    Comprehensive security policy for agent operations with inheritance support.
    """

    policy_id: str = Field(..., description="Unique identifier for the policy")
    name: str = Field(..., description="Human-readable policy name")
    description: str = Field(..., description="Policy purpose and scope")
    version: str = Field(default="1.0.0", description="Policy version")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Policy creation timestamp")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Policy last update timestamp")

    # Core permission settings
    permission_mode: PermissionMode = Field(default=PermissionMode.PROMPT, description="Permission approval mode")
    allowed_tools: List[str] = Field(default_factory=list, description="List of tools/operations permitted")
    disallowed_tools: List[str] = Field(default_factory=list, description="List of explicitly forbidden tools")
    approval_required: List[str] = Field(default_factory=list, description="Operations requiring explicit approval")

    # Resource and access controls
    resource_limits: ResourceLimits = Field(default_factory=ResourceLimits, description="Resource constraints")
    file_access_rules: FileAccessRules = Field(default_factory=FileAccessRules, description="File system access permissions")
    network_access_rules: NetworkAccessRules = Field(default_factory=NetworkAccessRules, description="Network access permissions")
    sandbox_config: SandboxConfig = Field(default_factory=SandboxConfig, description="Sandboxing configuration")

    # Policy inheritance
    inherits_from: Optional[str] = Field(None, description="Parent policy ID for inheritance")
    priority: int = Field(default=100, ge=1, le=1000, description="Policy priority (lower = higher priority)")

    # Audit and compliance
    audit_level: str = Field(default="standard", description="Audit logging level")
    compliance_tags: List[str] = Field(default_factory=list, description="Compliance requirement tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional policy metadata")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @validator('policy_id')
    def validate_policy_id(cls, v):
        """Validate policy ID is unique and follows naming convention."""
        if not v.strip():
            raise ValueError("policy_id cannot be empty")

        # Check naming convention (alphanumeric, underscore, hyphen)
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("policy_id must contain only alphanumeric characters, underscores, and hyphens")

        return v.strip()

    @validator('name')
    def validate_name(cls, v):
        """Validate policy name."""
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()

    @validator('allowed_tools', 'disallowed_tools')
    def validate_tool_lists(cls, v, values, field):
        """Validate tool lists don't overlap."""
        if field.name == 'disallowed_tools' and 'allowed_tools' in values:
            allowed = set(values['allowed_tools'])
            disallowed = set(v)
            overlap = allowed.intersection(disallowed)
            if overlap:
                raise ValueError(f"Tools cannot be both allowed and disallowed: {overlap}")

        return v

    @validator('updated_at', always=True)
    def validate_updated_at(cls, v, values):
        """Ensure updated_at is not before created_at."""
        if 'created_at' in values and v < values['created_at']:
            raise ValueError("updated_at cannot be before created_at")
        return v

    def is_tool_allowed(self, tool_name: str) -> bool:
        """
        Check if a tool is allowed by this policy.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if tool is allowed, False otherwise
        """
        # Explicit deny takes precedence
        if tool_name in self.disallowed_tools:
            return False

        # If there's an allow list, tool must be in it
        if self.allowed_tools:
            return tool_name in self.allowed_tools

        # If no allow list, tool is allowed unless explicitly denied
        return True

    def requires_approval(self, operation: str) -> bool:
        """
        Check if an operation requires explicit approval.

        Args:
            operation: Operation name to check

        Returns:
            True if approval is required
        """
        if self.permission_mode == PermissionMode.DENY:
            return True

        if self.permission_mode == PermissionMode.AUTO:
            # Only require approval for explicitly listed operations
            return operation in self.approval_required

        # PROMPT mode - check approval list
        return operation in self.approval_required

    def validate_file_access(self, file_path: str, operation: str = "read") -> bool:
        """
        Validate if file access is allowed.

        Args:
            file_path: Path to the file
            operation: Type of operation (read, write, delete)

        Returns:
            True if access is allowed
        """
        import fnmatch

        # Check against disallowed patterns first
        for pattern in self.file_access_rules.disallowed_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return False

        # Check against allowed patterns
        if self.file_access_rules.allowed_patterns:
            allowed = any(
                fnmatch.fnmatch(file_path, pattern)
                for pattern in self.file_access_rules.allowed_patterns
            )
            if not allowed:
                return False

        # Check write operation constraints
        if operation in ["write", "delete", "modify"]:
            # If read-only filesystem, deny writes
            if self.sandbox_config.read_only_filesystem:
                return False

            # Check writable paths
            if self.file_access_rules.writable_paths:
                writable = any(
                    file_path.startswith(path)
                    for path in self.file_access_rules.writable_paths
                )
                if not writable:
                    return False

        return True

    def validate_network_access(self, host: str, port: int = 80) -> bool:
        """
        Validate if network access is allowed.

        Args:
            host: Target hostname or IP
            port: Target port number

        Returns:
            True if access is allowed
        """
        if not self.network_access_rules.enabled:
            return False

        # Check blocked hosts
        if host in self.network_access_rules.blocked_hosts:
            return False

        # Check allowed hosts
        if self.network_access_rules.allowed_hosts:
            if host not in self.network_access_rules.allowed_hosts:
                return False

        # Check allowed ports
        if self.network_access_rules.allowed_ports:
            if port not in self.network_access_rules.allowed_ports:
                return False

        return True

    def merge_with_parent(self, parent_policy: 'PolicyConfiguration') -> 'PolicyConfiguration':
        """
        Merge this policy with its parent policy.

        Args:
            parent_policy: Parent policy to inherit from

        Returns:
            New merged policy configuration
        """
        # Create a new policy based on parent
        merged_data = parent_policy.dict()

        # Override with current policy settings
        current_data = self.dict(exclude={'inherits_from', 'created_at', 'updated_at'})

        # Merge lists (union for allowed, intersection for disallowed)
        merged_data['allowed_tools'] = list(set(parent_policy.allowed_tools + self.allowed_tools))
        merged_data['disallowed_tools'] = list(set(parent_policy.disallowed_tools + self.disallowed_tools))
        merged_data['approval_required'] = list(set(parent_policy.approval_required + self.approval_required))

        # Update other fields with current policy values
        for key, value in current_data.items():
            if key not in ['allowed_tools', 'disallowed_tools', 'approval_required']:
                if value is not None:  # Don't override with None values
                    merged_data[key] = value

        # Preserve original timestamps and inheritance
        merged_data['inherits_from'] = self.inherits_from
        merged_data['created_at'] = self.created_at
        merged_data['updated_at'] = self.updated_at

        return PolicyConfiguration(**merged_data)

    def get_effective_limits(self) -> ResourceLimits:
        """Get effective resource limits for this policy."""
        return self.resource_limits

    def to_enforcement_config(self) -> Dict[str, Any]:
        """Generate configuration for policy enforcement engine."""
        return {
            "policy_id": self.policy_id,
            "permission_mode": self.permission_mode,
            "tools": {
                "allowed": self.allowed_tools,
                "disallowed": self.disallowed_tools,
                "approval_required": self.approval_required
            },
            "resources": self.resource_limits.dict(),
            "file_access": self.file_access_rules.dict(),
            "network_access": self.network_access_rules.dict(),
            "sandbox": self.sandbox_config.dict(),
            "audit_level": self.audit_level
        }

    def to_summary(self) -> Dict[str, Any]:
        """Generate a summary of the policy for reporting."""
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "version": self.version,
            "permission_mode": self.permission_mode,
            "tools_allowed_count": len(self.allowed_tools),
            "tools_disallowed_count": len(self.disallowed_tools),
            "approval_required_count": len(self.approval_required),
            "sandbox_enabled": self.sandbox_config.enabled,
            "network_enabled": self.network_access_rules.enabled,
            "isolation_level": self.sandbox_config.isolation_level,
            "inherits_from": self.inherits_from,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }