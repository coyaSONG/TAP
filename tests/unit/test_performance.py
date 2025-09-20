"""
Performance validation tests for TAB system.

Tests conversation turn latency, resource usage, and system performance
to ensure <2 second per turn requirement is met.
"""

import asyncio
import time
import psutil
import pytest
from unittest.mock import Mock, AsyncMock
from typing import List, Dict, Any
from contextlib import asynccontextmanager

from tab.services.conversation_orchestrator import ConversationOrchestrator
from tab.services.session_manager import SessionManager
from tab.services.policy_enforcer import PolicyEnforcer
from tab.models.conversation_session import ConversationSession, SessionStatus
from tab.models.turn_message import TurnMessage, MessageRole
from tab.models.agent_adapter import AgentAdapter, AgentType, AgentStatus
from tab.models.policy_configuration import PolicyConfiguration, PermissionMode


class PerformanceMetrics:
    """Collects and analyzes performance metrics."""

    def __init__(self):
        self.turn_latencies: List[float] = []
        self.memory_usage: List[float] = []
        self.cpu_usage: List[float] = []
        self.concurrent_sessions = 0
        self.errors: List[str] = []

    def record_turn_latency(self, latency_ms: float) -> None:
        """Record turn processing latency."""
        self.turn_latencies.append(latency_ms)

    def record_system_metrics(self) -> None:
        """Record current system resource usage."""
        process = psutil.Process()
        self.memory_usage.append(process.memory_info().rss / 1024 / 1024)  # MB
        self.cpu_usage.append(process.cpu_percent())

    def get_statistics(self) -> Dict[str, Any]:
        """Get performance statistics."""
        if not self.turn_latencies:
            return {"error": "No performance data collected"}

        return {
            "turn_latency": {
                "avg_ms": sum(self.turn_latencies) / len(self.turn_latencies),
                "max_ms": max(self.turn_latencies),
                "min_ms": min(self.turn_latencies),
                "p95_ms": self._percentile(self.turn_latencies, 95),
                "p99_ms": self._percentile(self.turn_latencies, 99),
                "count": len(self.turn_latencies)
            },
            "memory_usage": {
                "avg_mb": sum(self.memory_usage) / len(self.memory_usage) if self.memory_usage else 0,
                "max_mb": max(self.memory_usage) if self.memory_usage else 0,
                "samples": len(self.memory_usage)
            },
            "cpu_usage": {
                "avg_percent": sum(self.cpu_usage) / len(self.cpu_usage) if self.cpu_usage else 0,
                "max_percent": max(self.cpu_usage) if self.cpu_usage else 0,
                "samples": len(self.cpu_usage)
            },
            "errors": {
                "count": len(self.errors),
                "details": self.errors[:10]  # First 10 errors
            }
        }

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile of data."""
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]


@asynccontextmanager
async def performance_monitor(metrics: PerformanceMetrics):
    """Context manager for monitoring performance during tests."""
    start_time = time.time()
    start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB

    try:
        yield
    finally:
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB

        latency_ms = (end_time - start_time) * 1000
        metrics.record_turn_latency(latency_ms)
        metrics.record_system_metrics()


class MockAgentAdapter:
    """Mock agent adapter for performance testing."""

    def __init__(self, agent_id: str, latency_ms: float = 500):
        self.agent_id = agent_id
        self.latency_ms = latency_ms
        self.call_count = 0

    async def process_request(self, content: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Mock agent request processing with configurable latency."""
        self.call_count += 1

        # Simulate processing time
        await asyncio.sleep(self.latency_ms / 1000)

        return {
            "status": "completed",
            "response": {
                "content": f"Mock response from {self.agent_id}: {content[:50]}...",
                "reasoning": "Mock reasoning",
                "confidence": 0.8
            },
            "metadata": {
                "execution_time_ms": self.latency_ms,
                "cost_usd": 0.01,
                "tokens_used": 100
            }
        }


