# TAB (Twin-Agent Bridge)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**TAB**은 Claude Code와 Codex CLI 같은 AI 에이전트 간의 안전하고 구조화된 대화를 orchestrate하는 시스템입니다. 코드 분석, 버그 재현, 보안 검토 등의 작업에서 여러 AI 에이전트가 협력할 수 있도록 지원합니다.

## 🌟 주요 기능

- **🤖 멀티 에이전트 오케스트레이션**: Claude Code, Codex CLI 등 다양한 AI 에이전트 간 협업
- **🔒 보안 우선 설계**: 샌드박스 실행, 권한 경계, 정책 기반 접근 제어
- **📊 포괄적 관찰성**: OpenTelemetry 기반 추적, 메트릭, 구조화된 로깅
- **🚀 CLI 기반 인터페이스**: 간단하고 직관적인 명령줄 도구
- **📝 감사 추적**: 모든 에이전트 상호작용 및 결정 로그
- **🔄 대화 수렴 감지**: 에이전트 간 합의 도달 자동 감지
- **💰 예산 및 제한 관리**: 비용 제한, 턴 제한, 시간 제한

## 🚀 빠른 시작

### 설치

```bash
# 저장소 클론
git clone https://github.com/tab-project/tab.git
cd tab

# Python 3.11+ 가상환경 생성
python3.11 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -e ".[dev]"

# 또는 uv 사용 (권장)
uv pip install -e ".[dev]"
```

### 기본 설정

```bash
# 설정 디렉토리 생성
mkdir -p ~/.tab/config

# 기본 설정 복사
cp config/default.yaml ~/.tab/config/config.yaml

# 환경 변수 설정
export TAB_CONFIG_PATH=~/.tab/config
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

### 첫 번째 대화 시작

```bash
# 간단한 코드 분석 대화 시작
tab conversation start "이 Python 코드의 보안 취약점을 분석해주세요" \
    --agents claude_code codex_cli \
    --policy default \
    --max-turns 6 \
    --budget 0.50

# 대화 상태 확인
tab conversation list

# 메시지 전송
tab conversation send <session_id> "추가로 성능 최적화 방안도 검토해주세요"
```

## 📖 사용 가이드

### CLI 명령어

#### 대화 관리

```bash
# 새 대화 시작
tab conversation start <topic> [옵션]
    --agents/-a <agent_id>      # 참여 에이전트 (여러 개 가능)
    --policy/-p <policy_id>     # 적용할 정책 (기본값: default)
    --max-turns/-t <number>     # 최대 턴 수 (기본값: 8)
    --budget/-b <amount>        # 최대 비용 (USD, 기본값: 1.0)
    --working-dir/-w <path>     # 작업 디렉토리
    --output-format/-f <format> # 출력 형식 (json/yaml/text)

# 메시지 전송
tab conversation send <session_id> <message> [옵션]
    --to-agent/-t <agent_id>    # 대상 에이전트 (기본값: auto)
    --attach/-a <file_path>     # 첨부 파일 (여러 개 가능)
    --output-format/-f <format> # 출력 형식

# 대화 상태 확인
tab conversation status <session_id> [옵션]
    --include-history           # 대화 기록 포함
    --output-format/-f <format> # 출력 형식

# 대화 목록 조회
tab conversation list [옵션]
    --status <status>           # 상태별 필터 (active/completed/failed/timeout)
    --limit/-l <number>         # 표시할 세션 수 (기본값: 10)
    --output-format/-f <format> # 출력 형식

# 감사 로그 내보내기
tab conversation export <session_id> [옵션]
    --format <format>           # 내보내기 형식 (json/csv/jsonl)
    --output/-o <file_path>     # 출력 파일 경로
    --include-security          # 보안 이벤트 포함
```

#### 에이전트 관리

```bash
# 에이전트 목록 및 상태
tab agent list [옵션]
    --include-capabilities      # 에이전트 기능 포함
    --output-format/-f <format> # 출력 형식

# 에이전트 건강도 체크
tab agent health <agent_id> [옵션]
    --deep-check               # 심층 건강 체크
    --output-format/-f <format> # 출력 형식
```

#### 정책 관리

```bash
# 정책 목록
tab policy list [옵션]
    --output-format/-f <format> # 출력 형식

