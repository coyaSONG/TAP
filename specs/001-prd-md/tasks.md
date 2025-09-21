# Tasks: Twin-Agent Bridge (TAB) PRD Implementation

**Input**: Design documents from `/specs/001-prd-md/`
**Prerequisites**: plan.md, research.md, data-model.md, contracts/, quickstart.md

## Execution Flow Summary
This tasks list addresses the key user context: upgrading real_ai_tab.py from PoC-level to production PRD compliance, implementing the 6 core entities, 2 MCP contracts, 4 quickstart scenarios, and ensuring security/observability requirements.

**Progress Status (2025-09-21)**:
- ✅ **Phase 3.1-3.4 완료**: T001-T024 (24/44 작업, 55%)
- 🟡 **Phase 3.5 진행중**: T025, T027, T028 완료, T026, T029 미완료
- ⏳ **Phase 3.6-3.8 대기**: T030-T044 미착수

## Path Conventions
Single project structure: `src/tab/`, `tests/` at repository root per plan.md

## Phase 3.1: Setup and Prerequisites

- [x] T001 Validate existing project structure and dependencies match pyproject.toml requirements
- [x] T002 [P] Configure development environment with black, ruff, mypy, and pytest tools
- [x] T003 [P] Setup OpenTelemetry infrastructure and Docker observability stack per research.md
- [x] T004 [P] Create test workspace and policy configuration files in config/

## Phase 3.2: Contract Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

- [x] T005 [P] Contract test for MCP start_conversation tool in tests/contract/test_mcp_orchestrator.py
- [x] T006 [P] Contract test for MCP send_message tool in tests/contract/test_mcp_orchestrator.py
- [x] T007 [P] Contract test for agent process_request interface in tests/contract/test_agent_interface.py
- [x] T008 [P] Contract test for agent health_check interface in tests/contract/test_agent_interface.py
- [x] T009 [P] Integration test for code review cross-verification scenario in tests/integration/test_code_review_scenario.py
- [x] T010 [P] Integration test for bug reproduction workflow in tests/integration/test_bug_reproduction_scenario.py
- [x] T011 [P] Integration test for permission boundary enforcement in tests/integration/test_security_scenario.py
- [x] T012 [P] Integration test for performance and observability in tests/integration/test_observability_scenario.py

## Phase 3.3: Core Data Models (ONLY after tests are failing)

- [x] T013 [P] ConversationSession model with state transitions in src/tab/models/conversation_session.py
- [x] T014 [P] TurnMessage model with validation rules in src/tab/models/turn_message.py
- [x] T015 [P] AgentAdapter model with status management in src/tab/models/agent_adapter.py
- [x] T016 [P] PolicyConfiguration model with permission rules in src/tab/models/policy_configuration.py
- [x] T017 [P] AuditRecord model with security context in src/tab/models/audit_record.py
- [x] T018 [P] OrchestrationState model with flow control in src/tab/models/orchestration_state.py

## Phase 3.4: Service Layer Implementation

- [x] T019 Enhance PolicyEnforcer service with validation logic per security research in src/tab/services/policy_enforcer.py
- [x] T020 Upgrade ClaudeCodeAdapter to use --output-format stream-json parsing in src/tab/services/claude_code_adapter.py
- [x] T021 Upgrade CodexAdapter to parse $CODEX_HOME/sessions/**/rollout-*.jsonl logs in src/tab/services/codex_adapter.py
- [x] T022 Enhance ConversationOrchestrator with budget controls and turn limits in src/tab/services/conversation_orchestrator.py
- [x] T023 Implement SessionManager with JSONL persistence and recovery in src/tab/services/session_manager.py
- [x] T024 Create MCP server implementation with tool handlers in src/tab/services/mcp_orchestrator_server.py

## Phase 3.5: Real AI Tab Upgrade (Core User Requirement)

- [x] T025 Replace real_ai_tab.py stdout parsing with structured ClaudeCodeAdapter integration
- [ ] T026 Add real_ai_tab.py session log parsing using CodexAdapter JSONL methods
- [x] T027 Implement real_ai_tab.py budget controls and max_turns constraints using ConversationOrchestrator
- [x] T028 Integrate real_ai_tab.py with OpenTelemetry spans for conversation.turn and agent.call operations
- [ ] T029 Add real_ai_tab.py approval mode and permission boundaries using PolicyEnforcer

## Phase 3.6: Observability and Security Integration

- [ ] T030 [P] Enhance observability.py with conversation-specific spans and metrics in src/tab/lib/observability.py
- [ ] T031 [P] Implement security audit logging with cryptographic integrity in src/tab/lib/logging_config.py
- [ ] T032 [P] Add circuit breaker patterns and retry logic in src/tab/lib/metrics.py
- [ ] T033 Configure Docker rootless containers with capability dropping per security requirements

