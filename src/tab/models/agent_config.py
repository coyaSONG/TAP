"""Dynamic agent configuration models for extensible agent loading.

Provides configuration models for dynamic agent registration, plugin loading,
and runtime agent capability discovery.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, validator


class AgentLoadingStrategy(str, Enum):
    """Strategy for loading agent implementations."""
    BUILTIN = "builtin"
    ENTRY_POINT = "entry_point"
    MODULE_CLASS = "module_class"
    PLUGIN = "plugin"


class AgentCapabilityType(str, Enum):
    """Types of agent capabilities."""
    CODE_ANALYSIS = "code_analysis"
    CODE_GENERATION = "code_generation"
    FILE_OPERATIONS = "file_operations"
    DEBUGGING = "debugging"
    TESTING = "testing"
    EXECUTION = "execution"
    TEXT_PROCESSING = "text_processing"
    API_INTERACTION = "api_interaction"
    DATABASE_OPERATIONS = "database_operations"
    CUSTOM = "custom"


class DynamicAgentConfig(BaseModel):
    """Enhanced agent configuration with dynamic loading support."""

    # Core agent identification
    agent_id: str = Field(..., min_length=1, max_length=50)
    agent_type: str = Field(..., min_length=1)  # Now accepts any string
    name: str = Field(..., min_length=1, max_length=100)
    version: str = Field(default="1.0.0")
    enabled: bool = Field(default=True)
    description: Optional[str] = Field(None, max_length=500)

    # Dynamic loading configuration
    loading_strategy: AgentLoadingStrategy = Field(default=AgentLoadingStrategy.BUILTIN)
    entry_point: Optional[str] = Field(None, description="Entry point name for plugin loading")
    module_path: Optional[str] = Field(None, description="Python module path")
    class_name: Optional[str] = Field(None, description="Agent class name")
    plugin_package: Optional[str] = Field(None, description="Plugin package name")

    # Enhanced capability management
    static_capabilities: List[str] = Field(default_factory=list)
    capability_discovery: bool = Field(default=True)
    runtime_capabilities: List[str] = Field(default_factory=list)
    environment_requirements: List[str] = Field(default_factory=list)

    # Connection and execution configuration
    connection_timeout: int = Field(default=120, ge=1)
    max_cost_per_request: float = Field(default=0.1, gt=0)
    health_check_interval: int = Field(default=60, ge=10)
    retry_attempts: int = Field(default=3, ge=0)

    # Execution limits
    max_execution_time_ms: int = Field(default=120000, ge=1000)
    max_memory_mb: int = Field(default=512, ge=64)
    max_file_size_mb: int = Field(default=10, ge=1)

    # Plugin-specific configuration
    plugin_config: Dict[str, Any] = Field(default_factory=dict)
    initialization_params: Dict[str, Any] = Field(default_factory=dict)
    environment_variables: Dict[str, str] = Field(default_factory=dict)

    # Security and validation
    security_policy: str = Field(default="default")
    sandbox_enabled: bool = Field(default=True)
    allowed_operations: List[str] = Field(default_factory=list)
    restricted_operations: List[str] = Field(default_factory=list)

    @validator('loading_strategy')
    def validate_loading_config(cls, v, values):
        """Validate loading configuration completeness."""
        if v == AgentLoadingStrategy.ENTRY_POINT and not values.get('entry_point'):
            raise ValueError("entry_point required when using ENTRY_POINT strategy")
        if v == AgentLoadingStrategy.MODULE_CLASS:
            if not values.get('module_path') or not values.get('class_name'):
                raise ValueError("module_path and class_name required when using MODULE_CLASS strategy")
        if v == AgentLoadingStrategy.PLUGIN and not values.get('plugin_package'):
            raise ValueError("plugin_package required when using PLUGIN strategy")
        return v

    @validator('static_capabilities')
    def validate_capabilities(cls, v):
        """Validate capability strings."""
        valid_capabilities = {cap.value for cap in AgentCapabilityType}
        for capability in v:
            if capability not in valid_capabilities and not capability.startswith("custom:"):
                raise ValueError(f"Invalid capability: {capability}. Must be a valid AgentCapabilityType or start with 'custom:'")
        return v

    @validator('environment_requirements')
    def validate_environment_requirements(cls, v):
        """Validate environment requirement format."""
        for req in v:
            if not isinstance(req, str) or not req.strip():
                raise ValueError("Environment requirements must be non-empty strings")
        return v


class AgentRegistration(BaseModel):
    """Model for tracking agent registration state."""

    agent_id: str
    config: DynamicAgentConfig
    registration_time: datetime = Field(default_factory=datetime.utcnow)
    last_health_check: Optional[datetime] = None
    health_status: str = Field(default="unknown", pattern="^(healthy|unhealthy|unknown|initializing|error)$")

    # Discovered capabilities and metadata
    discovered_capabilities: List[str] = Field(default_factory=list)
    runtime_metadata: Dict[str, Any] = Field(default_factory=dict)
    error_count: int = Field(default=0, ge=0)
    last_error: Optional[str] = None

    # Performance tracking
    avg_response_time_ms: float = Field(default=0.0, ge=0)
    total_requests: int = Field(default=0, ge=0)
    successful_requests: int = Field(default=0, ge=0)

    @property
    def success_rate(self) -> float:
        """Calculate agent success rate."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def is_healthy(self) -> bool:
        """Check if agent is healthy."""
        return self.health_status == "healthy"


