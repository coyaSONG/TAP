# Data Model: Twin-Agent Bridge (TAB)

**Date**: 2025-09-21
**Phase**: 1 - Design & Contracts
**Dependencies**: research.md

## Core Entities

### ConversationSession
Represents a complete multi-turn dialogue between agents, including turn history, state, and metadata.

**Attributes**:
- `session_id`: Unique identifier for the conversation session
- `participants`: List of agent identifiers participating in conversation
- `topic`: Initial question or task description
- `status`: Current session status (active, completed, failed, timeout)
- `created_at`: Session creation timestamp
- `updated_at`: Last activity timestamp
- `turn_history`: Ordered list of TurnMessage objects
- `metadata`: Session-level metadata (costs, performance metrics)
- `policy_config`: Applied PolicyConfiguration for this session

**Relationships**:
- Has many TurnMessage objects
- References PolicyConfiguration
- Tracked by multiple AuditRecord objects

**State Transitions**:
- `active` → `completed` (when consensus reached)
- `active` → `failed` (when agent failure occurs)
- `active` → `timeout` (when limits exceeded)

**Validation Rules**:
- session_id must be unique
- participants must contain at least 2 agents
- turn_history must maintain chronological order
- status transitions must follow defined state machine

---

### TurnMessage
Individual communication unit containing agent identity, content, role designation, and policy constraints.

**Attributes**:
- `turn_id`: Unique identifier for this conversation turn
- `session_id`: Reference to parent ConversationSession
- `from_agent`: Identifier of the sending agent
- `to_agent`: Identifier of the receiving agent
- `role`: Message role (user, assistant, system)
- `content`: Message content (text, structured data, files)
- `attachments`: Optional file attachments or references
- `timestamp`: When the message was created
- `policy_constraints`: Applied policy constraints for this turn
- `metadata`: Turn-specific metadata (cost, duration, tokens)

**Relationships**:
- Belongs to ConversationSession
- References AgentAdapter for from_agent and to_agent
- Generates AuditRecord entries

**Validation Rules**:
- turn_id must be unique within session
- from_agent and to_agent must be different
- content must not be empty
- role must be valid enumeration value
- policy_constraints must be valid for agent capabilities

---

### AgentAdapter
Interface wrapper for each CLI tool providing standardized communication protocol.

**Attributes**:
- `agent_id`: Unique identifier for the agent
- `agent_type`: Type of agent (claude_code, codex_cli, generic)
- `name`: Human-readable agent name
- `version`: Agent version or CLI version
- `capabilities`: List of supported operations/tools
- `connection_config`: Connection configuration (MCP, CLI, API)
- `status`: Current agent status (available, busy, failed, maintenance)
- `last_health_check`: Timestamp of last successful health check
- `session_manager`: Session management configuration
- `execution_limits`: Resource and time limits for this agent

**Relationships**:
- Sends and receives TurnMessage objects
- References PolicyConfiguration for permissions
- Generates OrchestrationState updates

**State Transitions**:
- `available` → `busy` (when processing request)
- `busy` → `available` (when request completed)
- `available` → `failed` (when health check fails)
- `failed` → `available` (when recovery succeeds)

**Validation Rules**:
- agent_id must be unique across system
- agent_type must be supported type
- capabilities must match agent_type specifications
- connection_config must be valid for agent_type

---

### PolicyConfiguration
Permission and constraint definitions governing agent behavior and resource access.

**Attributes**:
- `policy_id`: Unique identifier for the policy
- `name`: Human-readable policy name
- `description`: Policy purpose and scope
- `allowed_tools`: List of tools/operations permitted
- `disallowed_tools`: List of explicitly forbidden tools
- `permission_mode`: Permission approval mode (auto, prompt, deny)
- `resource_limits`: Resource constraints (time, cost, memory)
- `file_access_rules`: File system access permissions
- `network_access_rules`: Network access permissions
- `sandbox_config`: Sandboxing and isolation configuration
- `approval_required`: Operations requiring explicit approval

