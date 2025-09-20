# PRD: Claude Code × Codex CLI 양방향 Q\&A 브리지

**문서 버전**: v0.1 (2025-09-20)
**제품명(가칭)**: **TAB** — *Twin-Agent Bridge*
**문서 목적**: 두 개의 에이전틱 코딩 CLI(Anthropic **Claude Code**, OpenAI **Codex CLI**)가 **서로에게 질의하고 답변하는** 양방향 대화를 안전하게 오케스트레이션하는 시스템의 제품 요구사항 정의

---

## 0) 한눈에 보는 요약 (TL;DR)

* **핵심 결과물**: ① **오케스트레이터**(Python) ② **MCP(모델 컨텍스트 프로토콜) 상호연결** ③ **감사/관측(OTel) + 보안 샌드박스**
* **모드**

  * **브리지 모드**: 오케스트레이터가 Claude와 Codex를 번갈아 호출해 대화 루프를 이끕니다. Claude는 `-p --output-format stream-json`의 헤드리스 모드가 공식 문서로 보장됩니다.
  * **MCP 상호연동 모드**: Claude를 MCP **서버**로 띄워 Codex의 MCP **클라이언트**가 붙거나(표준은 **stdio** 우선), 필요 시 Codex를 MCP 서버로 띄워 Claude가 클라이언트로 붙습니다. **Codex의 원격(SSE/HTTP) MCP 지원은 현재 제한적**이며 stdio가 안전한 기본값입니다(확실하지 않음: SSE/HTTP 정식지원 여부는 이슈 기반 근거).
* **안전장치**: 권한 승인(permissions), 작업 디렉터리 격리, **rootless 컨테이너 + cap-drop** 권장, 전 과정 \*\*OTel(Traces/Logs/Metrics)\*\*로 가시화.

---

## 1) 배경 & 문제정의

* **배경**: 에이전틱 코딩 CLI가 급속히 보급되며(Claude Code, Codex CLI 등), 각 도구의 강점을 **서로에게 질의/검증**하는 메타-협업 패턴이 필요해졌습니다.

  * Claude Code는 **헤드리스 모드**와 **MCP**를 공식 지원합니다.
  * Codex CLI는 **비대화(Non-interactive/Quiet/Exec) 모드**와 **MCP 서버 연결** 및 \*\*구성 파일(`~/.codex/config.toml`)\*\*을 지원합니다(공식 GitHub). 다만 **exec 모드의 세션 재개(resume) 미지원** 등 일부 제약이 보고되어 있습니다(이슈 근거).
* **문제**: 두 에이전트가 **상호 질의응답**을 안정적으로 주고받으려면

  1. **스트리밍/구조화 출력** 파싱,
  2. **대화 상태·세션 관리**,
  3. **권한·보안 경계**,
  4. **관측/감사**가 필요합니다.

---

## 2) 목표(Goals) / 비목표(Non-goals)

### 2.1 목표

1. **양방향 Q\&A 루프**: Claude↔Codex가 번갈아 질문/답변하며 합의/최종안을 도출 (N-턴 내 수렴).
2. **신뢰성**: 한쪽 실패 시 **리트라이/페일오버**.
3. **안전성**: 각 에이전트의 \*\*권한 승인(Allowed Tools / Approval Modes)\*\*과 파일/명령 실행 경계를 준수.
4. **관측성**: **OpenTelemetry(OTLP)** 기반 **추적/로그/메트릭** 수집.

### 2.2 비목표

* 복수 IDE/플러그인(예: VS Code)과의 UI 통합은 **후속 단계**.
* 클라우드 에이전트(예: Codex Cloud)의 백그라운드 작업 오케스트레이션은 **초기 범위 외**.

---

## 3) 사용자 & 페르소나

* **에이전틱 도구 평가자**: 두 도구의 상호 검증 루프를 PoC로 빠르게 실험.
* **DevInfra/플랫폼 엔지니어**: CI/CD에 안전하게 접목, 감사/관측이 필수.
* **보안/컴플라이언스 팀**: 권한 경계, 무단 네트워크/파일 접근 방지, 감사로그 요구.