## Phase 3.7: CLI and API Integration

- [ ] T034 Enhance CLI main.py with conversation management commands and FastAPI integration
- [ ] T035 Add CLI command for starting conversations with agent selection and policy enforcement
- [ ] T036 Implement CLI status and monitoring commands for session management
- [ ] T037 Add CLI configuration management for policies and agent settings

## Phase 3.8: Polish and Production Readiness

- [ ] T038 [P] Unit tests for policy validation logic in tests/unit/test_policy_validation.py
- [ ] T039 [P] Unit tests for message parsing and routing in tests/unit/test_message_processing.py
- [ ] T040 [P] Unit tests for session state management in tests/unit/test_session_management.py
- [ ] T041 Performance validation for <200ms turn latency requirements per quickstart scenarios
- [ ] T042 [P] Security penetration testing for permission boundary bypass attempts
- [ ] T043 [P] End-to-end quickstart scenario validation with all 4 test cases
- [ ] T044 [P] Documentation updates for production deployment and monitoring setup

## Dependencies

**Critical Ordering**:
- Setup (T001-T004) before everything
- Contract tests (T005-T012) before ANY implementation
- Core models (T013-T018) before services (T019-T024)
- Services before real_ai_tab.py upgrade (T025-T029)
- Security/observability (T030-T033) before CLI integration (T034-T037)
- All implementation before polish (T038-T044)

**Blocking Dependencies**:
- T013 blocks T019, T022, T023 (ConversationSession needed for orchestration)
- T014 blocks T020, T021 (TurnMessage needed for adapters)
- T016 blocks T019, T025, T029 (PolicyConfiguration needed for enforcement)
- T020, T021 block T025-T029 (adapter upgrades needed for real_ai_tab.py)
- T022, T023 block T025-T029 (orchestrator/session management needed)

## Parallel Execution Examples

**Phase 3.2 - Contract Tests (can run simultaneously)**:
```bash
# Launch T005-T012 together - all different test files
Task: "Contract test for MCP start_conversation tool in tests/contract/test_mcp_orchestrator.py"
Task: "Contract test for agent process_request interface in tests/contract/test_agent_interface.py"
Task: "Integration test for code review cross-verification scenario in tests/integration/test_code_review_scenario.py"
Task: "Integration test for permission boundary enforcement in tests/integration/test_security_scenario.py"
```

**Phase 3.3 - Data Models (can run simultaneously)**:
```bash
# Launch T013-T018 together - all different model files
Task: "ConversationSession model with state transitions in src/tab/models/conversation_session.py"
Task: "TurnMessage model with validation rules in src/tab/models/turn_message.py"
Task: "AgentAdapter model with status management in src/tab/models/agent_adapter.py"
Task: "PolicyConfiguration model with permission rules in src/tab/models/policy_configuration.py"
```

**Phase 3.8 - Polish Tasks (can run simultaneously)**:
```bash
# Launch T038-T040, T042-T044 together - different files
Task: "Unit tests for policy validation logic in tests/unit/test_policy_validation.py"
Task: "Security penetration testing for permission boundary bypass attempts"
Task: "End-to-end quickstart scenario validation with all 4 test cases"
Task: "Documentation updates for production deployment and monitoring setup"
```

## Key Implementation Notes

**real_ai_tab.py Upgrade Strategy** (T025-T029):
- Replace subprocess stdout parsing with proper adapter pattern usage
- Integrate with existing production-ready components in src/tab/
- Maintain backward compatibility while adding PRD compliance features
- Focus on structured output, session management, and observability integration

**Security Focus** (T019, T031, T033, T042):
- Implement MAESTRO threat model recommendations from research.md
- Rootless container execution with strict capability controls
- Cryptographic audit logging for compliance requirements
- Permission boundary enforcement with real-time validation

**Observability Focus** (T030, T041, T043):
- OpenTelemetry spans for every conversation turn and agent interaction
- Performance validation against <200ms latency requirements
- Comprehensive metrics for cost tracking and budget enforcement
- Structured logging with trace correlation

## Validation Checklist
- [x] All contracts (2) have corresponding tests (T005-T008)
- [x] All entities (6) have model tasks (T013-T018)
- [x] All tests (T005-T012) come before implementation (T013+)
- [x] Parallel tasks [P] are truly independent (different files)
- [x] Each task specifies exact file path
- [x] No [P] task modifies same file as another [P] task
- [x] real_ai_tab.py upgrade addresses user context requirements
- [x] Production readiness covers security, observability, and performance