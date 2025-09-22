"""
Configuration management and validation for TAB system.

Provides comprehensive configuration loading, validation, and management
for the Twin-Agent Bridge orchestrator and all components.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, validator, ValidationError


class ObservabilityConfig(BaseModel):
    """Configuration for observability settings."""
    service_name: str = "tab-orchestrator"
    service_version: str = "1.0.0"
    environment: str = "development"
    otlp_endpoint: str = "http://localhost:4317"
    trace_sampling_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    export_timeout: int = Field(default=30, gt=0)
    resource_attributes: Dict[str, str] = field(default_factory=dict)


class LoggingConfig(BaseModel):
    """Configuration for logging settings."""
    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format: str = Field(default="structured", pattern="^(structured|simple)$")
    directory: str = "~/.tab/logs"
    max_file_size: int = Field(default=10 * 1024 * 1024, gt=0)  # 10MB
    backup_count: int = Field(default=5, ge=1)
    include_trace: bool = True
    environment: str = "development"


class AgentConfig(BaseModel):
    """Configuration for agent adapters."""
    agent_id: str
    agent_type: str = Field(pattern="^(claude_code|codex_cli|generic)$")
    name: str
    version: str
    enabled: bool = True
    connection_timeout: int = Field(default=120, gt=0)
    max_cost_per_request: float = Field(default=0.1, gt=0)
    health_check_interval: int = Field(default=60, gt=0)
    retry_attempts: int = Field(default=3, ge=0)

    # Agent-specific configurations
    command_path: Optional[str] = None
    working_directory: Optional[str] = None
    environment_variables: Dict[str, str] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)


class PolicyConfig(BaseModel):
    """Configuration for security policies."""
    policy_id: str
    name: str
    description: str
    permission_mode: str = Field(default="prompt", pattern="^(auto|prompt|deny)$")
    allowed_tools: List[str] = field(default_factory=list)
    disallowed_tools: List[str] = field(default_factory=list)
    resource_limits: Dict[str, Union[int, float]] = field(default_factory=dict)
    file_access_rules: Dict[str, List[str]] = field(default_factory=dict)
    network_access_rules: Dict[str, List[str]] = field(default_factory=dict)
    sandbox_enabled: bool = True
    approval_required: List[str] = field(default_factory=list)

    @validator('disallowed_tools')
    def validate_tool_lists(cls, v, values):
        """Ensure allowed and disallowed tools don't overlap."""
        if 'allowed_tools' in values:
            allowed = set(values['allowed_tools'])
            disallowed = set(v)
            overlap = allowed.intersection(disallowed)
            if overlap:
                raise ValueError(f"Tools cannot be both allowed and disallowed: {overlap}")
        return v


class ServerConfig(BaseModel):
    """Configuration for the TAB server."""
    host: str = "localhost"
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=1, ge=1)
    max_connections: int = Field(default=100, ge=1)
    request_timeout: int = Field(default=300, gt=0)
    enable_cors: bool = False
    cors_origins: List[str] = field(default_factory=list)


class SessionConfig(BaseModel):
    """Configuration for conversation sessions."""
    default_max_turns: int = Field(default=8, ge=1, le=50)
    default_budget_usd: float = Field(default=1.0, gt=0)
    session_timeout: int = Field(default=3600, gt=0)  # 1 hour
    turn_timeout: int = Field(default=120, gt=0)  # 2 minutes
    max_active_sessions: int = Field(default=50, ge=1)
    enable_persistence: bool = True
    storage_directory: str = "~/.tab/sessions"


class ServiceContainerConfig(BaseModel):
    """Configuration for service dependency injection container."""
    session_manager: Dict[str, Any] = field(default_factory=dict)
    policy_enforcer: Dict[str, Any] = field(default_factory=dict)
    conversation_orchestrator: Dict[str, Any] = field(default_factory=dict)

    # Service interface settings
    async_adapter_pool_size: int = Field(default=20, ge=1, le=100)
    circuit_breaker_threshold: int = Field(default=5, ge=1)
    health_check_interval: int = Field(default=60, ge=10)

    # Observability settings
    trace_service_calls: bool = Field(default=True)
    log_service_errors: bool = Field(default=True)
    metrics_collection: bool = Field(default=True)


class TABConfig(BaseModel):
    """Main TAB configuration."""
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    service_container: ServiceContainerConfig = field(default_factory=ServiceContainerConfig)
    agents: Dict[str, AgentConfig] = field(default_factory=dict)
    policies: Dict[str, PolicyConfig] = field(default_factory=dict)

    # Global settings
    debug: bool = False
    config_file_path: Optional[str] = None