---

## 4) 주요 시나리오 (User Stories)

1. **코드 리뷰 교차검증**:

   * Claude가 “이 모듈의 race condition 위험?” → Codex가 검사/증거 제시 → Claude가 반박/보완 후 합의.
2. **버그 재현 & 패치 제안**:

   * Codex가 테스트 재현 → Claude가 패치 범위 축소/리팩터 조언 → Codex가 수정안 PR 초안.
3. **안전한 자동 수정**:

   * 두 에이전트 모두 **권한 승인/제한** 하에서만 파일 쓰기·명령 실행을 수행.

---

## 5) 요구사항

### 5.1 기능 요구사항 (FRD)

* **FR1. 대화 오케스트레이션**

  * Claude **헤드리스**: `claude -p --output-format stream-json` 사용(공식) → JSONL 이벤트 파싱.
  * Codex **비대화 호출**: `codex exec "<프롬프트>"` 또는 `codex proto` 사용.

    * **사실**: `exec` 관련 문서와 이슈 다수 존재, `proto`는 “stdin/stdout 프로토콜 스트림” 헬프가 있으나 **상세 문서 부족(확실하지 않음)**.
  * **세션 관리**:

    * Claude: `--resume`/`--continue`로 세션 지속(공식).
    * Codex: `exec`에서 공식 `--resume` 미지원 보고(이슈 근거) → **오케스트레이터 레벨에서 상태를 유지**하고, Codex의 \*\*세션 로그(JSONL)\*\*를 조합해 컨텍스트를 재주입(워카라운드).
* **FR2. MCP 상호연결(옵션)**

  * **Claude를 MCP 서버로**: `claude mcp serve` 실행(공식).
  * **Codex의 MCP 클라이언트 설정**: `~/.codex/config.toml`에 stdio 서버 추가(예: Snyk 가이드 예시 형식).

    ```toml
    # ~/.codex/config.toml
    [mcp_servers.claude_code]
    command = "claude"
    args = ["mcp", "serve"]   # stdio
    ```
  * **역방향(옵션)**: Codex를 MCP 서버로 띄우는 `codex mcp` 서브커맨드가 **실험적**으로 노출됨(이슈 헬프 출력 근거, 확실하지 않음). Claude 측에서 `claude mcp add`로 **stdio 서버**로 붙일 수 있음.
  * **주요 제약**: Codex의 **SSE/HTTP 원격 MCP 공식 지원은 미흡**하다는 이슈 다수(확실하지 않음, 이슈 기반). stdio 경로를 기본값으로 채택.
* **FR3. 권한/보안 가드레일**

  * Claude: `--allowedTools`, `--permission-mode`, `--disallowedTools`를 통해 액션별 승인 정책 세팅(공식).
  * Codex: **Approval modes**(Suggest/Auto Edit/Full Auto) 존재 — 공식 블로그/문서 언급(일부는 2차 출처, 세부 옵션 문자열은 버전에 따라 상이할 수 있어 “확실하지 않음”).
* **FR4. 관측성/감사**

  * Claude 헤드리스 **JSON/Stream JSON**의 **비용/시간/턴 수** 메타데이터 파싱(공식 예시).
  * Codex는 `$CODEX_HOME/sessions/.../rollout-*.jsonl` 로그가 생성됨(이슈 근거) → 이를 수집·병합해 세션 단위 메트릭/감사 로그로 변환. **stdout JSON 보장은 버전별 차이, 확실하지 않음**.
  * 모든 파이프라인에 **OpenTelemetry OTLP** Exporters 도입(파이썬/노드 공식 문서).

### 5.2 비기능 요구사항 (NFR)

* **신뢰성**: 타임아웃/재시도/부분 실패 격리.
* **성능**: 한 턴 왕복 ≤ X초(조정), 동시 시나리오용 큐/버퍼.
* **보안**:

  * **Rootless Docker** 또는 **Firejail**로 CLI 실행, **cap-drop ALL → 최소 권한 add** 모형 권고(공식 보안 가이드).
  * 네트워크/파일 경계, 민감 폴더 denylist.
