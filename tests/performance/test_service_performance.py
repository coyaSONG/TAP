"""Performance tests for service integration overhead.

Tests that service layer integration meets the <50ms overhead requirement
for critical operations and doesn't introduce performance regressions.
"""

import pytest
import asyncio
import time
import statistics
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock

from src.tab.lib.config import TABConfig
from src.tab.services.session_manager import SessionManager
from src.tab.services.policy_enforcer import PolicyEnforcer
from src.tab.services.conversation_orchestrator import ConversationOrchestrator
from src.tab.models.conversation_session import ConversationSession
from src.tab.models.turn_message import TurnMessage, MessageRole


class PerformanceTestHelper:
    """Helper class for performance measurements."""

    @staticmethod
    async def measure_operation(operation, iterations: int = 10) -> Dict[str, float]:
        """Measure operation performance over multiple iterations."""
        times = []

        for _ in range(iterations):
            start_time = time.perf_counter()
            await operation()
            end_time = time.perf_counter()
            times.append((end_time - start_time) * 1000)  # Convert to milliseconds

        return {
            "avg_ms": statistics.mean(times),
            "min_ms": min(times),
            "max_ms": max(times),
            "median_ms": statistics.median(times),
            "p95_ms": sorted(times)[int(0.95 * len(times))],
            "iterations": iterations
        }

    @staticmethod
    def assert_performance_target(metrics: Dict[str, float], target_ms: float, operation_name: str):
        """Assert that performance metrics meet target."""
        avg_time = metrics["avg_ms"]
        p95_time = metrics["p95_ms"]

        assert avg_time < target_ms, (
            f"{operation_name} average time {avg_time:.2f}ms exceeds target {target_ms}ms"
        )

        assert p95_time < target_ms * 1.5, (
            f"{operation_name} P95 time {p95_time:.2f}ms exceeds relaxed target {target_ms * 1.5}ms"
        )

        print(f"✅ {operation_name}: avg={avg_time:.2f}ms, p95={p95_time:.2f}ms (target: <{target_ms}ms)")


@pytest.mark.performance
class TestServiceConstructorPerformance:
    """Test performance of enhanced service constructors."""

    @pytest.mark.asyncio
    async def test_session_manager_constructor_performance(self):
        """Test SessionManager constructor performance with dependency injection."""
        config = TABConfig()

        async def create_session_manager():
            return SessionManager(config.session)

        metrics = await PerformanceTestHelper.measure_operation(
            create_session_manager, iterations=20
        )

        # Constructor should be very fast
        PerformanceTestHelper.assert_performance_target(
            metrics, 10.0, "SessionManager constructor"
        )

    @pytest.mark.asyncio
    async def test_policy_enforcer_constructor_performance(self):
        """Test PolicyEnforcer constructor performance with dependency injection."""
        config = TABConfig()

        async def create_policy_enforcer():
            return PolicyEnforcer(config.policies)

        metrics = await PerformanceTestHelper.measure_operation(
            create_policy_enforcer, iterations=20
        )

        # Constructor should be very fast
        PerformanceTestHelper.assert_performance_target(
            metrics, 10.0, "PolicyEnforcer constructor"
        )

    @pytest.mark.asyncio
    async def test_orchestrator_constructor_performance(self):
        """Test ConversationOrchestrator constructor performance with dependency injection."""
        config = TABConfig()
        session_manager = SessionManager(config.session)
        policy_enforcer = PolicyEnforcer(config.policies)

        async def create_orchestrator():
            return ConversationOrchestrator(
                session_manager=session_manager,
                policy_enforcer=policy_enforcer,
                agent_configs=config.agents
            )

        metrics = await PerformanceTestHelper.measure_operation(
            create_orchestrator, iterations=20
        )

        # Constructor should be fast
        PerformanceTestHelper.assert_performance_target(
            metrics, 15.0, "ConversationOrchestrator constructor"
        )

    @pytest.mark.asyncio
    async def test_full_service_initialization_performance(self):
        """Test complete service initialization chain performance."""
        async def initialize_all_services():
            config = TABConfig()

            # Create all services
            session_manager = SessionManager(config.session)
            policy_enforcer = PolicyEnforcer(config.policies)
            orchestrator = ConversationOrchestrator(
                session_manager=session_manager,
                policy_enforcer=policy_enforcer,
                agent_configs=config.agents
            )

            # Initialize services
            await session_manager.initialize()
            await orchestrator.initialize()

            # Cleanup
            await orchestrator.shutdown()
            await session_manager.shutdown()

        metrics = await PerformanceTestHelper.measure_operation(
            initialize_all_services, iterations=5
        )

        # Full initialization should complete quickly
        PerformanceTestHelper.assert_performance_target(
            metrics, 100.0, "Full service initialization"
        )


