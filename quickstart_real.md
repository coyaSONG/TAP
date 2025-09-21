# TAB 실제 사용 가이드

## 새로운 기능! 🎉 Production-Ready real_ai_tab.py

### ✨ 즉시 사용 가능한 프로덕션 TAB
```bash
# 업그레이드된 real_ai_tab.py 실행 - 설정 없이 바로 사용!
python real_ai_tab.py

# 대화형 설정으로 시작:
# 1. 주제 입력
# 2. 보안 정책 선택 (기본/읽기전용/개발안전)
# 3. 승인 모드 선택 (자동/수동승인/거부)
# 4. 예산 및 턴 수 제한 설정
# 5. Claude Code ↔ Codex CLI 실시간 대화 시작!
```

### 🔒 새로운 보안 기능
- **정책 기반 접근 제어**: 3단계 보안 정책 선택
- **실시간 승인 워크플로**: 민감한 작업에 대한 사용자 승인
- **암호화 감사 로깅**: 변조 방지 로그 체인
- **예산 및 리소스 제한**: 비용 및 시간 제한 자동 적용

## 준비 사항

### 1. 필수 도구 설치
```bash
# Claude Code 설치 확인
claude --version

# Codex CLI 설치 (필요시)
npm install -g @openai/codex-cli

# TAB 시스템 의존성 설치
uv sync --dev
```

### 2. 환경 설정 (선택사항)
```bash
# TAB 설정 디렉토리 생성 (자동 생성됨)
mkdir -p ~/.tab/config
mkdir -p ~/.tab/logs
mkdir -p ~/.tab/sessions

# OpenTelemetry 관찰가능성 (선택사항)
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

## 실제 사용 방법

### 1. 🚀 빠른 시작 - real_ai_tab.py
```bash
# 단 한 번의 명령으로 시작!
python real_ai_tab.py

# 대화형 설정 과정:
💭 AI 에이전트들이 논의할 주제를 입력하세요: Python 성능 최적화

🔒 보안 및 승인 설정:
   1. auto   - 자동 승인 (빠른 대화)
   2. prompt - 사용자 승인 필요 (안전한 대화)
   3. deny   - 모든 요청 거부 (테스트 모드)
승인 모드를 선택하세요 (1-3, 기본값: 1): 2

🛡️ 보안 정책 선택:
   1. default          - 기본 개발 정책
   2. read_only_strict - 읽기 전용 엄격
   3. development_safe - 개발 안전 모드
보안 정책을 선택하세요 (1-3, 기본값: 1): 1

💰 예산 및 제한 설정:
최대 예산 (USD, 기본값: 1.0): 0.5
최대 턴 수 (기본값: 10): 8

✅ 대화 설정 완료:
   📝 주제: Python 성능 최적화
   🤖 참여 에이전트: Claude Code, Codex CLI
   🔒 승인 모드: prompt
   🛡️ 보안 정책: default
   💰 예산: $0.5
   🔄 최대 턴: 8
```

### 2. 고급 TAB 서버 모드
```bash
# 전체 TAB 서버 시작 (더 많은 기능)
uv run python -m tab.cli.main serve --port 8000

# HTTP API를 통한 접근
curl -X POST http://localhost:8000/api/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "코드 리팩토링",
    "participants": ["claude_code", "codex_cli"],
    "max_turns": 6,
    "budget_usd": 0.50,
    "policy_id": "development_safe",
    "approval_mode": "prompt"
  }'
```

### 3. 실시간 대화 관리

#### A) Claude Code를 통한 코드 분석 요청
```bash
# Claude Code 세션 시작
claude

# TAB를 통해 Codex CLI와 협업 요청
"TAB 시스템을 통해 Codex CLI와 함께 이 Python 함수의 성능을 분석하고 최적화해주세요"
```

#### B) HTTP API를 통한 직접 호출
```bash
# 새 대화 세션 시작
curl -X POST http://localhost:8000/api/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Python 코드 리팩토링",
    "participants": ["claude_code", "codex_cli"],
    "max_turns": 6,
    "budget_usd": 0.50
  }'