**Relationships**:
- Applied to ConversationSession objects
- Referenced by AgentAdapter configurations
- Enforced in AuditRecord validations

**Validation Rules**:
- policy_id must be unique
- allowed_tools and disallowed_tools must not overlap
- resource_limits must have positive values
- permission_mode must be valid enumeration
- sandbox_config must be valid for deployment environment

---

### AuditRecord
Security and compliance log entry tracking agent actions, decisions, and system events.

**Attributes**:
- `record_id`: Unique identifier for the audit record
- `timestamp`: When the event occurred
- `event_type`: Type of event (action, decision, error, security)
- `session_id`: Reference to related ConversationSession
- `agent_id`: Agent that performed the action
- `action`: Specific action or operation performed
- `result`: Outcome of the action (success, failure, blocked)
- `reason`: Rationale for the action or decision
- `policy_applied`: PolicyConfiguration that governed the action
- `resource_usage`: Resources consumed (time, cost, tokens)
- `security_context`: Security-related metadata
- `trace_id`: OpenTelemetry trace identifier for correlation

**Relationships**:
- References ConversationSession
- References AgentAdapter
- References PolicyConfiguration
- Correlates with OrchestrationState

**Validation Rules**:
- record_id must be unique
- timestamp must be valid and not future
- event_type must be valid enumeration
- session_id and agent_id must reference existing entities
- security_context must contain required security fields

---

### OrchestrationState
Current conversation context, participant status, and flow control information.

**Attributes**:
- `state_id`: Unique identifier for the orchestration state
- `session_id`: Reference to associated ConversationSession
- `current_turn`: Current turn number in conversation
- `active_agent`: Agent currently processing or expected to respond
- `conversation_flow`: Flow control state (waiting, processing, converging)
- `convergence_signals`: Indicators of conversation convergence
- `timeout_deadline`: When the current operation times out
- `cost_budget_remaining`: Remaining cost budget for session
- `turn_budget_remaining`: Remaining turn budget for session
- `error_count`: Number of errors encountered in session
- `retry_count`: Number of retries attempted for current operation
- `context_summary`: Summary of conversation context for agent handoff

**Relationships**:
- Belongs to ConversationSession
- References current AgentAdapter
- Updated by AuditRecord events

**State Transitions**:
- `waiting` → `processing` (when agent starts work)
- `processing` → `waiting` (when agent completes turn)
- `waiting` → `converging` (when convergence detected)
- `converging` → `completed` (when consensus reached)

**Validation Rules**:
- state_id must be unique
- current_turn must be positive and sequential
- active_agent must reference valid AgentAdapter
- budget values must be non-negative
- timeout_deadline must be future timestamp

---

## Entity Relationships

```
ConversationSession 1:N TurnMessage
ConversationSession 1:1 OrchestrationState
ConversationSession N:1 PolicyConfiguration
ConversationSession 1:N AuditRecord

TurnMessage N:1 AgentAdapter (from_agent)
TurnMessage N:1 AgentAdapter (to_agent)
TurnMessage 1:N AuditRecord

AgentAdapter 1:N TurnMessage
AgentAdapter N:1 PolicyConfiguration
AgentAdapter 1:N AuditRecord

PolicyConfiguration 1:N ConversationSession
PolicyConfiguration 1:N AgentAdapter
PolicyConfiguration 1:N AuditRecord

AuditRecord N:1 ConversationSession
AuditRecord N:1 AgentAdapter
AuditRecord N:1 PolicyConfiguration

OrchestrationState 1:1 ConversationSession
OrchestrationState N:1 AgentAdapter (active_agent)
```

## Data Storage Strategy

**Session Data**: File-based JSONL format for conversation logs and session state
**Configuration Data**: YAML/TOML files for policies and agent configurations
**Audit Data**: Structured JSON logs with OpenTelemetry correlation
**Temporary State**: In-memory with periodic persistence checkpoints

## Schema Validation

All entities use Pydantic models for runtime validation with strict type checking and business rule enforcement. Schema evolution handled through versioned model definitions with backward compatibility guarantees.