# 정책 상세 정보
tab policy show <policy_id> [옵션]
    --output-format/-f <format> # 출력 형식
```

#### 시스템 관리

```bash
# 시스템 상태 확인
tab status [옵션]
    --agent-id <agent_id>      # 특정 에이전트 상태

# 설정 검증
tab validate

# 설정 내보내기
tab export-config [옵션]
    --output/-o <file_path>    # 출력 파일 경로
```

### 사용 시나리오

#### 1. 코드 보안 검토

```bash
# 보안 정책으로 코드 검토 대화 시작
tab conversation start "사용자 인증 모듈의 보안 취약점 분석" \
    --agents claude_code codex_cli \
    --policy security_strict \
    --working-dir ./src/auth \
    --max-turns 8 \
    --budget 1.0

# 코드 파일 첨부하여 분석 요청
tab conversation send $SESSION_ID "이 파일들을 분석해주세요" \
    --attach ./src/auth/user_manager.py \
    --attach ./src/auth/session.py
```

#### 2. 버그 재현 및 수정

```bash
# 버그 재현 워크플로우
tab conversation start "데이터 검증 버그 재현 및 수정" \
    --agents codex_cli claude_code \
    --policy development_safe \
    --max-turns 10

# 버그 재현 요청
tab conversation send $SESSION_ID "API 엔드포인트의 데이터 검증 버그를 재현해주세요" \
    --attach ./tests/test_api.py
```

#### 3. 성능 최적화

```bash
# 성능 분석 대화
tab conversation start "알고리즘 성능 최적화 분석" \
    --agents claude_code \
    --policy read_only_strict \
    --max-turns 6

# 대화 진행 상황 모니터링
tab conversation status $SESSION_ID --include-history
```

## ⚙️ 설정

### 기본 설정 파일 (`~/.tab/config/config.yaml`)

```yaml
# 서버 설정
server:
  host: "localhost"
  port: 8000
  workers: 1

# 에이전트 설정
agents:
  claude_code:
    agent_id: "claude_code"
    agent_type: "claude_code"
    name: "Claude Code"
    enabled: true
    command_path: "/usr/local/bin/claude"
    version: "1.0.0"
    capabilities: ["read", "write", "analyze", "review"]

  codex_cli:
    agent_id: "codex_cli"
    agent_type: "codex_cli"
    name: "Codex CLI"
    enabled: true
    command_path: "/usr/local/bin/codex"
    version: "1.0.0"
    capabilities: ["execute", "test", "debug"]

# 정책 설정
policies:
  default:
    policy_id: "default"
    name: "Default Policy"
    description: "Balanced security and functionality"
    permission_mode: "prompt"
    allowed_tools: ["read", "write", "analyze"]
    disallowed_tools: ["delete", "system"]
    resource_limits:
      max_execution_time_ms: 120000
      max_cost_usd: 0.1
      max_memory_mb: 512
    file_access_rules:
      - "allow:/workspace/*"
      - "deny:/system/*"
    sandbox_config:
      enabled: true
      capability_drop: ["ALL"]

  security_strict:
    policy_id: "security_strict"
    name: "Security Strict"
    description: "High security restrictions"
    permission_mode: "prompt"
    allowed_tools: ["read", "analyze"]
    disallowed_tools: ["write", "delete", "execute", "system"]
    resource_limits:
      max_execution_time_ms: 60000
      max_cost_usd: 0.05
    file_access_rules:
      - "allow:/workspace/*"
      - "deny:/*"

# 관찰성 설정
observability:
  service_name: "tab"
  service_version: "1.0.0"
  environment: "development"
  tracing:
    enabled: true
    endpoint: "http://localhost:14268/api/traces"
  metrics:
    enabled: true
    endpoint: "http://localhost:9090"
  logging:
    level: "INFO"
    format: "json"

# 세션 설정
session:
  session_dir: "~/.tab/sessions"
  auto_save: true
  save_interval_seconds: 60
  max_sessions: 1000
  cleanup_after_days: 30
```

### 정책 설정

TAB는 세 가지 사전 정의된 정책을 제공합니다:

- **`default`**: 균형잡힌 보안과 기능성
- **`security_strict`**: 높은 보안 제한 (읽기 전용)
- **`development_safe`**: 개발 환경용 (제한적 쓰기 권한)

### 환경 변수

```bash
# 필수 환경 변수
export TAB_CONFIG_PATH=~/.tab/config          # 설정 파일 경로
export OTEL_EXPORTER_OTLP_ENDPOINT=...        # OpenTelemetry 엔드포인트
export TAB_LOG_LEVEL=INFO                     # 로그 레벨

