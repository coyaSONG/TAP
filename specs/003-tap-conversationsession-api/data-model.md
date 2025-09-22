# Data Model: TAP Agent Dialog Integration

**Date**: 2025-09-22
**Feature**: Service layer integration for real multi-agent conversations

## Service Interface Abstractions

### IConversationSessionService Interface

Core abstract interface for conversation session management:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import Field, validate_call

class IConversationSessionService(ABC):
    """Abstract interface for conversation session management."""

    @validate_call
    @abstractmethod
    async def create_session(
        self,
        topic: str = Field(..., min_length=1, max_length=1000),
        participants: List[str] = Field(..., min_length=2),
        policy_id: str = Field(default="default"),
        max_turns: int = Field(default=8, ge=1, le=20),
        **kwargs
    ) -> ConversationSession:
        """Create new conversation session with validation."""
        pass

    @validate_call
    @abstractmethod
    async def get_session(
        self,
        session_id: str = Field(..., min_length=1)
    ) -> Optional[ConversationSession]:
        """Retrieve session by ID."""
        pass

    @validate_call
    @abstractmethod
    async def add_turn_to_session(
        self,
        session_id: str = Field(..., min_length=1),
        turn: TurnMessage
    ) -> bool:
        """Add turn with policy validation."""
        pass

    @validate_call
    @abstractmethod
    async def get_session_context(
        self,
        session_id: str = Field(..., min_length=1),
        agent_filter: Optional[str] = None,
        limit: int = Field(default=5, ge=1, le=50)
    ) -> List[Dict[str, Any]]:
        """Get conversation context with caching."""
        pass
```

### Service Lifecycle Interface

```python
class IServiceLifecycle(ABC):
    """Interface for service lifecycle management."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize service resources."""
        pass

    @abstractmethod
    async def start(self) -> None:
        """Start service operations."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop service gracefully."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform service health check."""
        pass
