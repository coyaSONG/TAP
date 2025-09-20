# Implementation Plan: Twin-Agent Bridge (TAB)

**Branch**: `001-prd-md` | **Date**: 2025-09-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/home/chsong/projects/TAP/specs/001-prd-md/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path ✓
   → Feature spec loaded successfully
2. Fill Technical Context (scan for NEEDS CLARIFICATION) ✓
   → Detected Project Type: single (orchestrator system)
   → Set Structure Decision: Option 1 (single project)
3. Fill the Constitution Check section ✓
4. Evaluate Constitution Check section
   → Progress: Initial Constitution Check
5. Execute Phase 0 → research.md
   → Resolving NEEDS CLARIFICATION items
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, CLAUDE.md
7. Re-evaluate Constitution Check section
   → Progress: Post-Design Constitution Check
8. Plan Phase 2 → Describe task generation approach
9. STOP - Ready for /tasks command
```

## Summary
TAB (Twin-Agent Bridge) is a secure orchestration system that enables Claude Code and Codex CLI to engage in structured bidirectional conversations for cross-verification of code analysis, bug reproduction, and patch proposals. The system provides MCP integration, sandbox execution, OpenTelemetry observability, and permission controls to ensure safe multi-agent collaboration.

## Technical Context
**Language/Version**: Python 3.11+ (async support for concurrent agent management)
**Primary Dependencies**: asyncio, OpenTelemetry SDK, Pydantic (message validation), subprocess (agent execution)
**Storage**: File-based session logs (JSONL format), configuration files (TOML/YAML)
**Testing**: pytest (async testing capabilities), contract testing for MCP interfaces
**Target Platform**: Linux server (containerized execution preferred)
**Project Type**: single (orchestrator system with CLI interface)
**Performance Goals**: <2 seconds per conversation turn, support for 4-6 turn conversations
**Constraints**: Sandbox execution mandatory, permission approval required, budget/turn limits enforced
**Scale/Scope**: Support for 2 primary agents (Claude Code, Codex CLI), extensible to additional agents

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Bridge-First Architecture**: Does this feature facilitate secure AI agent communication?
- [x] ✅ PASS: Core orchestration system designed for agent interoperability with standardized message protocols

**Security by Default**: Are permission boundaries and sandbox requirements addressed?
- [x] ✅ PASS: Rootless container execution, capability dropping, permission approval workflows planned

**Observable Operations**: Are OpenTelemetry tracing and audit logging included?
- [x] ✅ PASS: Comprehensive OpenTelemetry integration for traces, logs, and metrics across all agent interactions

**Protocol Compliance**: Does this follow MCP standards with appropriate fallbacks?
- [x] ✅ PASS: MCP integration with stdio fallback for headless/exec modes when MCP unavailable

**Fail-Safe Design**: Are error handling, timeouts, and resource limits planned?
- [x] ✅ PASS: Timeout mechanisms, retry logic, cost budgets, and graceful degradation included

## Project Structure

### Documentation (this feature)
```
specs/001-prd-md/
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
├── models/              # Data models and schemas
├── services/            # Core orchestration services
├── cli/                 # Command-line interface
└── lib/                 # Utility libraries

tests/
├── contract/            # MCP and API contract tests
├── integration/         # End-to-end conversation tests
└── unit/                # Component unit tests
```

**Structure Decision**: Option 1 (single project) - TAB is an orchestration system, not a web/mobile application

## Phase 0: Outline & Research ✅
*COMPLETED: All technical unknowns resolved*

### Research Completed:
1. **MCP Integration Patterns**: ✅ Streamable HTTP selected for production deployment
2. **Claude Code Headless Mode**: ✅ Stream-json format and session management documented
3. **Codex CLI Integration**: ✅ CLI execution with session log parsing strategy defined
4. **Security Sandboxing**: ✅ Rootless Docker with Enhanced Container Isolation
5. **OpenTelemetry Integration**: ✅ Async Python OTLP exporters with multi-backend export

**Output**: research.md complete with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts ✅
*COMPLETED: All design artifacts generated*

**Completed Outputs**:
1. **data-model.md**: ✅ Core entities defined with relationships and validation rules
2. **contracts/**: ✅ MCP protocol schemas for orchestrator and agent interfaces
3. **Contract tests**: ✅ Schema validation ready for implementation
4. **quickstart.md**: ✅ End-to-end scenarios and validation procedures
5. **CLAUDE.md**: ✅ Agent context file updated with TAB project information

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Each MCP protocol → contract test task [P]
- Each entity (ConversationSession, TurnMessage) → model creation task [P]
- Each user story → integration test task
- Implementation tasks for orchestrator, agent adapters, CLI interface

**Ordering Strategy**:
- TDD order: Contract tests → Data models → Services → CLI
- Dependency order: Models → Agent adapters → Orchestrator → CLI
- Mark [P] for parallel execution (independent components)

**Estimated Output**: 25-30 numbered, ordered tasks in tasks.md

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)
**Phase 4**: Implementation (execute tasks.md following constitutional principles)
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*No constitutional violations requiring justification*

## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented

**Ready for**: /tasks command execution

---
*Based on Constitution v1.0.0 - See `/memory/constitution.md`*