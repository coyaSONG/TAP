# Quickstart: TAP Agent Dialog Integration

**Feature**: Service layer integration for real multi-agent conversations
**Time to complete**: 15-20 minutes

## Prerequisites

- Existing TAP development environment
- Python 3.11+ with asyncio support
- All TAP dependencies installed (`uv sync`)
- Access to TAP configuration files

## Quick Test Scenarios

### Scenario 1: Service Constructor Integration

Test that services can be properly instantiated with configuration objects:

```python
import asyncio
from src.tab.lib.config import initialize_config, get_config
from src.tab.services.session_manager import SessionManager
from src.tab.services.policy_enforcer import PolicyEnforcer
from src.tab.services.conversation_orchestrator import ConversationOrchestrator

async def test_service_constructors():
    """Test enhanced service constructors with dependency injection."""

    # Load configuration
    config = get_config()

    # Test SessionManager with config
    session_manager = SessionManager(config.session.dict())
    await session_manager.initialize()

    # Test PolicyEnforcer with config
    policy_enforcer = PolicyEnforcer({"default": config.policies.get("default", {})})

    # Test ConversationOrchestrator with dependencies
    orchestrator = ConversationOrchestrator(
        session_manager=session_manager,
        policy_enforcer=policy_enforcer,
        agent_configs=config.agents
    )
    await orchestrator.initialize()

    print("✅ All services instantiated successfully with dependency injection")

    # Cleanup
    await orchestrator.shutdown()
    await session_manager.shutdown()

if __name__ == "__main__":
    asyncio.run(test_service_constructors())
```

### Scenario 2: Unified API Parameters

Test that API parameter names are unified across service interfaces:

```python
async def test_unified_api_parameters():
    """Test unified parameter naming (max_turns → limit)."""

    config = get_config()

    # Initialize services
    session_manager = SessionManager(config.session.dict())
    policy_enforcer = PolicyEnforcer({"default": config.policies.get("default", {})})
    orchestrator = ConversationOrchestrator(
        session_manager=session_manager,
        policy_enforcer=policy_enforcer,
        agent_configs=config.agents
    )

    await session_manager.initialize()
    await orchestrator.initialize()

    # Create test session
    session = await session_manager.create_session(
        topic="Test unified API parameters",
        participants=["claude_code", "codex_cli"]
    )

    # Test unified parameter name (limit instead of max_turns)
    context = await orchestrator.get_conversation_context(
        session_id=session.session_id,
        agent_filter="claude_code",
        limit=3  # This should work (was max_turns before)
    )

    assert isinstance(context, list)
    print("✅ Unified API parameters working correctly")

    # Cleanup
    await orchestrator.shutdown()
    await session_manager.shutdown()

if __name__ == "__main__":
    asyncio.run(test_unified_api_parameters())
```

### Scenario 3: Missing Methods Implementation

Test that missing ConversationSession methods are implemented:

```python
from src.tab.models.conversation_session import ConversationSession
from src.tab.models.turn_message import TurnMessage, MessageRole

async def test_missing_methods():
    """Test implementation of missing ConversationSession methods."""

    # Create test session
    session = ConversationSession(
        participants=["claude_code", "codex_cli"],
        topic="Test missing methods implementation"
    )

    # Add some test turns
    for i in range(3):
        turn = TurnMessage(
            session_id=session.session_id,
            from_agent="claude_code" if i % 2 == 0 else "codex_cli",
            to_agent="codex_cli" if i % 2 == 0 else "claude_code",
            role=MessageRole.ASSISTANT if i % 2 == 0 else MessageRole.USER,
            content=f"Test message {i+1} for missing methods validation"
        )
        session.add_turn_message(turn)

    # Test should_auto_complete method
    try:
        should_complete = session.should_auto_complete()
        assert isinstance(should_complete, bool)
        print("✅ should_auto_complete() method working")
    except AttributeError:
        print("❌ should_auto_complete() method missing")
        return False

    # Test get_summary_stats method
    try:
        stats = session.get_summary_stats()
        assert isinstance(stats, dict)
        assert "total_turns" in stats
        assert "participants_activity" in stats
        print("✅ get_summary_stats() method working")
    except AttributeError:
        print("❌ get_summary_stats() method missing")
        return False

    # Test get_session_status method
    try:
        status = session.get_session_status()
        assert isinstance(status, dict)
        assert "status" in status
        assert "turn_progress" in status
        print("✅ get_session_status() method working")
    except AttributeError:
        print("❌ get_session_status() method missing")
        return False

    print("✅ All missing methods implemented correctly")
    return True

if __name__ == "__main__":
    asyncio.run(test_missing_methods())
```

### Scenario 4: Dynamic Agent Configuration

Test that agent configuration supports dynamic loading:

```python
async def test_dynamic_agent_configuration():
    """Test dynamic agent configuration loading."""

    # Test configuration with dynamic agent
    dynamic_config = {
        "custom_agent": {
            "agent_id": "custom_agent",
            "agent_type": "custom_llm",  # Not limited to enum values
            "name": "Custom LLM Agent",
            "version": "1.0.0",
            "enabled": True,
            "loading_strategy": "builtin",  # For testing, use builtin fallback
            "static_capabilities": ["text_generation"],
            "capability_discovery": True,
            "connection_config": {
                "connection_timeout": 120,
                "max_retries": 3
            },
            "execution_limits": {
                "max_execution_time_ms": 180000
            }
        }
    }

    # Test that configuration validates
    from src.tab.models.agent_adapter import AgentAdapter

    try:
        agent_config = AgentAdapter(**dynamic_config["custom_agent"])
        print("✅ Dynamic agent configuration validates correctly")

        # Test that agent_type is not restricted to enum
        assert agent_config.agent_type == "custom_llm"
        print("✅ Agent type accepts custom values")

    except Exception as e:
        print(f"❌ Dynamic agent configuration failed: {e}")
        return False

    return True

if __name__ == "__main__":
    asyncio.run(test_dynamic_agent_configuration())
```