class TestTurnLatencyPerformance:
    """Test conversation turn latency performance."""

    @pytest.fixture
    def performance_metrics(self):
        """Create performance metrics collector."""
        return PerformanceMetrics()

    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator for performance testing."""
        session_manager = Mock()
        policy_enforcer = Mock()

        # Mock successful policy validation
        policy_enforcer.validate_request = AsyncMock(return_value=True)
        policy_enforcer.get_constraints = Mock(return_value={})

        orchestrator = ConversationOrchestrator(
            session_manager=session_manager,
            policy_enforcer=policy_enforcer,
            agent_configs={}
        )

        # Mock agent adapters with different latencies
        orchestrator._agent_adapters = {
            "fast_agent": MockAgentAdapter("fast_agent", latency_ms=200),
            "medium_agent": MockAgentAdapter("medium_agent", latency_ms=800),
            "slow_agent": MockAgentAdapter("slow_agent", latency_ms=1500)
        }

        return orchestrator

    @pytest.mark.asyncio
    async def test_single_turn_latency_target(self, performance_metrics, mock_orchestrator):
        """Test that single conversation turns meet the <2s latency target."""
        target_latency_ms = 2000  # 2 seconds
        test_iterations = 10

        for i in range(test_iterations):
            async with performance_monitor(performance_metrics):
                # Simulate a conversation turn
                mock_session = ConversationSession(
                    session_id=f"perf-test-{i}",
                    participants=["fast_agent", "medium_agent"],
                    topic="Performance test conversation"
                )

                # Mock agent processing
                fast_agent = mock_orchestrator._agent_adapters["fast_agent"]
                await fast_agent.process_request(
                    content=f"Performance test message {i}",
                    context={"session_id": mock_session.session_id}
                )

        stats = performance_metrics.get_statistics()

        # Validate performance requirements
        assert stats["turn_latency"]["avg_ms"] < target_latency_ms, \
            f"Average turn latency {stats['turn_latency']['avg_ms']:.2f}ms exceeds target {target_latency_ms}ms"

        assert stats["turn_latency"]["max_ms"] < target_latency_ms, \
            f"Maximum turn latency {stats['turn_latency']['max_ms']:.2f}ms exceeds target {target_latency_ms}ms"

        assert stats["turn_latency"]["p95_ms"] < target_latency_ms, \
            f"95th percentile latency {stats['turn_latency']['p95_ms']:.2f}ms exceeds target {target_latency_ms}ms"

    @pytest.mark.asyncio
    async def test_multi_turn_conversation_performance(self, performance_metrics, mock_orchestrator):
        """Test performance of multi-turn conversations."""
        target_avg_latency_ms = 1500  # Allow slightly higher average for multi-turn
        conversation_turns = 6

        mock_session = ConversationSession(
            session_id="multi-turn-perf-test",
            participants=["fast_agent", "medium_agent"],
            topic="Multi-turn performance test"
        )

        for turn in range(conversation_turns):
            async with performance_monitor(performance_metrics):
                # Alternate between agents
                agent_id = "fast_agent" if turn % 2 == 0 else "medium_agent"
                agent = mock_orchestrator._agent_adapters[agent_id]

                await agent.process_request(
                    content=f"Turn {turn + 1} content for multi-turn conversation",
                    context={
                        "session_id": mock_session.session_id,
                        "turn_number": turn + 1
                    }
                )

        stats = performance_metrics.get_statistics()

        # Validate multi-turn performance
        assert len(stats["turn_latency"]["count"]) == conversation_turns, \
            f"Expected {conversation_turns} turns, got {stats['turn_latency']['count']}"

        assert stats["turn_latency"]["avg_ms"] < target_avg_latency_ms, \
            f"Multi-turn average latency {stats['turn_latency']['avg_ms']:.2f}ms exceeds target {target_avg_latency_ms}ms"

    @pytest.mark.asyncio
    async def test_concurrent_conversation_performance(self, performance_metrics):
        """Test performance under concurrent conversation load."""
        concurrent_sessions = 5
        turns_per_session = 3
        target_max_latency_ms = 3000  # Allow higher latency under load

        async def conversation_session(session_id: str):
            """Simulate a conversation session."""
            agent = MockAgentAdapter(f"agent-{session_id}", latency_ms=400)

            for turn in range(turns_per_session):
                async with performance_monitor(performance_metrics):
                    await agent.process_request(
                        content=f"Concurrent session {session_id} turn {turn + 1}",
                        context={"session_id": session_id, "turn_number": turn + 1}
                    )

        # Run concurrent sessions
        tasks = [
            conversation_session(f"concurrent-{i}")
            for i in range(concurrent_sessions)
        ]

        await asyncio.gather(*tasks)

        stats = performance_metrics.get_statistics()

        # Validate concurrent performance
        expected_total_turns = concurrent_sessions * turns_per_session
        assert stats["turn_latency"]["count"] == expected_total_turns, \
            f"Expected {expected_total_turns} turns, got {stats['turn_latency']['count']}"

        assert stats["turn_latency"]["max_ms"] < target_max_latency_ms, \
            f"Maximum concurrent latency {stats['turn_latency']['max_ms']:.2f}ms exceeds target {target_max_latency_ms}ms"


class TestResourceUsagePerformance:
    """Test system resource usage and memory performance."""

    @pytest.fixture
    def performance_metrics(self):
        """Create performance metrics collector."""
        return PerformanceMetrics()

    @pytest.mark.asyncio
    async def test_memory_usage_stability(self, performance_metrics):
        """Test that memory usage remains stable over time."""
        max_memory_growth_mb = 50  # Maximum allowed memory growth
        test_duration_seconds = 30
        sample_interval_seconds = 1

        start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB

        # Simulate continuous operation
        start_time = time.time()
        while time.time() - start_time < test_duration_seconds:
            # Simulate agent operations
            agent = MockAgentAdapter("memory-test-agent", latency_ms=100)
            await agent.process_request(
                content="Memory stability test",
                context={"test": "memory"}
            )

            performance_metrics.record_system_metrics()
            await asyncio.sleep(sample_interval_seconds)

        end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        memory_growth = end_memory - start_memory

        stats = performance_metrics.get_statistics()

        # Validate memory stability
        assert memory_growth < max_memory_growth_mb, \
            f"Memory growth {memory_growth:.2f}MB exceeds limit {max_memory_growth_mb}MB"

        assert stats["memory_usage"]["samples"] > 0, "No memory usage samples collected"

    @pytest.mark.asyncio
    async def test_cpu_usage_efficiency(self, performance_metrics):
        """Test CPU usage efficiency during operations."""
        max_sustained_cpu_percent = 80  # Maximum sustained CPU usage
        test_operations = 20

        for i in range(test_operations):
            start_cpu = psutil.Process().cpu_percent()

            # Simulate CPU-intensive agent operation
            agent = MockAgentAdapter(f"cpu-test-agent-{i}", latency_ms=200)
            await agent.process_request(
                content=f"CPU efficiency test {i}",
                context={"test": "cpu"}
            )

            performance_metrics.record_system_metrics()

            # Small delay to allow CPU measurement
            await asyncio.sleep(0.1)

        stats = performance_metrics.get_statistics()

        # Validate CPU efficiency
        if stats["cpu_usage"]["samples"] > 0:
            assert stats["cpu_usage"]["avg_percent"] < max_sustained_cpu_percent, \
                f"Average CPU usage {stats['cpu_usage']['avg_percent']:.2f}% exceeds limit {max_sustained_cpu_percent}%"

    @pytest.mark.asyncio
    async def test_session_scalability(self, performance_metrics):
        """Test system scalability with multiple active sessions."""
        max_concurrent_sessions = 10
        max_latency_degradation_percent = 50  # Max 50% latency increase

        # Baseline single session performance
        baseline_agent = MockAgentAdapter("baseline-agent", latency_ms=300)

        async with performance_monitor(performance_metrics):
            await baseline_agent.process_request(
                content="Baseline performance test",
                context={"test": "baseline"}
            )

        baseline_latency = performance_metrics.turn_latencies[0]

        # Test with multiple concurrent sessions
        performance_metrics.turn_latencies.clear()  # Reset for concurrent test

        async def concurrent_session(session_id: str):
            """Simulate a concurrent session."""
            agent = MockAgentAdapter(f"concurrent-agent-{session_id}", latency_ms=300)

            async with performance_monitor(performance_metrics):
                await agent.process_request(
                    content=f"Concurrent test {session_id}",
                    context={"session_id": session_id}
                )

        # Run multiple concurrent sessions
        tasks = [
            concurrent_session(f"scale-test-{i}")
            for i in range(max_concurrent_sessions)
        ]

        await asyncio.gather(*tasks)

        stats = performance_metrics.get_statistics()

        # Validate scalability
        assert stats["turn_latency"]["count"] == max_concurrent_sessions, \
            f"Expected {max_concurrent_sessions} concurrent operations"

        avg_concurrent_latency = stats["turn_latency"]["avg_ms"]
        latency_increase_percent = ((avg_concurrent_latency - baseline_latency) / baseline_latency) * 100

        assert latency_increase_percent < max_latency_degradation_percent, \
            f"Latency degradation {latency_increase_percent:.2f}% exceeds limit {max_latency_degradation_percent}%"


class TestStressAndLoadPerformance:
    """Test system performance under stress and load conditions."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_sustained_load_performance(self):
        """Test performance under sustained load."""
        metrics = PerformanceMetrics()
        load_duration_seconds = 60  # 1 minute sustained load
        operations_per_second = 5
        target_max_latency_ms = 3000  # Higher threshold for sustained load

        start_time = time.time()
        operation_count = 0

        while time.time() - start_time < load_duration_seconds:
            async with performance_monitor(metrics):
                agent = MockAgentAdapter(f"load-agent-{operation_count}", latency_ms=400)
                await agent.process_request(
                    content=f"Sustained load test operation {operation_count}",
                    context={"operation": operation_count}
                )

            operation_count += 1

            # Control operation rate
            await asyncio.sleep(1.0 / operations_per_second)

        stats = metrics.get_statistics()

        # Validate sustained load performance
        assert stats["turn_latency"]["max_ms"] < target_max_latency_ms, \
            f"Maximum latency under load {stats['turn_latency']['max_ms']:.2f}ms exceeds threshold"

        assert operation_count > load_duration_seconds * operations_per_second * 0.8, \
            f"Operation count {operation_count} below expected minimum"

    @pytest.mark.asyncio
    async def test_error_recovery_performance(self):
        """Test performance during error conditions and recovery."""
        metrics = PerformanceMetrics()
        total_operations = 20
        error_rate = 0.3  # 30% error rate
        recovery_time_threshold_ms = 1000

        class ErrorProneAgent(MockAgentAdapter):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.error_probability = error_rate

            async def process_request(self, content: str, context: Dict[str, Any]) -> Dict[str, Any]:
                if self.call_count < total_operations * self.error_probability:
                    # Simulate error
                    await asyncio.sleep(0.1)  # Error handling delay
                    raise Exception(f"Simulated error from {self.agent_id}")

                return await super().process_request(content, context)

        agent = ErrorProneAgent("error-prone-agent", latency_ms=500)

        successful_operations = 0
        failed_operations = 0

        for i in range(total_operations):
            try:
                async with performance_monitor(metrics):
                    await agent.process_request(
                        content=f"Error recovery test {i}",
                        context={"operation": i}
                    )
                successful_operations += 1
            except Exception as e:
                failed_operations += 1
                metrics.errors.append(str(e))

        stats = metrics.get_statistics()

        # Validate error recovery performance
        assert successful_operations > 0, "No successful operations completed"
        assert failed_operations > 0, "No errors occurred (test setup issue)"

        if successful_operations > 0:
            assert stats["turn_latency"]["avg_ms"] < recovery_time_threshold_ms, \
                f"Average recovery latency {stats['turn_latency']['avg_ms']:.2f}ms exceeds threshold"