* **운영**: 로그 보존/회수 정책, 비정상 루프 차단(턴 수/비용 상한).

---

## 6) 시스템 아키텍처

```
+------------------------------+         +------------------------------+
|   Claude Adapter             |         |   Codex Adapter              |
|  - headless: stream-json     |         |  - exec/proto wrapper        |
|  - MCP client/server (opt.)  |         |  - session JSONL tailer      |
+--------------+---------------+         +---------------+--------------+
               \                                       /
                \                                     /
                 v                                   v
                +---------------------------------------+
                |          Orchestrator (Python)        |
                |  - Turn loop (Claude <-> Codex)       |
                |  - State mgmt (topic, history)        |
                |  - Policy (who-asks-next, stop rule)  |
                |  - Cost/time budget guard             |
                |  - OTel tracing/logging/metrics       |
                +-----------------+---------------------+
                                  |
                                  v
                   +-------------------------------+
                   |   Observability (OTel -> ...) |
                   +-------------------------------+
```

* **Claude Adapter**

  * `claude -p --output-format stream-json [--input-format stream-json]` 파싱. 공식 헤드리스 문서에서 출력 형식/세션/옵션 명시.
* **Codex Adapter**

  * `codex exec "<prompt>"` 표준 출력/종료코드 수집 + **세션 JSONL** 파일 tail & 병합(이슈 근거). `codex proto`는 문서가 빈약(확실하지 않음)하므로 MVP는 **exec+로그 파싱**을 기본값으로.
* **MCP 경로(옵션)**

  * Claude를 MCP 서버(`claude mcp serve`)로 띄우고, Codex에서 stdio MCP 서버로 연결. 역으로 Codex를 MCP 서버로 띄우는 실험적 커맨드는 존재 보고(확실하지 않음).

---

## 7) 기술 스택 선정

* **오케스트레이터**: **Python 3.11+** (asyncio, `subprocess` 스트리밍, Pydantic/TypedDict)

  * 장점: 빠른 PoC, JSONL 파싱·상태기록 용이, OTel SDK 성숙.
* **옵션 래퍼/툴링**: Node.js 20+ (필요 시 MCP/SDK 연동), OpenTelemetry JS Exporters.
* **관측**: OpenTelemetry(OTLP/HTTP 또는 gRPC) → Jaeger/Tempo/Elastic 중 택1(내부 표준에 맞춤).
* **격리 실행**: Rootless Docker 또는 Firejail(선호 OS에 맞춤), `--cap-drop all` 기본.
* **구성 파일**

  * Codex: `~/.codex/config.toml` 내 `mcp_servers` 섹션(공식/벤더 가이드 예시).
  * Claude: `claude mcp add`로 stdio/SSE/HTTP 서버 등록 가능(공식).

---

## 8) 상호작용 규약(프로토콜)

* **메시지 스키마(요지)**

  ```json
  {
    "turn_id": "uuid",
    "from": "claude|codex",
    "to": "codex|claude",
    "role": "user|assistant",
    "content": "string",
    "attachments": [],
    "policy": { "max_turns": 8, "budget_usd": 0.5 }
  }
  ```
* **턴 진행 규칙**

  * 초기질문 발화자 선택(설정).
  * “추가 증거 필요/실행 필요/확신도 낮음” 신호를 읽어 상대에게 바통.
  * **Stop Rule**: (a) 해결책 합의 문장 생성, (b) 턴/비용 초과, (c) 동일 주장 반복 감지.

---

## 9) UX 흐름(CLI 중심)

1. `tab run --repo . --topic "X 버그 원인과 패치 설계"`
2. Orchestrator가 Claude에 1차 질문 → stream-json 수신/파싱.
3. 요지·근거를 Codex에 전달(`exec`) → 결과와 세션 JSONL 취합. (Codex stdout 형식은 버전에 따라 상이 가능, **확실하지 않음**. 세션 로그 파싱이 주채널)
4. 상호 3\~6턴 반복 → 합의 초안 생성.
5. 최종 제안/패치/커밋 메시지 산출(권한 승인 범위 내에서만 수정).

