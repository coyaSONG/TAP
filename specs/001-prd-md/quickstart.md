# TAB Quickstart Guide

**Date**: 2025-09-21
**Purpose**: End-to-end validation scenarios for Twin-Agent Bridge
**Prerequisites**: Docker, Python 3.11+, Claude Code CLI, Codex CLI

## Quick Setup

### 1. Environment Preparation
```bash
# Clone and setup TAB
git clone <repository-url> tab
cd tab

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify CLI tools are available
claude --version
codex --version
```

### 2. Configuration
```bash
# Create configuration directory
mkdir -p ~/.tab/config

# Copy default configuration
cp config/default.yaml ~/.tab/config/config.yaml

# Set environment variables
export TAB_CONFIG_PATH=~/.tab/config
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export TAB_LOG_LEVEL=INFO
```

### 3. Start Services
```bash
# Start observability stack (Jaeger, Prometheus)
docker-compose up -d observability

# Start TAB orchestrator
python -m tab.cli serve --port 8000 --config ~/.tab/config/config.yaml
```

## Test Scenarios

### Scenario 1: Code Review Cross-Verification (5 minutes)

**Objective**: Verify that Claude Code and Codex CLI can collaborate on code analysis

**Steps**:
1. **Start conversation** about race condition analysis:
   ```bash
   curl -X POST http://localhost:8000/api/conversations \
     -H "Content-Type: application/json" \
     -d '{
       "topic": "Analyze potential race conditions in the user authentication module",
       "participants": ["claude_code", "codex_cli"],
       "max_turns": 6,
       "budget_usd": 0.50,
       "files": ["src/auth/user_manager.py", "tests/test_auth.py"]
     }'
   ```

2. **Expected behavior**:
   - Session created with unique ID
   - Claude Code provides initial analysis
   - Codex CLI performs counter-verification
   - 4-6 turns of structured dialogue
   - Consensus reached on findings

3. **Validation checks**:
   ```bash
   # Check session completed successfully
   curl http://localhost:8000/api/conversations/{session_id}/status

   # Verify audit log contains security analysis
   curl http://localhost:8000/api/conversations/{session_id}/audit

   # Check OpenTelemetry traces in Jaeger UI
   open http://localhost:16686
   ```

**Success Criteria**:
- ✅ Session status: `completed`
- ✅ Turn count: 4-6 turns
- ✅ Cost under budget ($0.50)
- ✅ Both agents provided substantive input
- ✅ Consensus reached on race condition assessment

---

### Scenario 2: Bug Reproduction and Patch Proposal (10 minutes)

**Objective**: Test end-to-end bug fixing workflow with agent collaboration

**Steps**:
1. **Create bug report conversation**:
   ```bash
   curl -X POST http://localhost:8000/api/conversations \
     -H "Content-Type: application/json" \
     -d '{
       "topic": "Reproduce and fix the data validation bug in the API endpoint",
       "participants": ["codex_cli", "claude_code"],
       "max_turns": 8,
       "budget_usd": 1.00,
       "working_directory": "./test_workspace",
       "policy_id": "development_safe"
     }'
   ```

2. **Expected workflow**:
   - Codex CLI reproduces the bug with test cases
   - Claude Code analyzes root cause and suggests patch scope
   - Codex CLI implements fix with tests
   - Claude Code reviews and suggests improvements
   - Final consolidated patch proposal

3. **Validation**:
   ```bash
   # Check final output includes working patch
   curl http://localhost:8000/api/conversations/{session_id}/summary

   # Verify no unauthorized file modifications
   git status

   # Check security audit events
   curl http://localhost:8000/api/conversations/{session_id}/audit?security_events=true
   ```

**Success Criteria**:
- ✅ Bug successfully reproduced with test case
- ✅ Patch proposal includes code and tests
- ✅ All file operations within approved directory
- ✅ No security policy violations
- ✅ Both agents contributed to solution

---

### Scenario 3: Permission Boundary Enforcement (3 minutes)

**Objective**: Verify security controls prevent unauthorized operations

**Steps**:
1. **Start restricted conversation**:
   ```bash
   curl -X POST http://localhost:8000/api/conversations \
     -H "Content-Type: application/json" \
     -d '{
       "topic": "Analyze system performance and suggest optimizations",
       "participants": ["claude_code"],
       "policy_id": "read_only_strict",
       "max_turns": 3
     }'
   ```

2. **Attempt unauthorized operations**:
   - Request file modifications outside workspace
   - Attempt network access to external services
   - Try to execute system commands

3. **Expected behavior**:
   - Operations blocked by policy enforcement
   - Security events logged
   - Agent receives permission denied responses
   - Conversation continues with allowed operations only

**Success Criteria**:
- ✅ Unauthorized operations blocked
- ✅ Security audit events recorded
- ✅ Agent adapts to work within constraints
- ✅ No system compromise

---

### Scenario 4: Performance and Observability (2 minutes)

**Objective**: Validate monitoring and performance characteristics

**Steps**:
1. **Monitor system metrics** during conversation:
   ```bash
   # Check Prometheus metrics
   curl http://localhost:9090/metrics | grep tab_

   # View OpenTelemetry traces
   # Navigate to Jaeger UI at http://localhost:16686
   ```

2. **Performance validation**:
   - Conversation turn latency < 2 seconds
   - Memory usage within limits
   - No resource leaks
   - Proper trace correlation

**Success Criteria**:
- ✅ Average turn latency < 2 seconds
- ✅ Memory usage stable over time
- ✅ Complete trace data in Jaeger
- ✅ Metrics available in Prometheus
- ✅ Structured logs in correct format

---

## Environment Reset

After testing, clean up the environment:

```bash
# Stop orchestrator
pkill -f "tab.cli serve"

# Stop observability stack
docker-compose down

# Clean test workspace
rm -rf ./test_workspace

# Clear session data
rm -rf ~/.tab/sessions/*

# Reset log files
truncate -s 0 ~/.tab/logs/*.log
```

## Troubleshooting

### Common Issues

**Issue**: Agent not responding
```bash
# Check agent health
curl http://localhost:8000/api/agents/health

# Restart specific agent adapter
python -m tab.agents.claude_code restart
```

**Issue**: Permission denied errors
```bash
# Check policy configuration
cat ~/.tab/config/policies.yaml

# Verify file permissions
ls -la ~/.tab/config/
```

**Issue**: High latency
```bash
# Check system resources
docker stats

# Review trace data for bottlenecks
# Open Jaeger UI and examine slow traces
```

### Logs and Debugging

```bash
# Application logs
tail -f ~/.tab/logs/orchestrator.log

# Agent-specific logs
tail -f ~/.tab/logs/agents/claude_code.log
tail -f ~/.tab/logs/agents/codex_cli.log

# Audit logs
tail -f ~/.tab/logs/audit.jsonl

# Docker logs
docker-compose logs observability
```

## Next Steps

After successful quickstart validation:

1. **Explore Configuration**: Review `~/.tab/config/` for customization options
2. **Add Custom Policies**: Create custom security policies for your use case
3. **Integration Testing**: Run the full test suite with `pytest tests/`
4. **Production Deployment**: Follow the deployment guide for production setup
5. **Monitoring Setup**: Configure alerts and dashboards for operational monitoring

For more detailed information, see:
- [Configuration Guide](./configuration.md)
- [Security Policy Reference](./security-policies.md)
- [API Documentation](./api-reference.md)
- [Deployment Guide](./deployment.md)