@pytest.mark.performance
class TestMissingMethodsPerformance:
    """Test performance of implemented missing methods."""

    def setup_method(self):
        """Set up test session with content."""
        self.session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Performance test session"
        )

        # Add multiple turns for realistic testing
        for i in range(10):
            turn = TurnMessage(
                session_id=self.session.session_id,
                from_agent="claude_code" if i % 2 == 0 else "codex_cli",
                to_agent="codex_cli" if i % 2 == 0 else "claude_code",
                role=MessageRole.ASSISTANT if i % 2 == 0 else MessageRole.USER,
                content=f"Performance test message {i+1} with enough content to be realistic for testing purposes and measure actual performance impact."
            )
            self.session.add_turn_message(turn)

    @pytest.mark.asyncio
    async def test_should_auto_complete_performance(self):
        """Test should_auto_complete() method performance."""
        async def call_should_auto_complete():
            return self.session.should_auto_complete()

        metrics = await PerformanceTestHelper.measure_operation(
            call_should_auto_complete, iterations=50
        )

        # Should be very fast
        PerformanceTestHelper.assert_performance_target(
            metrics, 5.0, "should_auto_complete()"
        )

    @pytest.mark.asyncio
    async def test_get_summary_stats_performance(self):
        """Test get_summary_stats() method performance."""
        async def call_get_summary_stats():
            return self.session.get_summary_stats()

        metrics = await PerformanceTestHelper.measure_operation(
            call_get_summary_stats, iterations=50
        )

        # Should be fast
        PerformanceTestHelper.assert_performance_target(
            metrics, 10.0, "get_summary_stats()"
        )

    @pytest.mark.asyncio
    async def test_get_session_status_performance(self):
        """Test get_session_status() method performance."""
        async def call_get_session_status():
            return self.session.get_session_status()

        metrics = await PerformanceTestHelper.measure_operation(
            call_get_session_status, iterations=50
        )

        # Should be fast
        PerformanceTestHelper.assert_performance_target(
            metrics, 10.0, "get_session_status()"
        )

    @pytest.mark.asyncio
    async def test_all_missing_methods_combined_performance(self):
        """Test performance of calling all missing methods together."""
        async def call_all_missing_methods():
            auto_complete = self.session.should_auto_complete()
            stats = self.session.get_summary_stats()
            status = self.session.get_session_status()
            return auto_complete, stats, status

        metrics = await PerformanceTestHelper.measure_operation(
            call_all_missing_methods, iterations=30
        )

        # Combined should still be fast
        PerformanceTestHelper.assert_performance_target(
            metrics, 25.0, "All missing methods combined"
        )


@pytest.mark.performance
class TestUnifiedAPIPerformance:
    """Test performance of unified API methods."""

    @pytest.mark.asyncio
    async def test_get_conversation_context_performance(self):
        """Test get_conversation_context() method performance."""
        # Setup mocked dependencies
        session_manager = Mock()
        session_manager.get_session = AsyncMock()

        mock_session = Mock()
        mock_session.get_conversation_context = Mock(return_value=[
            {"role": "assistant", "content": f"Message {i}", "from_agent": "claude_code"}
            for i in range(10)
        ])
        session_manager.get_session.return_value = mock_session

        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=Mock(),
            agent_configs={"claude_code": {"agent_id": "claude_code"}}
        )

        await orchestrator.initialize()

        async def call_get_conversation_context():
            return await orchestrator.get_conversation_context(
                session_id="test-session",
                limit=10
            )

        metrics = await PerformanceTestHelper.measure_operation(
            call_get_conversation_context, iterations=50
        )

        # Should meet the 50ms target
        PerformanceTestHelper.assert_performance_target(
            metrics, 50.0, "get_conversation_context()"
        )

        await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_process_turn_performance(self):
        """Test process_turn() method performance."""
        # Setup mocked dependencies
        session_manager = Mock()
        session_manager.get_session = AsyncMock()
        session_manager.update_session = AsyncMock()

        mock_session = Mock()
        mock_session.add_turn_message = Mock(return_value=True)
        session_manager.get_session.return_value = mock_session

        policy_enforcer = Mock()
        policy_enforcer.validate_turn_addition = Mock(return_value={
            "allowed": True,
            "violations": []
        })

        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=policy_enforcer,
            agent_configs={"claude_code": {"agent_id": "claude_code"}}
        )

        await orchestrator.initialize()

        async def call_process_turn():
            return await orchestrator.process_turn(
                session_id="test-session",
                content="Test message for performance",
                from_agent="claude_code",
                to_agent="codex_cli"
            )

        metrics = await PerformanceTestHelper.measure_operation(
            call_process_turn, iterations=30
        )

        # Should meet the 50ms target
        PerformanceTestHelper.assert_performance_target(
            metrics, 50.0, "process_turn()"
        )

        await orchestrator.shutdown()