# 메시지 전송
curl -X POST http://localhost:8000/api/conversations/{session_id}/message \
  -H "Content-Type: application/json" \
  -d '{
    "content": "이 함수를 최적화해주세요",
    "to_agent": "codex_cli"
  }'
```

### 3. 모니터링 및 관리

#### 시스템 상태 확인
```bash
# 시스템 상태
curl http://localhost:8000/api/status

# 활성 세션 목록
curl http://localhost:8000/api/conversations

# 에이전트 상태
curl http://localhost:8000/api/agents/health
```

#### 로그 확인
```bash
# 애플리케이션 로그
tail -f ~/.tab/logs/orchestrator.log

# 감사 로그
tail -f ~/.tab/logs/audit.jsonl

# 에이전트별 로그
tail -f ~/.tab/logs/agents/claude_code.log
tail -f ~/.tab/logs/agents/codex_cli.log
```

## 실제 사용 시나리오

### 시나리오 1: 코드 리뷰 협업
```python
# 1. TAB 세션 시작
session_id = "code-review-001"

# 2. Claude Code가 초기 분석 수행
claude_analysis = "이 코드에서 잠재적인 버그 3개를 발견했습니다..."

# 3. Codex CLI가 검증 및 테스트 수행
codex_verification = "제시된 버그를 검증하고 수정안을 구현했습니다..."

# 4. 최종 합의 도달
final_solution = "검토 완료: 3개 버그 수정, 성능 15% 향상"
```

### 시나리오 2: 버그 수정 협업
```python
# 1. 버그 보고서 분석
bug_report = "사용자 인증에서 간헐적 실패 발생"

# 2. Claude Code 진단
diagnosis = "경쟁 조건(race condition) 문제로 추정"

# 3. Codex CLI 재현 및 수정
reproduction = "버그 재현 성공, 동기화 로직 추가로 수정"

# 4. 검증 및 배포
validation = "수정 사항 테스트 완료, 프로덕션 배포 준비"
```

## 고급 기능

### 1. 사용자 정의 정책
```yaml
# ~/.tab/config/policies.yaml
custom_policy:
  name: "엄격한 보안 정책"
  permission_mode: "prompt"
  allowed_tools: ["read", "analyze"]
  disallowed_tools: ["write", "delete", "network"]
  resource_limits:
    max_cost_usd: 0.10
    max_time_ms: 60000
```

### 2. 관찰 가능성 설정
```yaml
# ~/.tab/config/config.yaml
observability:
  otlp_endpoint: "http://localhost:4317"
  trace_sampling_ratio: 1.0
  service_name: "tab-production"
```

### 3. 에이전트 커스터마이징
```yaml
agents:
  claude_code:
    command_path: "/usr/local/bin/claude"
    timeout: 120
    capabilities: ["analysis", "debugging", "optimization"]

  codex_cli:
    command_path: "/usr/local/bin/codex"
    timeout: 180
    capabilities: ["implementation", "testing", "deployment"]
```

## 문제 해결

### 일반적인 문제들

1. **에이전트 연결 실패**
   ```bash
   # 에이전트 상태 확인
   curl http://localhost:8000/api/agents/health

   # 에이전트 재시작
   systemctl restart tab-orchestrator
   ```

2. **성능 문제**
   ```bash
   # 메트릭 확인
   curl http://localhost:9090/metrics | grep tab_

   # 로그 분석
   grep "duration_ms" ~/.tab/logs/orchestrator.log
   ```

3. **권한 오류**
   ```bash
   # 정책 검증
   uv run python -m tab.cli.main validate

   # 감사 로그 확인
   grep "permission_denied" ~/.tab/logs/audit.jsonl
   ```

## 다음 단계

1. **프로덕션 배포**: Docker Compose를 사용한 전체 스택 배포
2. **모니터링 설정**: Prometheus + Grafana 대시보드 구성
3. **확장**: 추가 에이전트 통합
4. **자동화**: CI/CD 파이프라인에 TAB 통합