```

### Policy Validation Interface

```python
class IPolicyValidator(ABC):
    """Interface for policy enforcement."""

    @abstractmethod
    async def validate_session_creation(
        self,
        policy_id: str,
        session_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate session creation against policy."""
        pass

    @abstractmethod
    async def validate_turn_addition(
        self,
        policy_id: str,
        session: ConversationSession,
        turn: TurnMessage
    ) -> Dict[str, Any]:
        """Validate turn addition against policy."""
        pass
```

## Enhanced Configuration Models

### Enhanced Service Configuration

```python
class ServiceContainerConfig(BaseModel):
    """Configuration for service dependency injection."""

    session_manager: Dict[str, Any] = Field(default_factory=dict)
    policy_enforcer: Dict[str, Any] = Field(default_factory=dict)
    conversation_orchestrator: Dict[str, Any] = Field(default_factory=dict)

    # Service interface settings
    async_adapter_pool_size: int = Field(default=20, ge=1, le=100)
    circuit_breaker_threshold: int = Field(default=5, ge=1)
    health_check_interval: int = Field(default=60, ge=10)

    # Observability settings
    trace_service_calls: bool = Field(default=True)
    log_service_errors: bool = Field(default=True)
    metrics_collection: bool = Field(default=True)
```

### Dynamic Agent Configuration

```python
from enum import Enum
from typing import Union, Literal

class AgentLoadingStrategy(str, Enum):
    """Strategy for loading agent implementations."""
    BUILTIN = "builtin"
    ENTRY_POINT = "entry_point"
    MODULE_CLASS = "module_class"

class DynamicAgentConfig(BaseModel):
    """Enhanced agent configuration with dynamic loading."""

    # Existing fields preserved
    agent_id: str
    agent_type: str  # Now accepts any string
    name: str
    version: str = Field(default="1.0.0")
    enabled: bool = Field(default=True)

    # Dynamic loading configuration
    loading_strategy: AgentLoadingStrategy = Field(default=AgentLoadingStrategy.BUILTIN)
    entry_point: Optional[str] = Field(None, description="Entry point name for plugin loading")
    module_path: Optional[str] = Field(None, description="Python module path")
    class_name: Optional[str] = Field(None, description="Agent class name")

    # Enhanced capability management
    static_capabilities: List[str] = Field(default_factory=list)
    capability_discovery: bool = Field(default=True)
    environment_requirements: List[str] = Field(default_factory=list)

    # Existing connection and execution configs preserved
    connection_config: ConnectionConfig = Field(default_factory=ConnectionConfig)
    execution_limits: ExecutionLimits = Field(default_factory=ExecutionLimits)

    # Plugin-specific configuration
    plugin_config: Dict[str, Any] = Field(default_factory=dict)
    initialization_params: Dict[str, Any] = Field(default_factory=dict)

    @validator('loading_strategy')
    def validate_loading_config(cls, v, values):
        """Validate loading configuration completeness."""
        if v == AgentLoadingStrategy.ENTRY_POINT and not values.get('entry_point'):
            raise ValueError("entry_point required when using ENTRY_POINT strategy")
        if v == AgentLoadingStrategy.MODULE_CLASS:
            if not values.get('module_path') or not values.get('class_name'):
                raise ValueError("module_path and class_name required when using MODULE_CLASS strategy")
        return v
```

### Service Registry Model

```python
class ServiceRegistration(BaseModel):
    """Model for service registration in container."""

    service_id: str
    interface_type: str
    implementation_class: str
    config_section: str
    singleton: bool = Field(default=True)
    initialization_order: int = Field(default=100, ge=1)
    health_check_enabled: bool = Field(default=True)
    dependencies: List[str] = Field(default_factory=list)

class AgentRegistration(BaseModel):
    """Model for agent registration."""

    agent_id: str
    config: DynamicAgentConfig
    registration_time: datetime
    health_status: AgentStatus = Field(default=AgentStatus.UNKNOWN)
    capabilities: List[str] = Field(default_factory=list)
    last_health_check: Optional[datetime] = None
```

## Enhanced ConversationSession Extensions

### Missing Method Specifications

Based on the existing implementation, formalize the missing method contracts:

```python
class ConversationSessionExtensions:
    """Extended method contracts for ConversationSession."""

    def should_auto_complete(self) -> bool:
        """
        Determine if conversation should auto-complete based on convergence signals.

        Returns:
            bool: True if conversation should be automatically completed

        Implementation based on check_convergence_signals() results:
        - explicit_completion signals → True
        - resource_exhaustion + high confidence → True
        - repetitive_content + low progress → True
        - Otherwise → False
        """
        pass

    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get conversation summary statistics.

        Returns:
            Dict containing:
            - total_turns: int
            - total_cost: float
            - avg_turn_length: float
            - participants_activity: Dict[str, int]
            - duration_minutes: float
            - convergence_confidence: float
        """
        pass

    def get_session_status(self) -> Dict[str, Any]:
        """
        Get current session status with details.

        Returns:
            Dict containing:
            - status: SessionStatus
            - turn_progress: Dict[str, int]  # current/max
            - budget_progress: Dict[str, float]  # used/total
            - health_indicators: List[str]
            - next_actions: List[str]
        """
        pass
```

### State Transition Enhancements

```python
class SessionStateTransition(BaseModel):
    """Model for session state transitions."""

    from_status: SessionStatus
    to_status: SessionStatus
    reason: str
    triggered_by: str  # agent_id or "system"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    context: Dict[str, Any] = Field(default_factory=dict)

class ConversationMetrics(BaseModel):
    """Model for conversation performance metrics."""

    session_id: str
    total_turns: int = Field(default=0)
    avg_response_time_ms: float = Field(default=0.0)
    total_duration_seconds: float = Field(default=0.0)
    agent_participation: Dict[str, int] = Field(default_factory=dict)
    convergence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    quality_indicators: Dict[str, float] = Field(default_factory=dict)
```

## Service Integration Schemas

### Constructor Dependency Schema

```python
class ServiceDependencies(BaseModel):
    """Model for service constructor dependencies."""

    session_manager_config: Optional[SessionConfig] = None
    policy_configs: Optional[Dict[str, PolicyConfig]] = None
    agent_configs: Optional[Dict[str, DynamicAgentConfig]] = None
    observability_config: Optional[ObservabilityConfig] = None

    def get_session_manager_args(self) -> Dict[str, Any]:
        """Get arguments for SessionManager constructor."""
        return self.session_manager_config.dict() if self.session_manager_config else {}

    def get_policy_enforcer_args(self) -> Dict[str, Any]:
        """Get arguments for PolicyEnforcer constructor."""
        return {"config": self.policy_configs} if self.policy_configs else {}

    def get_orchestrator_args(self, session_manager, policy_enforcer) -> Dict[str, Any]:
        """Get arguments for ConversationOrchestrator constructor."""
        return {
            "session_manager": session_manager,
            "policy_enforcer": policy_enforcer,
            "agent_configs": self.agent_configs or {}
        }
```

### API Unification Schema

```python
class UnifiedAPIParameters(BaseModel):
    """Unified parameter naming across service interfaces."""

    # Context retrieval parameters
    session_id: str
    agent_filter: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=50)  # Unified from max_turns

    # Session creation parameters
    topic: str = Field(..., min_length=1, max_length=1000)
    participants: List[str] = Field(..., min_length=2)
    policy_id: str = Field(default="default")
    max_turns: int = Field(default=8, ge=1, le=20)

    # Turn addition parameters
    turn_data: TurnMessage
    validate_policy: bool = Field(default=True)
    update_convergence: bool = Field(default=True)

    def to_legacy_params(self) -> Dict[str, Any]:
        """Convert to legacy parameter names for backward compatibility."""
        params = self.dict()
        if "limit" in params:
            params["max_turns"] = params["limit"]  # Legacy compatibility
        return params
```

## Validation Rules

### Service Interface Validation

- All service methods must be async and return appropriate types
- Service constructors must accept configuration objects matching container expectations
- All service interfaces must implement health_check() method
- Service registration must specify dependencies and initialization order

### Agent Configuration Validation

- Dynamic agent configs must specify complete loading strategy
- Agent implementations must extend BaseAgentAdapter
- Environment requirements must be verifiable commands or packages
- Plugin configurations must pass Pydantic validation

### Session Management Validation

- Session state transitions must follow defined state machine
- Turn additions must respect session limits and policy constraints
- Context retrieval must validate agent filter against session participants
- Convergence detection must produce deterministic confidence scores

### API Compatibility Validation

- Parameter names must be unified across all service interfaces
- Legacy parameter support must be maintained during transition
- Return types must be consistent with existing API contracts
- Error types and messages must preserve existing behavior

This data model provides the foundation for implementing service layer integration while maintaining compatibility with existing TAB architecture and enabling dynamic agent extensibility.