# Tasks: Twin-Agent Bridge (TAB)

**Input**: Design documents from `/home/chsong/projects/TAP/specs/001-prd-md/`
**Prerequisites**: plan.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

## Execution Flow (main)
```
1. Load plan.md from feature directory ✓
   → Tech stack: Python 3.11+, asyncio, OpenTelemetry, Pydantic, pytest
   → Structure: Single project (src/, tests/)
2. Load design documents ✓:
   → data-model.md: 6 entities identified
   → contracts/: 2 MCP schemas (orchestrator, agent interface)
   → quickstart.md: 4 test scenarios identified
3. Generate tasks by category ✓:
   → Setup: project init, Python dependencies, Docker, linting
   → Tests: contract tests, integration tests (TDD approach)
   → Core: data models, agent adapters, orchestration services
   → Integration: MCP servers, CLI interface, observability
   → Polish: unit tests, performance validation, documentation
4. Applied task rules ✓:
   → Different files = [P] for parallel execution
   → Same file = sequential execution
   → Tests before implementation (TDD)
5. Tasks numbered T001-T036 with proper dependencies
6. Generated parallel execution examples
7. Validated task completeness ✓
8. SUCCESS: 36 tasks ready for execution
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Exact file paths included in task descriptions

## Path Conventions
Single project structure (from plan.md):
- **Source**: `src/models/`, `src/services/`, `src/cli/`, `src/lib/`
- **Tests**: `tests/contract/`, `tests/integration/`, `tests/unit/`

## Phase 3.1: Setup & Infrastructure

- [X] T001 Create project structure with src/ and tests/ directories per implementation plan
- [X] T002 Initialize Python 3.11+ project with pyproject.toml and core dependencies (asyncio, pydantic, opentelemetry-sdk)
- [X] T003 [P] Configure development tools: pre-commit hooks, black, isort, mypy in pyproject.toml
- [X] T004 [P] Setup Docker environment with rootless configuration and observability stack in docker-compose.yml
- [X] T005 [P] Create base configuration files: config/default.yaml, config/policies.yaml

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

### Contract Tests (MCP Protocol Validation)
- [X] T006 [P] Contract test for start_conversation MCP tool in tests/contract/test_orchestrator_start_conversation.py
- [X] T007 [P] Contract test for send_message MCP tool in tests/contract/test_orchestrator_send_message.py
- [X] T008 [P] Contract test for get_session_status MCP tool in tests/contract/test_orchestrator_session_status.py
- [X] T009 [P] Contract test for list_agents MCP tool in tests/contract/test_orchestrator_list_agents.py
- [X] T010 [P] Contract test for export_audit_log MCP tool in tests/contract/test_orchestrator_audit_log.py
- [X] T011 [P] Contract test for agent process_request interface in tests/contract/test_agent_interface.py
- [X] T012 [P] Contract test for agent health_check interface in tests/contract/test_agent_health.py

### Integration Tests (End-to-End Scenarios)
- [X] T013 [P] Integration test: Code review cross-verification scenario in tests/integration/test_code_review_scenario.py
- [X] T014 [P] Integration test: Bug reproduction and patch proposal scenario in tests/integration/test_bug_reproduction_scenario.py
- [X] T015 [P] Integration test: Permission boundary enforcement scenario in tests/integration/test_permission_enforcement.py
- [X] T016 [P] Integration test: Performance and observability validation in tests/integration/test_performance_observability.py

## Phase 3.3: Core Implementation (ONLY after tests are failing)

### Data Models (Parallel - Different Files)
- [X] T017 [P] ConversationSession model with state transitions in src/models/conversation_session.py
- [X] T018 [P] TurnMessage model with validation rules in src/models/turn_message.py
- [X] T019 [P] AgentAdapter model with capability definitions in src/models/agent_adapter.py
- [X] T020 [P] PolicyConfiguration model with permission rules in src/models/policy_configuration.py
- [X] T021 [P] AuditRecord model with security context in src/models/audit_record.py
- [X] T022 [P] OrchestrationState model with flow control in src/models/orchestration_state.py

### Agent Adapters (Parallel - Different Files)
- [X] T023 [P] Claude Code agent adapter with headless mode integration in src/services/claude_code_adapter.py
- [X] T024 [P] Codex CLI agent adapter with exec mode integration in src/services/codex_adapter.py
- [X] T025 [P] Base agent adapter interface with common functionality in src/services/base_agent_adapter.py

### Core Services (Sequential - Interdependent)
- [X] T026 Conversation orchestrator service with turn management in src/services/conversation_orchestrator.py
- [X] T027 MCP server implementation for orchestrator tools in src/services/mcp_orchestrator_server.py
- [X] T028 Policy enforcement service with security validation in src/services/policy_enforcer.py
- [X] T029 Session manager with state persistence in src/services/session_manager.py

## Phase 3.4: Integration & Infrastructure

### Observability (Parallel - Different Files)
- [ ] T030 [P] OpenTelemetry configuration with OTLP exporters in src/lib/observability.py
- [ ] T031 [P] Structured logging with audit trail support in src/lib/logging_config.py
- [ ] T032 [P] Metrics collection for conversation performance in src/lib/metrics.py

### CLI Interface
- [ ] T033 Main CLI application with serve and management commands in src/cli/main.py
- [ ] T034 Configuration management and validation in src/lib/config.py

## Phase 3.5: Polish & Validation

### Unit Tests (Parallel - Different Files)
- [ ] T035 [P] Unit tests for data models validation and serialization in tests/unit/test_models.py
- [ ] T036 [P] Performance validation: conversation turn latency <2s in tests/unit/test_performance.py

## Dependencies

### Critical Path
1. **Setup First**: T001-T005 before everything else
2. **Tests Before Implementation**: T006-T016 MUST complete and FAIL before T017-T036
3. **Models Before Services**: T017-T022 before T026-T029
4. **Base Adapter Before Specific**: T025 before T023-T024
5. **Core Services Sequential**: T026 → T027 → T028 → T029
6. **Integration Depends on Core**: T030-T034 after T026-T029

### Parallel Groups
```
Group 1 (Setup): T003, T004, T005
Group 2 (Contract Tests): T006, T007, T008, T009, T010, T011, T012
Group 3 (Integration Tests): T013, T014, T015, T016
Group 4 (Models): T017, T018, T019, T020, T021, T022
Group 5 (Agent Adapters): T023, T024, T025
Group 6 (Observability): T030, T031, T032
Group 7 (Unit Tests): T035, T036
```

## Parallel Execution Examples

### Launch Contract Tests (Phase 3.2)
```bash
# All contract tests can run in parallel - different files
python -m tab.agents.task T006 "Contract test for start_conversation MCP tool in tests/contract/test_orchestrator_start_conversation.py" &
python -m tab.agents.task T007 "Contract test for send_message MCP tool in tests/contract/test_orchestrator_send_message.py" &
python -m tab.agents.task T008 "Contract test for get_session_status MCP tool in tests/contract/test_orchestrator_session_status.py" &
wait
```

### Launch Data Models (Phase 3.3)
```bash
# All data models can run in parallel - different files
python -m tab.agents.task T017 "ConversationSession model with state transitions in src/models/conversation_session.py" &
python -m tab.agents.task T018 "TurnMessage model with validation rules in src/models/turn_message.py" &
python -m tab.agents.task T019 "AgentAdapter model with capability definitions in src/models/agent_adapter.py" &
wait
```

## Validation Checklist
*GATE: Verified before task generation*

- [x] All contracts have corresponding tests (T006-T012)
- [x] All entities have model tasks (T017-T022)
- [x] All tests come before implementation (T006-T016 before T017-T036)
- [x] Parallel tasks truly independent (different files, no shared dependencies)
- [x] Each task specifies exact file path
- [x] No [P] task modifies same file as another [P] task
- [x] Integration scenarios from quickstart.md covered (T013-T016)
- [x] Constitutional requirements addressed (security, observability, MCP compliance)

## Notes
- **TDD Approach**: All tests (T006-T016) must be written and failing before any implementation
- **Parallel Safety**: [P] tasks operate on different files with no shared state
- **Security Focus**: Permission enforcement and audit logging throughout
- **Performance Target**: <2 seconds per conversation turn (validated in T036)
- **MCP Compliance**: Full Model Context Protocol implementation with fallbacks
- **Container Security**: Rootless Docker with capability dropping (T004)

## Constitutional Compliance
This task list ensures compliance with TAB constitutional requirements:
- **Bridge-First Architecture**: MCP integration and agent adapters (T006-T012, T023-T025)
- **Security by Default**: Permission enforcement and audit logging (T015, T021, T028)
- **Observable Operations**: Comprehensive OpenTelemetry integration (T030-T032)
- **Protocol Compliance**: Full MCP implementation with standards (T006-T012, T027)
- **Fail-Safe Design**: Error handling and circuit breakers (T023-T029)