---

## 10) 테스트 전략 & 수용 기준

* **기능 테스트**

  * T1: 4턴 이내 상호요약 + 반박 + 재요약 수렴률 ≥ 80% (샘플 20케이스).
  * T2: 권한 밖 액션 시도 시 **차단/프롬프트** 발생(Claude AllowedTools / Codex Approval mode).
  * T3: Codex 세션 로그(JSONL)로 **최소 (행동타임라인, 최종 결과)** 재구성 성공률 ≥ 95%.
* **성능 테스트**

  * 평균 턴 왕복 시간, 실패 재시도 평균 1회 이하.
* **보안 테스트**

  * 임의 파일/네트워크 접근 시도 → 컨테이너/샌드박스에서 차단 로그 확인.

---

## 11) 운영 & 관측

* **OTel**:

  * Trace: `Turn → Claude Call → Codex Call` 스팬 트리.
  * Metrics: 턴 수, 비용(Claude JSON에 포함), 실패율, 평균 응답시간.
  * Logs: 양측 원본 이벤트(JSON/JSONL) → 수집·적재.
* **대시보드**: “대화 수렴도, 중단 사유(타임아웃/예산초과), 권한 차단 이벤트”.

---

## 12) 보안/프라이버시

* **권한 최소화**: Claude의 `--allowedTools`/`--disallowedTools`, Codex 승인 모드로 쓰기/실행 제한.
* **격리**: Rootless Docker/Firejail + `--cap-drop all` 기본 권고.
* **데이터 보존**: 세션 로그 보존기간/암호화. Codex **ZDR(Zero Data Retention)** 옵션은 리포지토리 문서 존재(세부 조건은 배포/플랜에 따라 **확실하지 않음**).

---

## 13) 단계적 로드맵

* **MVP (2\~3주 가량의 범위 가정, 일정은 외부 요인 따라 변동 가능)**

  1. 오케스트레이터(단일 프로세스) + Claude 헤드리스 + Codex exec 래퍼
  2. 세션/상태 파일 + OTel 최소계측
  3. Rootless/Firejail 템플릿
* **Phase 2**

  * MCP 상호연결(Claude↔Codex stdio) 옵션 제공, 승인 정책 세분화
  * CI/CD 샘플 워크플로
* **Phase 3**

  * 간단 웹 뷰어(대화·로그 타임라인), 다중 에이전트 확장(LangGraph/AG2 연동 검토 — 정보성 참고).

---

## 14) 리스크 & 대응

* **Codex exec의 세션 재개 미지원**: 오케스트레이터로 상태 유지, 세션 로그 재주입. (이슈 기반 사실)
* **Codex의 MCP 원격(SSE/HTTP) 미성숙**: stdio 우선, 필요 시 **프록시/어댑터**. (이슈 기반)
* **무한 루프/자기호출 위험**: 최대 턴/중복 주장 탐지/합의 신호로 종료.
* **권한 오남용**: 기본 read-only, 명령 실행은 명시 승인만 허용.

---

## 15) 오픈 질문(불확실/확인 필요)

1. **Codex `proto`의 정식 프로토콜 스펙/샘플**: 공식 문서 미비(이슈 보고만 확인). *확실하지 않음*.
2. **Codex stdout에 완전한 JSON 스트림 제공 여부**: 버전별 상이 보고. 기본은 **세션 JSONL 수집**으로 가정. *확실하지 않음*.
3. **Codex MCP 서버(`codex mcp`)의 안정성/지원 수준**: 실험적 표기(이슈 헬프 출력). *확실하지 않음*.

---

## 16) 수용 가능한 대안(Design Alternatives)

* **완전 MCP 기반**: Claude와 Codex 모두 MCP 서버/클라이언트로 상호 연결. (현 시점 Codex의 원격 전송 제약으로 **stdio 우선** 권고)
* **LangGraph/AG2로 오케스트레이션 재구성**: 장기적으로 멀티에이전트 워크플로 모델링에 유리(정보성).

---

## 17) 샘플 실행/구성 (참고)