# 선택적 환경 변수
export TAB_SESSION_DIR=~/.tab/sessions        # 세션 저장 디렉토리
export TAB_CACHE_DIR=~/.tab/cache            # 캐시 디렉토리
export TAB_MAX_CONCURRENT_SESSIONS=10         # 최대 동시 세션 수
```

## 🔒 보안

### 샌드박스 실행

TAB는 모든 에이전트를 Docker 컨테이너에서 실행하여 시스템을 보호합니다:

```bash
# 예시: rootless Docker 설정
docker run --rm \
  --cap-drop=ALL \
  --pids-limit=256 \
  --network=custom-bridge \
  --user 1000:1000 \
  -v "$PWD:/work:ro" \
  tab-runtime:latest
```

### 권한 경계

- **파일 접근**: 화이트리스트 기반 파일 시스템 접근
- **네트워크**: 내부 네트워크만 허용, 외부 접근 차단
- **리소스 제한**: CPU, 메모리, 실행 시간 제한
- **도구 제한**: 정책 기반 도구 사용 제한

### 감사 로깅

모든 에이전트 상호작용이 암호화된 감사 로그에 기록됩니다:

```bash
# 감사 로그 확인
tab conversation export $SESSION_ID --include-security
```

## 📊 모니터링 및 관찰성

### OpenTelemetry 통합

```bash
# Jaeger 시작 (개발용)
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 14268:14268 \
  jaegertracing/all-in-one:latest

# Prometheus 메트릭 확인
curl http://localhost:9090/metrics | grep tab_
```

### 주요 메트릭

- `tab_conversation_duration_seconds`: 대화 지속 시간
- `tab_turn_latency_seconds`: 턴 응답 지연 시간
- `tab_agent_errors_total`: 에이전트 오류 수
- `tab_policy_violations_total`: 정책 위반 수
- `tab_cost_tracking_usd`: 비용 추적

### 로그 구조

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "event_type": "conversation.turn",
  "session_id": "session_123",
  "turn_id": "turn_005",
  "from_agent": "claude_code",
  "to_agent": "codex_cli",
  "cost_usd": 0.02,
  "duration_ms": 1500,
  "trace_id": "abc123..."
}
```

## 🧪 테스트

### 단위 테스트 실행

```bash
# 모든 테스트 실행
pytest tests/ -v

# 특정 테스트 카테고리
pytest tests/unit/ -m unit
pytest tests/integration/ -m integration
pytest tests/contract/ -m contract

# 커버리지 포함
pytest tests/ --cov=src --cov-report=html
```

### 통합 테스트

```bash
# 엔드투엔드 시나리오 테스트
pytest tests/integration/test_code_review_scenario.py
pytest tests/integration/test_bug_reproduction_scenario.py
pytest tests/integration/test_security_scenario.py
pytest tests/integration/test_observability_scenario.py
```

## 🚀 프로덕션 배포

### Docker 배포

```dockerfile
# Dockerfile 예시
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -e .

EXPOSE 8000
CMD ["tab", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

### 환경별 설정

```bash
# 개발 환경
export TAB_ENV=development
tab serve --reload

# 스테이징 환경
export TAB_ENV=staging
tab serve --workers 2

# 프로덕션 환경
export TAB_ENV=production
tab serve --workers 4
```

## 🤝 기여하기

1. 저장소를 포크합니다
2. 기능 브랜치를 생성합니다 (`git checkout -b feature/amazing-feature`)
3. 변경사항을 커밋합니다 (`git commit -m 'Add amazing feature'`)
4. 브랜치에 푸시합니다 (`git push origin feature/amazing-feature`)
5. Pull Request를 생성합니다

### 개발 환경 설정

```bash
# 개발 의존성 설치
pip install -e ".[dev]"

# Pre-commit 훅 설치
pre-commit install

# 코드 품질 검사
black src/ tests/
isort src/ tests/
ruff check src/ tests/
mypy src/
```

## 📝 라이선스

이 프로젝트는 [MIT 라이선스](LICENSE) 하에 배포됩니다.