class ConfigurationManager:
    """Manages TAB configuration loading and validation."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config: Optional[TABConfig] = None

    def _get_default_config_path(self) -> str:
        """Get the default configuration file path."""
        # Check environment variable first
        if "TAB_CONFIG_PATH" in os.environ:
            return os.environ["TAB_CONFIG_PATH"]

        # Check standard locations
        candidates = [
            "~/.tab/config/config.yaml",
            "./config/config.yaml",
            "./config.yaml"
        ]

        for candidate in candidates:
            path = Path(candidate).expanduser()
            if path.exists():
                return str(path)

        # Return default location
        return "~/.tab/config/config.yaml"

    def load_config(self, config_path: Optional[str] = None) -> TABConfig:
        """Load and validate configuration from file."""
        if config_path:
            self.config_path = config_path

        config_file = Path(self.config_path).expanduser()

        if not config_file.exists():
            # Create default configuration
            self._create_default_config(config_file)

        try:
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f) or {}

            # Merge with environment variables
            config_data = self._merge_environment_config(config_data)

            # Validate and create configuration object
            self.config = TABConfig(**config_data)
            self.config.config_file_path = str(config_file)

            return self.config

        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in config file {config_file}: {e}")
        except ValidationError as e:
            raise ConfigurationError(f"Configuration validation failed: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error loading configuration: {e}")

    def _create_default_config(self, config_file: Path) -> None:
        """Create a default configuration file."""
        config_file.parent.mkdir(parents=True, exist_ok=True)

        default_config = {
            "observability": {
                "service_name": "tab-orchestrator",
                "environment": "development",
                "otlp_endpoint": os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
            },
            "logging": {
                "level": os.getenv("TAB_LOG_LEVEL", "INFO"),
                "directory": "~/.tab/logs"
            },
            "server": {
                "host": os.getenv("TAB_HOST", "localhost"),
                "port": int(os.getenv("TAB_PORT", "8000"))
            },
            "session": {
                "storage_directory": "~/.tab/sessions"
            },
            "agents": {
                "claude_code": {
                    "agent_id": "claude_code",
                    "agent_type": "claude_code",
                    "name": "Claude Code",
                    "version": "1.0.0",
                    "command_path": "claude",
                    "capabilities": ["code_analysis", "file_operations", "debugging"]
                },
                "codex_cli": {
                    "agent_id": "codex_cli",
                    "agent_type": "codex_cli",
                    "name": "Codex CLI",
                    "version": "1.0.0",
                    "command_path": "codex",
                    "capabilities": ["code_generation", "execution", "testing"]
                }
            },
            "policies": {
                "default": {
                    "policy_id": "default",
                    "name": "Default Policy",
                    "description": "Default security policy for general use",
                    "permission_mode": "prompt",
                    "sandbox_enabled": True,
                    "resource_limits": {
                        "max_execution_time_ms": 120000,
                        "max_cost_usd": 0.1
                    }
                },
                "read_only": {
                    "policy_id": "read_only",
                    "name": "Read Only Policy",
                    "description": "Restrictive policy for read-only operations",
                    "permission_mode": "deny",
                    "disallowed_tools": ["write", "delete", "execute"],
                    "sandbox_enabled": True
                }
            }
        }

        with open(config_file, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False, indent=2)

    def _merge_environment_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Merge configuration with environment variables."""
        env_mappings = {
            "TAB_LOG_LEVEL": ["logging", "level"],
            "TAB_HOST": ["server", "host"],
            "TAB_PORT": ["server", "port"],
            "TAB_DEBUG": ["debug"],
            "OTEL_EXPORTER_OTLP_ENDPOINT": ["observability", "otlp_endpoint"]
        }

        for env_var, config_path in env_mappings.items():
            if env_var in os.environ:
                value = os.environ[env_var]

                # Type conversion for specific fields
                if env_var == "TAB_PORT":
                    value = int(value)
                elif env_var == "TAB_DEBUG":
                    value = value.lower() in ("true", "1", "yes")

                # Set nested configuration value
                current = config_data
                for key in config_path[:-1]:
                    current = current.setdefault(key, {})
                current[config_path[-1]] = value

        return config_data

    def get_config(self) -> TABConfig:
        """Get the loaded configuration."""
        if self.config is None:
            raise ConfigurationError("Configuration not loaded. Call load_config() first.")
        return self.config

    def get_agent_config(self, agent_id: str) -> AgentConfig:
        """Get configuration for a specific agent."""
        config = self.get_config()
        if agent_id not in config.agents:
            raise ConfigurationError(f"Agent configuration not found: {agent_id}")
        return config.agents[agent_id]

    def get_policy_config(self, policy_id: str) -> PolicyConfig:
        """Get configuration for a specific policy."""
        config = self.get_config()
        if policy_id not in config.policies:
            raise ConfigurationError(f"Policy configuration not found: {policy_id}")
        return config.policies[policy_id]

    def validate_config(self) -> List[str]:
        """Validate the current configuration and return any warnings."""
        warnings = []
        config = self.get_config()

        # Check for common configuration issues
        if config.debug and config.observability.environment == "production":
            warnings.append("Debug mode enabled in production environment")

        if config.observability.trace_sampling_ratio < 1.0 and config.observability.environment == "development":
            warnings.append("Trace sampling ratio less than 1.0 in development environment")

        # Validate agent configurations
        for agent_id, agent_config in config.agents.items():
            if agent_config.command_path and not Path(agent_config.command_path).exists():
                warnings.append(f"Agent command path does not exist: {agent_config.command_path}")

        # Validate policy configurations
        for policy_id, policy_config in config.policies.items():
            if not policy_config.allowed_tools and not policy_config.disallowed_tools:
                warnings.append(f"Policy {policy_id} has no tool restrictions defined")

        return warnings

    def reload_config(self) -> TABConfig:
        """Reload configuration from file."""
        return self.load_config()


class ConfigurationError(Exception):
    """Exception raised for configuration-related errors."""
    pass


# Global configuration manager instance
_config_manager: Optional[ConfigurationManager] = None


def initialize_config(config_path: Optional[str] = None) -> ConfigurationManager:
    """Initialize global configuration manager."""
    global _config_manager
    _config_manager = ConfigurationManager(config_path)
    _config_manager.load_config()
    return _config_manager


def get_config_manager() -> ConfigurationManager:
    """Get the global configuration manager instance."""
    if _config_manager is None:
        raise ConfigurationError("Configuration not initialized. Call initialize_config() first.")
    return _config_manager


def get_config() -> TABConfig:
    """Get the global configuration."""
    return get_config_manager().get_config()


def get_agent_config(agent_id: str) -> AgentConfig:
    """Get configuration for a specific agent."""
    return get_config_manager().get_agent_config(agent_id)


def get_policy_config(policy_id: str) -> PolicyConfig:
    """Get configuration for a specific policy."""
    return get_config_manager().get_policy_config(policy_id)