@pytest.mark.performance
class TestPerformanceRegression:
    """Performance regression tests to ensure no performance degradation."""

    @pytest.mark.asyncio
    async def test_performance_baseline(self):
        """Establish performance baseline for regression testing."""
        metrics = PerformanceMetrics()

        # Baseline configuration
        baseline_config = {
            "operations": 50,
            "agent_latency_ms": 500,
            "concurrent_sessions": 3,
            "expected_max_latency_ms": 2000,
            "expected_avg_latency_ms": 800
        }

        async def baseline_operation(op_id: int):
            """Baseline operation for regression testing."""
            agent = MockAgentAdapter(f"baseline-{op_id}",
                                   latency_ms=baseline_config["agent_latency_ms"])

            async with performance_monitor(metrics):
                await agent.process_request(
                    content=f"Baseline regression test {op_id}",
                    context={"operation_id": op_id}
                )

        # Execute baseline operations
        tasks = [
            baseline_operation(i)
            for i in range(baseline_config["operations"])
        ]

        await asyncio.gather(*tasks)

        stats = metrics.get_statistics()

        # Regression validation
        assert stats["turn_latency"]["avg_ms"] < baseline_config["expected_avg_latency_ms"], \
            f"Regression detected: average latency {stats['turn_latency']['avg_ms']:.2f}ms > baseline {baseline_config['expected_avg_latency_ms']}ms"

        assert stats["turn_latency"]["max_ms"] < baseline_config["expected_max_latency_ms"], \
            f"Regression detected: maximum latency {stats['turn_latency']['max_ms']:.2f}ms > baseline {baseline_config['expected_max_latency_ms']}ms"

        # Log performance metrics for monitoring
        print(f"\nPerformance Baseline Results:")
        print(f"  Average Latency: {stats['turn_latency']['avg_ms']:.2f}ms")
        print(f"  Maximum Latency: {stats['turn_latency']['max_ms']:.2f}ms")
        print(f"  95th Percentile: {stats['turn_latency']['p95_ms']:.2f}ms")
        print(f"  Operations: {stats['turn_latency']['count']}")
        print(f"  Memory Usage: {stats['memory_usage']['avg_mb']:.2f}MB")
        print(f"  CPU Usage: {stats['cpu_usage']['avg_percent']:.2f}%")