# Research: Multi-Turn Conversation Context Management

**Date**: 2025-09-22
**Feature**: ConversationSession missing methods implementation

## Current TAB Architecture Analysis

### Decision: Use existing Pydantic models and integrate with TAB services
**Rationale**: ConversationSession and TurnMessage models already exist with comprehensive validation, field constraints, and proper typing. Missing methods should extend existing functionality rather than rewrite.

**Alternatives considered**:
- Creating new models from scratch - rejected due to breaking existing integrations
- Using dict-based storage - rejected due to lack of type safety and validation

### Decision: Implement methods within existing model classes
**Rationale**: ConversationSession.py already has business logic methods (can_add_turn, transition_to), following established pattern for new methods.

**Alternatives considered**:
- Separate service classes - rejected due to TAB preference for model-based business logic
- Utility functions - rejected due to lack of access to instance state

### Decision: Use TurnMessage model for strong typing in conversation context
**Rationale**: TurnMessage has comprehensive validation, policy constraints, and attachment support. Provides structured format via to_chat_format() method.

**Alternatives considered**:
- Raw dict format - rejected due to loss of validation and type safety
- Custom context objects - rejected due to duplication of existing functionality

## Implementation Research

### Missing Method Analysis

1. **add_turn_message(turn: TurnMessage)**
   - Should validate turn limits, budget constraints via existing can_add_turn()
   - Update current_turn counter and total_cost_usd
   - Append to turn_history list (currently typed as List[Any])
   - Update updated_at timestamp
   - Integrate with observability spans

2. **get_conversation_context(agent_filter: Optional[str] = None, limit: int = 5)**
   - Return recent turns in structured format for agent consumption
   - Filter by from_agent/to_agent if agent_filter provided
   - Use TurnMessage.to_chat_format() for standardized output
   - Implement memory management with configurable limit

3. **check_convergence_signals() -> Dict[str, Any]**
   - Analyze turn_history for conversation completion indicators
   - Detect repetitive content patterns
   - Check for explicit completion statements
   - Return structured convergence assessment

### Integration Points

- **PolicyEnforcer**: Methods should respect existing policy constraints
- **OpenTelemetry**: Add spans for conversation.context_retrieval and conversation.convergence_check
- **Observability**: Integrate with existing metrics collection
- **JSONL Session Logs**: Methods should work with existing session persistence

### Backward Compatibility Requirements

- turn_history field is List[Any] - must maintain compatibility
- Existing session validation and state transitions must continue working
- Integration with ConversationOrchestrator must remain seamless
- real_ai_tab.py usage patterns must be preserved

## Performance Considerations

### Decision: Memory-efficient context windows
**Rationale**: Conversation history can grow large; context retrieval should be O(1) with configurable limits to prevent memory issues.

**Alternatives considered**:
- Full history return - rejected due to memory and processing overhead
- Database storage - rejected as current implementation uses in-memory + JSONL

### Decision: Simple convergence detection algorithms
**Rationale**: Start with basic pattern matching and explicit signals rather than complex NLP analysis for MVP implementation.

**Alternatives considered**:
- LLM-based convergence detection - rejected due to cost and latency
- Complex similarity analysis - rejected due to computational overhead

## Security Integration

### Decision: Maintain existing security boundaries
**Rationale**: New methods should integrate with PolicyEnforcer and audit logging without introducing new security vectors.

**Implementation approach**:
- Use existing policy constraint validation patterns
- Integrate with audit record generation via TurnMessage.to_audit_record()
- Follow observability patterns for security monitoring

## Research Conclusion

All technical requirements are clear and implementable within existing TAB architecture. No external dependencies or architectural changes required. Implementation can proceed directly to Phase 1 design.