### 17.1 Claude 헤드리스 샘플

```bash
# 한 번성 요청
claude -p "이 리포의 구조를 요약해줘" --output-format stream-json --max-turns 4
# 공식 헤드리스/스트리밍 JSON 모드 근거
# docs: Headless mode / Output Formats / Streaming JSON Output
```

### 17.2 Codex 실행(비대화) + 세션 로그 수집(워카라운드)

```bash
# 비대화 실행(버전별 플래그 차이 있음: 확실하지 않음)
codex exec "테스트 재현 절차를 만들어줘"

# 세션 로그(JSONL) 경로를 찾아 병합/파싱
# (이슈 근거: $CODEX_HOME/sessions/YYYY/MM/DD/rollout-*.jsonl 생성)
```

### 17.3 MCP 상호연결(옵션)

* **Claude를 MCP 서버로**:

```bash
claude mcp serve
```

* **Codex에서 stdio MCP 서버 등록** (`~/.codex/config.toml`)

```toml
[mcp_servers.claude_code]
command = "claude"
args = ["mcp", "serve"]
```

* **Claude에서 외부 MCP 서버 추가(참고)**:

```bash
# stdio 서버 예시
claude mcp add myserver -- npx -y airtable-mcp-server
# 원격 SSE/HTTP 예시
claude mcp add --transport sse linear https://mcp.linear.app/sse
claude mcp add --transport http notion https://mcp.notion.com/mcp
```

---

## 18) 관측/보안 템플릿(요지)

* **OTel(파이썬)**: OTLP 수출자 설정(환경변수 `OTEL_EXPORTER_*`)으로 수집기 또는 백엔드에 전송.
* **컨테이너 격리 예시**:

```bash
docker run --rm --cap-drop=ALL --pids-limit=256 --network=none \
  -v "$PWD:/work:ro" my/tab-runtime:latest \
  bash -lc 'codex exec "..."'
```

(보안 권고 원칙: rootless + cap-drop all)

---

## 19) 성공 지표 (KPIs)

* **수렴률**: N턴 내 합의/최종안 도출 비율
* **정확도**: 교차검증상 상호 모순 최소화
* **안전 이벤트**: 권한 차단 발생 시 정상 차단/로깅 비율
* **비용/시간**: 턴당 평균 비용/지연(Claude 메타데이터 + Codex 로그 기반)

---

## 20) 부록 — 근거/출처 하이라이트

* **Claude 헤드리스/스트림 JSON, CLI 레퍼런스, MCP**: 공식 문서.
* **Codex CLI 공식 리포지토리**: 설치/구성, MCP, 비대화/CI 모드(문서 섹션 존재), `~/.codex/config.toml`. (일부 세부 플래그/동작은 이슈/커뮤니티 근거)
* **Codex exec의 resume 미지원/JSONL 세션 로그**: GitHub 이슈/질문 근거.
* **Codex MCP 전송(원격) 제약**: stdio 우선(이슈 근거, 확실하지 않음).
* **MCP stdio 등록 예시**(Codex): Snyk 공식 가이드.
* **보안 모범 사례**: Rootless Docker, cap-drop all, Firejail.
* **멀티에이전트 오케스트레이션 프레임워크(참고)**: LangGraph/AG2 문서.

---

### 메모 (불확실/확인 예정)

* `codex proto`의 구체 프로토콜/JSON 스키마와 stdout JSON 보장 여부는 **버전/설정에 따라 다를 가능성이 높음** — 현재는 **세션 JSONL 병합 파이프라인**을 신뢰경로로 채택했습니다. *확실하지 않음*.
* Codex의 Approval modes 세부 스위치와 조합은 릴리스에 따라 변동 가능 — **공식 개발자 페이지/릴리스 노트**를 기준으로 구현 시점에 재확인 필요. *확실하지 않음*.

---

원하시면 위 PRD를 기반으로 **초기 구현용 저장소 스캐폴딩**(Python 오케스트레이터, 샘플 파서/파이프라인, OTel 설정, Docker/Firejail 프로필)까지 한 번에 정리해 드리겠습니다.
