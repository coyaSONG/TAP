# Data Model: ConversationSession Method Extensions

**Date**: 2025-09-22
**Feature**: Multi-turn conversation context management

## Extended ConversationSession Model

### New Methods

#### add_turn_message(turn: TurnMessage) -> bool
**Purpose**: Add a new turn to the conversation with validation and state updates

**Parameters**:
- `turn: TurnMessage` - Validated turn message to add to conversation

**Returns**:
- `bool` - True if turn was added successfully, False if constraints violated

**Validation Rules**:
- Session must be in ACTIVE status
- Must not exceed max_turns limit
- Must not exceed budget_usd limit
- turn.session_id must match session.session_id
- turn.from_agent must be in participants list

**State Changes**:
- Increments current_turn counter
- Updates total_cost_usd with turn.cost_usd
- Appends turn to turn_history list
- Updates updated_at timestamp

**Error Handling**:
- ValidationError for invalid turn data
- ValueError for constraint violations
- Graceful failure with detailed error messages

#### get_conversation_context(agent_filter: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]
**Purpose**: Retrieve recent conversation context for agent consumption

**Parameters**:
- `agent_filter: Optional[str]` - Filter by specific agent ID (from_agent or to_agent)
- `limit: int` - Maximum number of recent turns to return (default: 5)

**Returns**:
- `List[Dict[str, Any]]` - List of turn messages in standard chat format

**Filtering Logic**:
- If agent_filter provided: return turns where from_agent == agent_filter OR to_agent == agent_filter
- If no filter: return all recent turns
- Always ordered by timestamp (newest first)
- Limited to specified number of turns

**Output Format**:
Uses TurnMessage.to_chat_format() for each turn:
```python
{
    "role": "assistant",
    "content": "message content",
    "from_agent": "claude_code",
    "timestamp": "2025-09-22T10:30:00Z",
    "attachments": [...] or None
}
```

#### check_convergence_signals() -> Dict[str, Any]
**Purpose**: Analyze conversation for completion indicators

**Returns**:
- `Dict[str, Any]` - Structured convergence assessment

**Analysis Components**:
1. **Repetition Detection**: Identify repeated content patterns in recent turns
2. **Explicit Completion**: Detect completion statements ("task completed", "solved", etc.)
3. **Turn Limit Proximity**: Warn when approaching max_turns
4. **Budget Proximity**: Warn when approaching budget_usd limit
5. **Conversation Quality**: Basic metrics on turn length and engagement

**Return Structure**:
```python
{
    "should_continue": bool,
    "confidence": float,  # 0.0 to 1.0
    "signals": {
        "repetitive_content": bool,
        "explicit_completion": bool,
        "resource_exhaustion": bool,
        "quality_degradation": bool
    },
    "recommendations": List[str],
    "metadata": {
        "turns_analyzed": int,
        "avg_turn_length": float,
        "completion_keywords": List[str]
    }
}
```

## Integration Requirements

### Type Safety Updates
- Update turn_history field annotation from `List[Any]` to `List[TurnMessage]`
- Maintain backward compatibility during transition period
- Add runtime type checking for turn_history items

### Observability Integration
- Add OpenTelemetry spans for each method
- Instrument context retrieval latency
- Track convergence detection accuracy
- Log method usage patterns

### Policy Integration
- Respect existing PolicyEnforcer constraints
- Generate audit records for context access
- Validate agent permissions for context retrieval
- Enforce conversation-level security policies

## Validation Rules

### Session State Validation
- All methods verify session is in valid state for operation
- add_turn_message requires ACTIVE status
- Context methods work in any status (read-only)
- Methods update session state consistently

### Data Integrity
- Turn message session_id consistency
- Participant validation for turn authors
- Timestamp ordering in turn_history
- Cost accumulation accuracy

### Performance Constraints
- Context retrieval limited to reasonable turn counts
- Convergence analysis bounded by computational limits
- Memory usage controlled via configurable limits
- Response time targets: <100ms for context, <500ms for convergence

## Error Handling Patterns

### Validation Errors
- Use Pydantic ValidationError for data issues
- Provide specific field-level error messages
- Include suggested corrections where possible

### Constraint Violations
- Use ValueError for business rule violations
- Include current vs. limit values in messages
- Suggest alternative actions (e.g., increase budget)

### System Errors
- Graceful degradation for convergence analysis failures
- Context retrieval fallbacks (reduced data)
- Comprehensive error logging for debugging