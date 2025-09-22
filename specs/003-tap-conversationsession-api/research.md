# Research: TAP Agent Dialog Integration

**Date**: 2025-09-22
**Feature**: Service layer integration for real multi-agent conversations

## Research Findings

### Decision: Fix Service Constructor Dependency Injection Pattern
**Rationale**: TAP already implements configuration-driven dependency injection in TABApplication, but service constructors don't match expected signatures. Current implementation expects `SessionManager(config.session)` and `PolicyEnforcer(config.policies)` but constructors don't accept these parameters.

**Current Architecture Analysis**:
- TABApplication acts as service container with manual dependency wiring
- Configuration uses Pydantic models with structured nested objects
- Only SessionManager properly accepts configuration parameters
- PolicyEnforcer and ConversationOrchestrator use parameter-less constructors with internal defaults

**Implementation Approach**:
- Update service constructors to accept configuration objects
- Maintain existing configuration schema and validation
- Use constructor injection pattern already established in BaseAgentAdapter
- Preserve singleton lifecycle management in TABApplication

**Alternatives considered**:
- Formal DI container (Spring-style) - rejected due to over-engineering for current scope
- Service locator pattern - rejected due to hidden dependencies and testing complexity

### Decision: Use ThreadPool Adapter for Sync-to-Async Service Integration
**Rationale**: TAB already implements solid async foundation with BaseAgentAdapter and ConversationOrchestrator. Need compatibility layer for existing sync operations without breaking async patterns.

**Implementation Approach**:
- Use `asyncio.to_thread()` for simple sync operations (Python 3.9+ preferred)
- ThreadPoolExecutor for more complex sync-to-async wrapping
- Circuit breaker pattern for external sync operations resilience
- Maintain existing OpenTelemetry observability integration

**Performance Considerations**:
- Thread pool size: 20 workers for I/O-bound operations
- Timeout handling with `asyncio.wait_for()`
- Resource pool management with metrics tracking
- Exception translation across sync/async boundaries

**Alternatives considered**:
- ProcessPool for CPU-bound operations - not needed for current service layer fixes
- Full async rewrite - rejected due to backward compatibility requirements

### Decision: Implement Interface Segregation with Abstract Base Classes
**Rationale**: TAB already uses ABC pattern effectively in BaseAgentAdapter. Extend this pattern to standardize service interfaces while maintaining existing service implementations.

**Interface Design Approach**:
- Create `IConversationSessionService` abstract base with focused interfaces
- Separate concerns: SessionCreation, SessionQuery, SessionContext, PolicyValidation
- Use Pydantic `@validate_call` for method signature standardization
- Maintain async-first interface design consistent with existing patterns

**Integration Strategy**:
- SessionManager implements SessionCreation and SessionQuery interfaces
- PolicyEnforcer implements PolicyValidation interface
- ConversationOrchestrator implements orchestration interface
- Create adapter pattern for backward compatibility during transition

**Alternatives considered**:
- Single large interface - rejected due to Interface Segregation Principle
- Duck typing without abstractions - rejected due to lack of contract validation

### Decision: Configuration-Driven Dynamic Agent Loading with Entry Points
**Rationale**: Current hardcoded agent validation in ConversationSession limits extensibility. Need dynamic agent registration while maintaining type safety and security.

**Implementation Strategy**:
- Extend existing AgentConfig with dynamic loading fields
- Use Python entry points for plugin discovery (`tab.agents` group)
- Implement AgentRegistry for dynamic discovery and validation
- Maintain existing agent lifecycle management patterns

**Security and Validation**:
- Agent class validation against BaseAgentAdapter interface
- Runtime capability detection and validation
- Integration with existing PolicyEnforcer for plugin security
- Graceful degradation for failed agent loading

**Configuration Schema Extensions**:
```yaml
agents:
  new_agent:
    agent_type: "custom_type"  # No longer limited to enum
    loading_strategy: "entry_point"
    entry_point: "my_agent_plugin"
    capability_discovery: "full"
    environment_requirements: ["custom_tool"]
```

**Alternatives considered**:
- Module path loading - supported as fallback option
- Factory function pattern - supported for complex initialization
- Static agent registration - rejected due to extensibility limitations

## Technical Implementation Decisions

### Service Constructor Pattern
Update service constructors to match TABApplication expectations:
```python
class PolicyEnforcer:
    def __init__(self, config: Dict[str, PolicyConfig]):
        self._policies = {k: PolicyConfiguration(**v.dict()) for k, v in config.items()}

class ConversationOrchestrator:
    def __init__(self, session_manager: SessionManager,
                 policy_enforcer: PolicyEnforcer,
                 agent_configs: Dict[str, AgentConfig]):
        # Accept injected dependencies
```

### API Parameter Standardization
Unify parameter naming across service interfaces:
- `max_turns` → `limit` in ConversationOrchestrator calls
- Add missing `should_auto_complete()` method to ConversationSession
- Standardize async method signatures using Pydantic validation

### Agent Configuration Flexibility
Remove hardcoded agent type validation:
- ConversationSession.validate_participants() accepts dynamic agent list
- Agent types loaded from configuration instead of enum
- Maintain security through PolicyEnforcer validation

### Backward Compatibility Strategy
- Maintain all existing API surfaces
- Add adapter layers for sync-to-async transitions
- Preserve existing configuration file formats
- Keep current test patterns and extend with new contract tests

## Integration Points

### OpenTelemetry Integration
- Add conversation-specific spans: `conversation.create_session`, `conversation.add_turn`
- Instrument service constructor injection and validation
- Monitor dynamic agent loading performance and success rates
- Maintain existing trace correlation patterns

### Policy Enforcement Integration
- Service constructors validate configuration against policies
- Dynamic agent loading respects security policies
- Session operations enforced through existing policy framework
- Add policy validation for new service interface methods

### Configuration Management
- Extend existing config.yaml schema with service interface settings
- Maintain Pydantic validation for all new configuration fields
- Support environment variable overrides for service behavior
- Preserve existing configuration loading patterns

## Risk Mitigation

### Service Integration Risks
- **Constructor Changes**: Implement gradually with backward compatibility adapters
- **Async Transition**: Use proven ThreadPool patterns with comprehensive testing
- **Interface Changes**: Maintain existing method signatures during transition period

### Dynamic Loading Risks
- **Security**: Validate all dynamic agents against BaseAgentAdapter interface
- **Stability**: Implement circuit breakers and health monitoring for dynamic agents
- **Performance**: Cache capability detection and use lazy loading

### Backward Compatibility Risks
- **Existing Tests**: Ensure all current tests continue passing
- **Configuration**: Maintain existing config file format support
- **API Surface**: Preserve all existing CLI and service APIs

## Validation Approach

### Testing Strategy
- Contract tests for all new service interfaces
- Integration tests for end-to-end conversation flows
- Performance tests for sync-to-async adapter overhead
- Security tests for dynamic agent loading validation

### Rollout Plan
1. Fix service constructors and validate basic dependency injection
2. Implement interface abstractions and verify service compatibility
3. Add dynamic agent loading with comprehensive validation
4. Performance optimization and monitoring integration

All research decisions align with TAB's existing architectural patterns while providing the necessary flexibility for real multi-agent conversation support.