### Scenario 5: End-to-End Conversation Flow

Test complete conversation flow with enhanced service integration:

```python
async def test_end_to_end_conversation():
    """Test complete conversation flow with enhanced services."""

    config = get_config()

    # Initialize enhanced services
    session_manager = SessionManager(config.session.dict())
    policy_enforcer = PolicyEnforcer({"default": config.policies.get("default", {})})
    orchestrator = ConversationOrchestrator(
        session_manager=session_manager,
        policy_enforcer=policy_enforcer,
        agent_configs=config.agents
    )

    await session_manager.initialize()
    await orchestrator.initialize()

    try:
        # Start conversation
        conversation_response = await orchestrator.start_conversation(
            topic="Test end-to-end conversation flow",
            participants=["claude_code", "codex_cli"]
        )

        session_id = conversation_response["session_id"]
        print(f"✅ Conversation started with session ID: {session_id}")

        # Get session for validation
        session = await session_manager.get_session(session_id)
        assert session is not None
        print("✅ Session retrieved successfully")

        # Test context retrieval with unified parameters
        context = await orchestrator.get_conversation_context(
            session_id=session_id,
            limit=5
        )
        assert isinstance(context, list)
        print("✅ Context retrieval with unified parameters working")

        # Test convergence checking
        convergence = session.check_convergence_signals()
        assert isinstance(convergence, dict)
        assert "should_continue" in convergence
        print("✅ Convergence checking working")

        # Test auto-completion decision
        should_complete = session.should_auto_complete()
        assert isinstance(should_complete, bool)
        print("✅ Auto-completion decision working")

        print("✅ End-to-end conversation flow successful")

    finally:
        # Cleanup
        await orchestrator.shutdown()
        await session_manager.shutdown()

if __name__ == "__main__":
    asyncio.run(test_end_to_end_conversation())
```

## Expected Test Results

**All tests should pass** if the implementation is correct:

1. ✅ Service constructors accept configuration objects
2. ✅ API parameters are unified across interfaces (limit vs max_turns)
3. ✅ Missing ConversationSession methods are implemented
4. ✅ Dynamic agent configuration supports custom agent types
5. ✅ Complete conversation flow works end-to-end

## Validation Commands

Run these commands to validate the implementation:

```bash
# Test service integration
python -c "import asyncio; from quickstart_scenarios import test_service_constructors; asyncio.run(test_service_constructors())"

# Test API unification
python -c "import asyncio; from quickstart_scenarios import test_unified_api_parameters; asyncio.run(test_unified_api_parameters())"

# Test missing methods
python -c "import asyncio; from quickstart_scenarios import test_missing_methods; asyncio.run(test_missing_methods())"

# Test dynamic configuration
python -c "import asyncio; from quickstart_scenarios import test_dynamic_agent_configuration; asyncio.run(test_dynamic_agent_configuration())"

# Test complete flow
python -c "import asyncio; from quickstart_scenarios import test_end_to_end_conversation; asyncio.run(test_end_to_end_conversation())"

# Run existing TAP CLI to ensure no regressions
uv run python -m tab.cli.main start-conversation --topic "Integration test"
```

## Common Issues and Solutions

### Issue: Service constructor signature mismatch
**Solution**: Ensure service constructors accept configuration objects as specified in contracts

### Issue: AttributeError for missing methods
**Solution**: Implement `should_auto_complete()`, `get_summary_stats()`, and `get_session_status()` methods in ConversationSession

### Issue: API parameter conflicts (max_turns vs limit)
**Solution**: Unify parameter naming and provide backward compatibility adapters

### Issue: Agent type validation errors
**Solution**: Remove hardcoded agent type restrictions and support dynamic agent types

### Issue: Dependency injection failures
**Solution**: Verify service dependencies are properly registered and injected in correct order

## Performance Targets

- **Service startup**: <2 seconds for all services
- **Session creation**: <1 second
- **Context retrieval**: <100ms
- **Convergence analysis**: <500ms
- **Agent configuration validation**: <200ms

## Success Criteria

- [ ] All quickstart scenarios pass without errors
- [ ] Service constructors accept configuration objects
- [ ] API parameters are unified across all interfaces
- [ ] Missing methods are implemented and functional
- [ ] Dynamic agent configuration supports extensibility
- [ ] Complete conversation flow works end-to-end
- [ ] No regressions in existing TAP functionality
- [ ] Performance targets are met

## Next Steps

1. Implement the four core integration fixes identified in research
2. Add comprehensive contract tests for all service interfaces
3. Update existing TAB integration points to use unified APIs
4. Validate with real conversation scenarios using enhanced orchestration
5. Monitor performance and service health in development environment

This quickstart guide provides immediate validation that the service layer integration changes work correctly while maintaining backward compatibility with existing TAB functionality.