# Implementation Plan: TAP Agent Dialog Integration

**Branch**: `003-tap-conversationsession-api` | **Date**: 2025-09-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/home/chsong/projects/TAP/specs/003-tap-conversationsession-api/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Fill the Constitution Check section based on the content of the constitution document.
4. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
5. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, `GEMINI.md` for Gemini CLI, `QWEN.md` for Qwen Code or `AGENTS.md` for opencode).
7. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
8. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
9. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
Extend TAB system's 3-layer architecture (CLI → services → infra) to enable real multi-agent conversations by fixing service layer integration issues. Complete dependency injection container integration for SessionManager, PolicyEnforcer, and ConversationOrchestrator while standardizing API interfaces through IConversationSessionService abstract base. Preserve existing sync entry points via async adapters while maintaining all current TAB components (Pydantic, FastAPI, OpenTelemetry, Docker).

## Technical Context
**Language/Version**: Python 3.11+ with asyncio (existing TAB foundation)
**Primary Dependencies**: Pydantic for models, FastAPI for HTTP, OpenTelemetry for observability (existing TAB stack)
**Storage**: JSONL session files with existing persistence layer (no changes required)
**Testing**: pytest with asyncio-mode=auto (from existing TAB configuration)
**Target Platform**: Linux server (existing TAB deployment environment)
**Project Type**: single (TAB unified Python project)
**Performance Goals**: <5s conversation startup, <100ms context retrieval, real-time agent responses
**Constraints**: Maintain backward compatibility with existing TAB services, preserve all current functionality
**Scale/Scope**: Support 2-4 concurrent agent conversations initially, extensible to additional agent types

**Architecture Decision**: Maintain TAB 3-layer architecture (CLI → services → infra); new async services coexist with existing sync services via adapter pattern
**Dependency Management**: Extend existing dependency injection patterns; register ConversationSessionService, PolicyEngine, Persistence gateways via configuration
**Service Interface Contract**: Introduce IConversationSessionService abstract base with async start_session, stream_turns, finalize hooks; legacy implementations conform via adapters
**Integration Strategy**: Fix constructor dependency injection, unify API parameter naming, implement missing methods, make agent configuration dynamic

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Bridge-First Architecture**: Does this feature facilitate secure AI agent communication?
- [x] ✅ PASS: Enhances agent interoperability - Enables structured conversations between Claude Code and Codex CLI with extensibility for additional agents

**Security by Default**: Are permission boundaries and sandbox requirements addressed?
- [x] ✅ PASS: Implements proper containment - Integrates with existing PolicyEnforcer and maintains security boundaries through service layer abstraction

**Observable Operations**: Are OpenTelemetry tracing and audit logging included?
- [x] ✅ PASS: Comprehensive monitoring planned - Leverages existing OpenTelemetry infrastructure and adds conversation-specific spans

**Protocol Compliance**: Does this follow MCP standards with appropriate fallbacks?
- [x] ✅ PASS: Standards-compliant communication - Uses existing Pydantic models and structured message passing consistent with TAB architecture

**Fail-Safe Design**: Are error handling, timeouts, and resource limits planned?
- [x] ✅ PASS: Robust failure handling - Implements conversation convergence detection, turn limits, and graceful agent failure recovery

## Project Structure

### Documentation (this feature)
```
specs/003-tap-conversationsession-api/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
# Option 1: Single project (DEFAULT)
src/
├── models/              # ConversationSession enhancements
├── services/            # SessionManager, PolicyEnforcer, ConversationOrchestrator fixes
├── cli/                 # start-conversation command integration
└── lib/                 # Configuration and utilities

tests/
├── contract/            # Service interface contract tests
├── integration/         # End-to-end conversation flow tests
└── unit/               # Individual service component tests
```

**Structure Decision**: Option 1 (single project) - maintains existing TAB architecture

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - Dependency injection container integration patterns in existing TAB codebase
   - Async/sync adapter implementation strategies
   - Service interface standardization approaches
   - Agent configuration management patterns

2. **Generate and dispatch research agents**:
   ```
   Task: "Research existing TAB dependency injection patterns for service container integration"
   Task: "Find best practices for async/sync adapter patterns in Python 3.11+ asyncio"
   Task: "Research service interface abstraction patterns for conversation management"
   Task: "Investigate dynamic agent configuration loading strategies"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all technical approach decisions resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - IConversationSessionService interface definition
   - Enhanced ConversationSession model extensions
   - Agent configuration and registry models
   - Service container registration schemas

2. **Generate API contracts** from functional requirements:
   - ConversationSessionService interface methods
   - SessionManager enhanced constructor contract
   - PolicyEnforcer configuration injection contract
   - ConversationOrchestrator unified API contract
   - Output service interface schemas to `/contracts/`

3. **Generate contract tests** from contracts:
   - One test file per service interface
   - Assert service registration and initialization
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - CLI conversation initiation test scenario
   - Agent response and session persistence scenario
   - Dynamic agent configuration loading scenario
   - Policy enforcement and convergence detection scenario

5. **Update agent file incrementally** (O(1) operation):
   - Run `.specify/scripts/bash/update-agent-context.sh claude` for Claude Code
   - Add async service patterns and DI container usage
   - Preserve existing TAB architectural guidelines
   - Update with conversation management specifics
   - Keep under 150 lines for token efficiency

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, CLAUDE.md

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `.specify/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Each service interface → contract test task [P]
- Each constructor fix → implementation task (sequential - same files)
- Each API unification → parameter alignment task [P]
- Each missing method → implementation task (sequential - same files)
- Integration tasks to verify end-to-end conversation flow

**Ordering Strategy**:
- TDD order: Contract tests before implementation
- Dependency order: Service constructors before orchestrator before CLI
- Mark [P] for parallel execution (different services/files)
- Sequential execution for same-file modifications

**Estimated Output**: 15-20 numbered, ordered tasks in tasks.md focusing on the 4 core integration issues

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)
**Phase 4**: Implementation (execute tasks.md following constitutional principles)
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

No constitutional violations identified. All requirements align with TAB's Bridge-First Architecture and maintain existing security, observability, and protocol compliance standards.

## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command) - research.md created
- [x] Phase 1: Design complete (/plan command) - data-model.md, contracts/, quickstart.md, CLAUDE.md created
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS - All constitutional principles maintained
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented (none required)

---
*Based on Constitution v1.0.0 - See `/memory/constitution.md`*