
# Implementation Plan: Twin-Agent Bridge (TAB) PRD Implementation

**Branch**: `001-prd-md` | **Date**: 2025-09-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/home/chsong/projects/TAP/specs/001-prd-md/spec.md`

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
Secure orchestration system enabling bidirectional conversations between Claude Code and Codex CLI agents for cross-verification of code analysis, bug reproduction, and patch proposals. Implements MCP-compliant communication protocol with sandbox execution, permission controls, OpenTelemetry observability, and configurable turn limits/budget constraints.

## Technical Context
**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, OpenTelemetry, Pydantic, asyncio, Docker, Click
**Storage**: JSONL session logs, YAML config files, in-memory conversation state
**Testing**: pytest with asyncio support, contract testing, integration testing
**Target Platform**: Linux containers with CI/CD integration
**Project Type**: single - CLI/server application with structured agent communication
**Performance Goals**: <200ms turn latency, 4-6 turn conversations, handle concurrent sessions
**Constraints**: Rootless containers, capability dropping, budget/turn limits, MCP compliance
**Scale/Scope**: Multi-agent orchestration, structured message routing, comprehensive audit trails

**User Context**: real_ai_tab.py is PoC-level that partially meets PRD v0.1 core requirements but lacks structured output parsing, session management, budget controls, and OTel integration. Formal src/tab/* components already exist with PRD-compliant adapters, orchestrator, and observability.

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Bridge-First Architecture**: Does this feature facilitate secure AI agent communication?
- [x] ✅ PASS: Enhances agent interoperability | ❌ FAIL: Violates agent-agnostic design

**Security by Default**: Are permission boundaries and sandbox requirements addressed?
- [x] ✅ PASS: Implements proper containment | ❌ FAIL: Bypasses security controls

**Observable Operations**: Are OpenTelemetry tracing and audit logging included?
- [x] ✅ PASS: Comprehensive monitoring planned | ❌ FAIL: Missing observability

**Protocol Compliance**: Does this follow MCP standards with appropriate fallbacks?
- [x] ✅ PASS: Standards-compliant communication | ❌ FAIL: Proprietary protocols

**Fail-Safe Design**: Are error handling, timeouts, and resource limits planned?
- [x] ✅ PASS: Robust failure handling | ❌ FAIL: Missing error resilience

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
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
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure]
```

**Structure Decision**: Option 1 (Single project) - CLI/server application with structured agent communication protocols

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:
   ```
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - One test file per endpoint
   - Assert request/response schemas
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Each story → integration test scenario
   - Quickstart test = story validation steps

5. **Update agent file incrementally** (O(1) operation):
   - Run `.specify/scripts/bash/update-agent-context.sh claude` for your AI assistant
   - If exists: Add only NEW tech from current plan
   - Preserve manual additions between markers
   - Update recent changes (keep last 3)
   - Keep under 150 lines for token efficiency
   - Output to repository root

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, agent-specific file

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `.specify/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Real_ai_tab.py upgrade tasks based on PRD compliance gaps identified in user context
- MCP integration tasks for agent adapters and protocol compliance
- Security policy enforcement tasks with sandbox execution
- OpenTelemetry integration tasks for comprehensive observability

**Specific Task Categories**:
1. **real_ai_tab.py Upgrade Tasks**: Replace stdout parsing with stream-json, add session log parsing, implement budget controls
2. **Contract Implementation**: MCP orchestrator API, agent interface contracts
3. **Security Enhancement**: Permission validation, sandbox execution, approval workflows
4. **Observability Integration**: OTel spans, metrics collection, audit logging
5. **Testing Infrastructure**: Contract tests, integration scenarios, end-to-end validation

**Ordering Strategy**:
- TDD order: Tests before implementation
- Dependency order: Models → Adapters → Orchestrator → CLI → Integration
- Priority: Security and observability foundational components first
- Mark [P] for parallel execution (independent modules)

**Estimated Output**: 30-35 numbered, ordered tasks in tasks.md focusing on production readiness

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |


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
- [ ] Complexity deviations documented

---
*Based on Constitution v1.0.0 - See `/memory/constitution.md`*