class AgentPluginManifest(BaseModel):
    """Manifest for agent plugin packages."""

    plugin_name: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    author: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)

    # Plugin metadata
    supported_agent_types: List[str] = Field(..., min_items=1)
    required_dependencies: List[str] = Field(default_factory=list)
    optional_dependencies: List[str] = Field(default_factory=list)
    minimum_python_version: str = Field(default="3.11")

    # Plugin configuration schema
    configuration_schema: Dict[str, Any] = Field(default_factory=dict)
    default_configuration: Dict[str, Any] = Field(default_factory=dict)

    # Entry points and loading
    entry_points: Dict[str, str] = Field(..., min_items=1)
    initialization_hooks: List[str] = Field(default_factory=list)
    cleanup_hooks: List[str] = Field(default_factory=list)


class AgentCapabilitySpec(BaseModel):
    """Specification for agent capabilities."""

    capability_id: str = Field(..., min_length=1)
    capability_type: AgentCapabilityType
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)

    # Capability metadata
    parameters: Dict[str, Any] = Field(default_factory=dict)
    return_type: Optional[str] = None
    examples: List[Dict[str, Any]] = Field(default_factory=list)

    # Runtime requirements
    requires_context: bool = Field(default=False)
    requires_environment: List[str] = Field(default_factory=list)
    resource_intensive: bool = Field(default=False)


class AgentLoadingResult(BaseModel):
    """Result of agent loading operation."""

    agent_id: str
    success: bool
    loading_strategy_used: AgentLoadingStrategy
    load_time_ms: float = Field(ge=0)

    # Success details
    agent_class: Optional[str] = None
    discovered_capabilities: List[str] = Field(default_factory=list)

    # Error details
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    traceback: Optional[str] = None

    # Loading metadata
    plugin_info: Optional[Dict[str, Any]] = None
    dependency_validation: Dict[str, bool] = Field(default_factory=dict)


def create_builtin_agent_config(agent_id: str, agent_type: str, name: str) -> DynamicAgentConfig:
    """Create a configuration for a built-in agent."""
    return DynamicAgentConfig(
        agent_id=agent_id,
        agent_type=agent_type,
        name=name,
        loading_strategy=AgentLoadingStrategy.BUILTIN,
        static_capabilities=["basic_operations"],
        capability_discovery=True,
        environment_requirements=[],
        connection_timeout=120,
        max_execution_time_ms=120000,
        sandbox_enabled=True
    )


def create_plugin_agent_config(
    agent_id: str,
    agent_type: str,
    name: str,
    plugin_package: str,
    entry_point: str
) -> DynamicAgentConfig:
    """Create a configuration for a plugin-based agent."""
    return DynamicAgentConfig(
        agent_id=agent_id,
        agent_type=agent_type,
        name=name,
        loading_strategy=AgentLoadingStrategy.PLUGIN,
        plugin_package=plugin_package,
        entry_point=entry_point,
        capability_discovery=True,
        sandbox_enabled=True,
        security_policy="plugin_default"
    )