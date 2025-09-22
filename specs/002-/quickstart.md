# Quickstart: ConversationSession Method Extensions

**Feature**: Multi-turn conversation context management
**Time to complete**: 5-10 minutes

## Prerequisites

- Existing TAP development environment
- Python 3.11+ with dependencies installed
- Ability to run pytest tests

## Quick Test Scenarios

### Scenario 1: Add Turn Message Functionality

```python
from src.tab.models.conversation_session import ConversationSession
from src.tab.models.turn_message import TurnMessage, MessageRole

# Create a session
session = ConversationSession(
    participants=["claude_code", "codex_cli"],
    topic="Test conversation context management"
)

# Create a turn message
turn = TurnMessage(
    session_id=session.session_id,
    from_agent="claude_code",
    to_agent="codex_cli",
    role=MessageRole.ASSISTANT,
    content="Hello, I'm ready to help with your task."
)

# Test the new method
success = session.add_turn_message(turn)
assert success == True
assert session.current_turn == 1
assert len(session.turn_history) == 1
```

### Scenario 2: Conversation Context Retrieval

```python
# Add a few more turns for context testing
for i in range(3):
    turn = TurnMessage(
        session_id=session.session_id,
        from_agent="codex_cli" if i % 2 else "claude_code",
        to_agent="claude_code" if i % 2 else "codex_cli",
        role=MessageRole.USER if i % 2 else MessageRole.ASSISTANT,
        content=f"Message {i+2} in the conversation"
    )
    session.add_turn_message(turn)

# Test context retrieval
context = session.get_conversation_context(limit=3)
assert len(context) == 3
assert all("role" in turn for turn in context)
assert all("content" in turn for turn in context)

# Test filtered context
claude_context = session.get_conversation_context(agent_filter="claude_code", limit=5)
assert all(turn["from_agent"] == "claude_code" for turn in claude_context)
```

### Scenario 3: Convergence Signal Detection

```python
# Test convergence analysis
signals = session.check_convergence_signals()

# Verify response structure
required_keys = ["should_continue", "confidence", "signals", "recommendations", "metadata"]
assert all(key in signals for key in required_keys)

# Verify signal types
assert isinstance(signals["should_continue"], bool)
assert 0.0 <= signals["confidence"] <= 1.0
assert isinstance(signals["recommendations"], list)
assert isinstance(signals["metadata"]["turns_analyzed"], int)
```

### Scenario 4: Integration with Existing TAB Services

```python
# Test that methods work with existing session constraints
session.max_turns = 2  # Set low limit for testing
session.current_turn = 1

# This should work (within limits)
turn1 = TurnMessage(
    session_id=session.session_id,
    from_agent="claude_code",
    to_agent="codex_cli",
    role=MessageRole.ASSISTANT,
    content="This should be accepted"
)
assert session.add_turn_message(turn1) == True

# This should fail (exceeds limit)
turn2 = TurnMessage(
    session_id=session.session_id,
    from_agent="codex_cli",
    to_agent="claude_code",
    role=MessageRole.USER,
    content="This should be rejected"
)
assert session.add_turn_message(turn2) == False
```

## Expected Test Results

**All tests should pass** if the implementation is correct:

1. ✅ Turn messages are added successfully within constraints
2. ✅ Context retrieval returns properly formatted data
3. ✅ Convergence analysis provides structured assessment
4. ✅ Existing session validation continues to work
5. ✅ Type safety is maintained throughout

## Validation Commands

Run these commands to validate the implementation:

```bash
# Run contract tests
pytest tests/contract/ -k "conversation_session_methods" -v

# Run integration tests
pytest tests/integration/ -k "conversation_context" -v

# Type checking
mypy src/tab/models/conversation_session.py

# Lint checking
ruff check src/tab/models/conversation_session.py
```

## Common Issues and Solutions

### Issue: Type validation errors
**Solution**: Ensure turn_history is properly typed and TurnMessage objects are validated

### Issue: Session state inconsistencies
**Solution**: Verify that all state updates (current_turn, total_cost_usd, updated_at) happen atomically

### Issue: Context retrieval performance
**Solution**: Ensure context methods don't load excessive data and use proper indexing

### Issue: Convergence analysis false positives
**Solution**: Adjust convergence thresholds and improve pattern detection algorithms

## Next Steps

1. Implement the three missing methods in `ConversationSession`
2. Add comprehensive unit tests for each method
3. Update existing TAB integration points to use new functionality
4. Validate with real conversation scenarios using `real_ai_tab.py`
5. Monitor performance and convergence accuracy in production use

## Success Criteria

- [ ] All quickstart scenarios pass
- [ ] Contract tests validate method signatures and return types
- [ ] Integration with existing TAB services works seamlessly
- [ ] Performance meets <100ms target for context retrieval
- [ ] Convergence analysis provides useful insights for conversation management