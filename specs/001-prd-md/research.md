# Technical Research: Twin-Agent Bridge (TAB)

**Date**: 2025-09-21
**Phase**: 0 - Research & Analysis
**Status**: Complete

## Research Summary

This document consolidates research findings on key technical decisions for implementing the TAB (Twin-Agent Bridge) system. All NEEDS CLARIFICATION items from the specification have been resolved with concrete technical recommendations.

---

## 1. MCP Integration Architecture

### Decision: Streamable HTTP for Production
**Rationale**: Streamable HTTP transport provides superior reliability (100% success rates vs STDIO performance bottlenecks), supports OAuth 2.0/2.1 authentication, and enables distributed deployments with session resumption capabilities.

**Implementation Framework**: FastMCP (official Python SDK)
- High-level abstraction for rapid development
- Built-in validation and error handling
- Support for both client and server implementations

**Fallback Strategy**: Multi-layer fallback (MCP → CLI wrapper → Direct API)
```
MCP Native → CLI Execution → Cached Response/Graceful Degradation
```

**Alternatives Considered**:
- STDIO transport: Limited to single-machine deployments, performance issues under load
- Custom protocol: Would require extensive development and testing

---

## 2. Claude Code Integration Pattern

### Decision: Headless Mode with Stream-JSON
**Rationale**: Claude Code's `--output-format stream-json` provides structured, parseable output ideal for orchestration systems. Session management via `--resume` enables conversation continuity.

**Command Pattern**:
```bash
claude -p "prompt" --output-format stream-json --resume session-id
```

**JSON Response Schema**:
```json
{
  "type": "result",
  "subtype": "success",
  "total_cost_usd": 0.003,
  "duration_ms": 1234,
  "session_id": "abc123",
  "result": "response content"
}
```

**Session Management**: Use `--resume session-id` for conversation continuity with automatic session tracking in the orchestrator.

**Alternatives Considered**:
- Plain text output: Difficult to parse, no metadata
- Interactive mode: Not suitable for automation

---

## 3. Codex CLI Integration Strategy

### Decision: CLI Execution with Session Log Parsing
**Rationale**: Codex CLI's `exec` mode provides non-interactive execution suitable for orchestration. Session logs in JSONL format provide conversation history and metadata.

**Execution Pattern**:
```bash
codex exec "prompt" --approval-mode auto
```

**Session Log Location**: `$CODEX_HOME/sessions/YYYY/MM/DD/rollout-*.jsonl`

**Workaround for Resume Limitation**: Orchestrator-level state management with context re-injection for conversation continuity.

**Alternatives Considered**:
- Proto mode: Insufficient documentation for reliable implementation
- Direct API: Limited availability and authentication complexity

---

## 4. Security Sandboxing Architecture

### Decision: Rootless Docker with Enhanced Container Isolation
**Rationale**: Rootless Docker provides superior security by eliminating root daemon vulnerabilities while maintaining container isolation. Enhanced Container Isolation (ECI) adds additional protection layers.

**Security Configuration**:
```bash
docker run --rm --cap-drop=ALL --pids-limit=256 --network=custom-bridge \
  --user 1000:1000 -v "$PWD:/work:ro" tab-runtime:latest
```

**File System Isolation**:
- Read-only workspace mounts
- Tmpfs with noexec, nosuid flags
- User namespace remapping

**Network Isolation**:
- Custom bridge networks for agent communication
- Internal networks with no external access
- mTLS for inter-agent communication

**Alternatives Considered**:
- Podman: Better security profile but less ecosystem support
- Firejail: Simpler but less comprehensive isolation
- Native OS sandboxing: Platform-specific limitations

---

## 5. Observability Implementation

### Decision: OpenTelemetry with Multi-Backend Export
**Rationale**: OpenTelemetry provides comprehensive observability with standardized APIs for traces, metrics, and logs. Multi-backend export enables flexibility in monitoring infrastructure.

**Tracing Architecture**:
- Conversation-level spans with nested agent turns
- Subprocess execution tracing for CLI integrations
- Distributed trace correlation across async operations

**Metrics Collection**:
- Real-time performance monitoring (response times, resource usage)
- Cost tracking and budget enforcement
- Conversation convergence analytics

**Structured Logging**:
- JSON-formatted audit trails
- Security event logging
- Correlation with trace and span IDs

**Export Targets**:
- OTLP for comprehensive telemetry
- Prometheus for metrics and alerting
- File-based logs for audit compliance

**Alternatives Considered**:
- Vendor-specific monitoring: Lock-in concerns
- Custom telemetry: Development overhead
- Basic logging only: Insufficient for production monitoring

---

## 6. Performance and Scalability

### Decision: Async Python with Connection Pooling
**Rationale**: Python 3.11+ asyncio provides excellent support for concurrent agent management. Connection pooling optimizes resource usage for multi-agent scenarios.

**Performance Targets**:
- <2 seconds per conversation turn
- Support for 4-6 turn conversations
- Concurrent execution of agent operations

**Resource Management**:
- Connection pools for MCP sessions
- Circuit breakers for fault tolerance
- Caching for repeated operations

**Scalability Approach**:
- Horizontal scaling via multiple orchestrator instances
- Load balancing across agent pools
- State persistence for conversation recovery

---

## 7. Error Handling and Resilience

### Decision: Three-Layer Error Handling with Circuit Breakers
**Rationale**: Comprehensive error handling at input validation, protocol, and application layers ensures robust operation. Circuit breakers prevent cascade failures.

**Error Layers**:
1. Input validation with Pydantic schemas
2. Protocol-level error handling (MCP, subprocess)
3. Application-level graceful degradation

**Circuit Breaker Pattern**:
- Failure threshold: 5 consecutive failures
- Timeout: 60 seconds before retry
- Half-open state for recovery testing

**Fallback Strategies**:
- Agent substitution for failed components
- Cached responses for network failures
- Graceful degradation with partial results

---

## 8. Constitutional Compliance Summary

All research findings align with TAB constitutional requirements:

- **Bridge-First Architecture** ✅: MCP standardization enables agent interoperability
- **Security by Default** ✅: Rootless containers with capability dropping
- **Observable Operations** ✅: Comprehensive OpenTelemetry integration
- **Protocol Compliance** ✅: MCP standards with graceful fallbacks
- **Fail-Safe Design** ✅: Circuit breakers and multi-layer error handling

---

## Next Steps

Research phase complete. Ready to proceed to Phase 1 (Design & Contracts) with:
1. Data model definition based on research findings
2. MCP contract specifications
3. Security policy implementations
4. Observability schema definitions

All technical uncertainties have been resolved and implementation patterns established.