@pytest.mark.performance
class TestConcurrentOperationPerformance:
    """Test performance under concurrent load."""

    @pytest.mark.asyncio
    async def test_concurrent_session_creation_performance(self):
        """Test performance of concurrent session creation."""
        config = TABConfig()
        session_manager = SessionManager(config.session)
        await session_manager.initialize()

        async def create_session():
            return await session_manager.create_session(
                topic="Concurrent test session",
                participants=["claude_code", "codex_cli"]
            )

        # Measure concurrent session creation
        start_time = time.perf_counter()

        # Create 10 sessions concurrently
        tasks = [create_session() for _ in range(10)]
        sessions = await asyncio.gather(*tasks)

        end_time = time.perf_counter()
        total_time = (end_time - start_time) * 1000

        # All sessions should be created
        assert len(sessions) == 10
        assert all(session is not None for session in sessions)

        # Average per session should be well under 50ms
        avg_time_per_session = total_time / 10
        assert avg_time_per_session < 50.0, (
            f"Concurrent session creation average {avg_time_per_session:.2f}ms exceeds 50ms target"
        )

        print(f"✅ Concurrent session creation: {avg_time_per_session:.2f}ms per session (target: <50ms)")

        await session_manager.shutdown()

    @pytest.mark.asyncio
    async def test_concurrent_missing_methods_performance(self):
        """Test performance of missing methods under concurrent access."""
        session = ConversationSession(
            participants=["claude_code", "codex_cli"],
            topic="Concurrent missing methods test"
        )

        # Add some content
        for i in range(5):
            turn = TurnMessage(
                session_id=session.session_id,
                from_agent="claude_code" if i % 2 == 0 else "codex_cli",
                to_agent="codex_cli" if i % 2 == 0 else "claude_code",
                role=MessageRole.ASSISTANT if i % 2 == 0 else MessageRole.USER,
                content=f"Concurrent test message {i+1}"
            )
            session.add_turn_message(turn)

        async def call_missing_methods():
            # Call all missing methods concurrently
            auto_complete_task = asyncio.create_task(
                asyncio.to_thread(session.should_auto_complete)
            )
            stats_task = asyncio.create_task(
                asyncio.to_thread(session.get_summary_stats)
            )
            status_task = asyncio.create_task(
                asyncio.to_thread(session.get_session_status)
            )

            return await asyncio.gather(auto_complete_task, stats_task, status_task)

        start_time = time.perf_counter()

        # Run multiple concurrent calls
        tasks = [call_missing_methods() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        end_time = time.perf_counter()
        total_time = (end_time - start_time) * 1000

        # All calls should succeed
        assert len(results) == 5
        assert all(len(result) == 3 for result in results)

        # Average time should be reasonable
        avg_time = total_time / 5
        assert avg_time < 100.0, (
            f"Concurrent missing methods average {avg_time:.2f}ms exceeds 100ms target"
        )

        print(f"✅ Concurrent missing methods: {avg_time:.2f}ms per batch (target: <100ms)")


@pytest.mark.performance
class TestMemoryPerformance:
    """Test memory usage of service integration."""

    @pytest.mark.asyncio
    async def test_service_memory_usage(self):
        """Test that service creation doesn't use excessive memory."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        config = TABConfig()

        # Create multiple service instances
        services = []
        for i in range(10):
            session_manager = SessionManager(config.session)
            policy_enforcer = PolicyEnforcer(config.policies)
            orchestrator = ConversationOrchestrator(
                session_manager=session_manager,
                policy_enforcer=policy_enforcer,
                agent_configs=config.agents
            )
            services.append((session_manager, policy_enforcer, orchestrator))

        # Initialize all services
        for session_manager, _, orchestrator in services:
            await session_manager.initialize()
            await orchestrator.initialize()

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 100MB for 10 service sets)
        assert memory_increase < 100.0, (
            f"Memory increase {memory_increase:.2f}MB exceeds 100MB limit"
        )

        print(f"✅ Service memory usage: {memory_increase:.2f}MB for 10 service sets")

        # Cleanup
        for session_manager, _, orchestrator in services:
            await orchestrator.shutdown()
            await session_manager.shutdown()


if __name__ == "__main__":
    # Allow running performance tests directly
    pytest.main([__file__, "-v", "-m", "performance"])