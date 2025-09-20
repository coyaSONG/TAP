<!--
Sync Impact Report:
Version change: Initial → 1.0.0
New constitution created for TAP (Twin-Agent Bridge) project
Added sections: Core Principles (5), Security Requirements, Development Workflow
No template files requiring updates at this time
Follow-up TODOs: None
-->

# TAP Constitution

## Core Principles

### I. Bridge-First Architecture
All features MUST facilitate secure communication between AI coding agents; Components must be agent-agnostic and interoperable; Clear protocol boundaries required between Claude Code and Codex CLI interfaces.

**Rationale**: The primary purpose is orchestrating bidirectional Q&A between different AI agents, requiring consistent interfaces regardless of underlying agent implementation.

### II. Security by Default
All agent interactions MUST operate within strict permission boundaries; Sandbox execution mandatory for all external commands; Permission approval required for file system and network access.

**Rationale**: AI agents have broad capabilities that require careful containment to prevent unauthorized access or actions during cross-agent collaboration.

### III. Observable Operations
All agent communications MUST be traced via OpenTelemetry; Structured logging required for audit trails; Real-time monitoring of agent interactions and resource consumption.

**Rationale**: Cross-agent operations are complex and require comprehensive visibility for debugging, security auditing, and performance optimization.

### IV. Protocol Compliance
Communication MUST follow standardized message schemas; MCP (Model Context Protocol) integration required where available; Graceful fallback to headless/exec modes when MCP unavailable.

**Rationale**: Standardized protocols ensure reliable communication between heterogeneous AI agents and enable future extensibility.

### V. Fail-Safe Design
System MUST handle single-agent failures gracefully; Timeout and retry mechanisms mandatory; Cost and iteration budgets enforced to prevent runaway operations.

**Rationale**: Multi-agent systems introduce additional failure modes that require robust error handling and resource protection.

## Security Requirements

Rootless container execution with capability dropping (`--cap-drop ALL`); File system access limited to designated work directories; Network isolation except for essential MCP communications; All agent permissions must be explicitly approved; Sensitive data logging prohibited.

## Development Workflow

Test-Driven Development mandatory for all bridge components; Integration tests required for agent communication protocols; Contract testing for MCP interfaces; Performance validation for multi-turn conversations; Security testing for permission boundary enforcement.

## Governance

Constitution supersedes all development practices; All code changes must demonstrate compliance with security and observability requirements; Cross-agent interaction patterns must be documented and tested; Breaking changes to communication protocols require architectural review; Performance regressions in agent coordination are blocking issues.

**Version**: 1.0.0 | **Ratified**: 2025-09-21 | **Last Amended**: 2025-09-21