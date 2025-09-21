#!/usr/bin/env python3
"""
TAB (Twin-Agent Bridge) - 실제 AI CLI 도구 대화 시스템

실제 Claude Code CLI와 OpenAI Codex CLI를 사용하여
진짜 AI 에이전트들이 서로 대화하는 시스템
"""

import asyncio
import json
import subprocess
import signal
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import tempfile
import os

# TAB 서비스 통합 (T025: structured adapter integration)
from tab.services.claude_code_adapter import ClaudeCodeAdapter
from tab.services.codex_adapter import CodexAdapter
from tab.services.conversation_orchestrator import ConversationOrchestrator
from tab.services.session_manager import SessionManager
from tab.services.policy_enforcer import PolicyEnforcer
from tab.lib.observability import initialize_telemetry, get_tracer
from tab.models.agent_adapter import AgentAdapter, AgentStatus

class RealAISession:
    """실제 AI 대화 세션 - Production-Ready with TAB Services"""

    def __init__(self, session_id: str, topic: str, max_turns: int = 10, budget_usd: float = 1.0,
                 approval_mode: str = "auto", policy_id: str = "default"):
        self.session_id = session_id
        self.topic = topic
        self.status = "active"
        self.created_at = datetime.now()
        self.turns = []
        self.conversation_active = True
        self.user_intervention = False

        # T027: Budget controls and turn limits
        self.max_turns = max_turns
        self.budget_usd = budget_usd
        self.total_cost_usd = 0.0
        self.current_turn = 0

        # T029: Approval mode and permission boundaries
        self.approval_mode = approval_mode  # "auto", "prompt", "deny"
        self.policy_id = policy_id
        self.policy_enforcer = PolicyEnforcer()
        self.pending_approvals = []  # Queue for approval requests

        # T025: Structured adapter integration
        self.claude_adapter = ClaudeCodeAdapter()

        # T026: Initialize CodexAdapter with proper configuration
        from tab.models.agent_adapter import ConnectionConfig, ExecutionLimits, AgentType

        codex_config = AgentAdapter(
            agent_id="codex_cli_real_tab",
            agent_type=AgentType.CODEX_CLI,
            name="Codex CLI for Real TAB",
            version="1.0.0",
            connection_config=ConnectionConfig(
                type="cli",
                endpoint="codex",
                timeout_seconds=180,
                retry_attempts=2
            ),
            execution_limits=ExecutionLimits(
                max_execution_time_seconds=180,
                max_cost_usd=budget_usd,
                max_memory_mb=512,
                max_concurrent_requests=1
            )
        )
        self.codex_adapter = CodexAdapter(codex_config)

        # T028: OpenTelemetry integration
        self.tracer = get_tracer(__name__)

        # 각 에이전트의 대화 컨텍스트 관리
        self.claude_context = []
        self.codex_context = []

    def add_turn(self, from_agent: str, to_agent: str, content: str, metadata: Dict = None):
        turn_id = f"turn-{len(self.turns) + 1:03d}"
        metadata = metadata or {}

        # T027: Budget tracking
        if "cost_usd" in metadata:
            self.total_cost_usd += metadata["cost_usd"]

        turn = {
            "turn_id": turn_id,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata
        }
        self.turns.append(turn)
        self.current_turn += 1

        # 컨텍스트 업데이트
        if from_agent == "claude_code":
            self.claude_context.append(f"나: {content}")
            self.codex_context.append(f"Claude Code: {content}")
        elif from_agent == "codex_cli":
            self.codex_context.append(f"나: {content}")
            self.claude_context.append(f"Codex CLI: {content}")

    def check_budget_limits(self) -> bool:
        """T027: Check if budget and turn limits are within bounds"""
        if self.current_turn >= self.max_turns:
            print(f"⚠️ 턴 제한 도달: {self.current_turn}/{self.max_turns}")
            return False

        if self.total_cost_usd >= self.budget_usd:
            print(f"⚠️ 예산 제한 도달: ${self.total_cost_usd:.4f}/${self.budget_usd}")
            return False

        return True

    def get_context_for_agent(self, agent_id: str) -> str:
        """에이전트용 컨텍스트 문자열 생성"""
        if agent_id == "claude_code":
            context = self.claude_context[-5:]  # 최근 5개 대화만
        else:
            context = self.codex_context[-5:]

        context_str = "\n".join(context) if context else ""
        return context_str

    def should_continue_conversation(self) -> bool:
        """대화 계속 여부 결정"""
        if self.user_intervention:
            return False
        return self.conversation_active

    def validate_agent_call(self, agent_name: str, content: str) -> Dict[str, Any]:
        """T029: Validate agent call against policy before execution"""
        validation_result = {
            "allowed": True,
            "reason": "",
            "requires_approval": False,
            "action_required": "none"
        }

        # Check if agent calls are allowed by policy
        tool_validation = self.policy_enforcer.validate_tool_usage(
            self.policy_id, f"agent_call_{agent_name}", self.session_id
        )

        if not tool_validation["allowed"]:
            validation_result.update({
                "allowed": False,
                "reason": tool_validation["reason"],
                "action_required": "block"
            })
            return validation_result

        # Check approval mode requirements
        if self.approval_mode == "prompt":
            validation_result.update({
                "requires_approval": True,
                "reason": "Approval mode requires user confirmation for agent calls"
            })
        elif self.approval_mode == "deny":
            validation_result.update({
                "allowed": False,
                "reason": "Approval mode is set to deny all agent calls",
                "action_required": "block"
            })

        return validation_result

    async def request_approval(self, action: str, details: Dict[str, Any]) -> bool:
        """T029: Request user approval for sensitive operations"""
        if self.approval_mode != "prompt":
            return self.approval_mode == "auto"

        print(f"\n🔒 승인 요청 - {action}")
        print(f"   세부사항: {details}")
        print(f"   정책 ID: {self.policy_id}")
        print(f"   세션 ID: {self.session_id}")

        while True:
            try:
                choice = input("\n승인하시겠습니까? (y/n/d=세부정보): ").strip().lower()

                if choice == 'y':
                    print("✅ 승인됨")
                    return True
                elif choice == 'n':
                    print("❌ 거부됨")
                    return False
                elif choice == 'd':
                    print(f"\n📋 세부 정보:")
                    for key, value in details.items():
                        print(f"   {key}: {value}")
                    continue
                else:
                    print("y(승인), n(거부), d(세부정보)를 입력하세요.")

            except KeyboardInterrupt:
                print("\n❌ 승인 취소됨")
                return False

    def check_permission_boundaries(self, operation: str, target: str) -> Dict[str, Any]:
        """T029: Check permission boundaries for specific operations"""
        # Validate file access if operation involves files
        if operation in ["file_read", "file_write", "file_execute"]:
            return self.policy_enforcer.validate_file_access(
                self.policy_id, target, operation.split("_")[1], self.session_id
            )

        # Validate network access
        elif operation == "network_access":
            host, port = target.split(":") if ":" in target else (target, 80)
            return self.policy_enforcer.validate_network_access(
                self.policy_id, host, int(port), self.session_id
            )

        # Validate tool usage
        elif operation == "tool_usage":
            return self.policy_enforcer.validate_tool_usage(
                self.policy_id, target, self.session_id
            )

        return {"allowed": True, "reason": "No specific boundary check needed"}

class RealAITAB:
    """실제 AI CLI 도구를 사용하는 TAB 오케스트레이터"""

    def __init__(self):
        self.session: Optional[RealAISession] = None
        self.is_paused = False

        # CLI 도구 설정
        self.claude_cli = "claude"
        self.codex_cli = "codex"

        # 신호 처리
        signal.signal(signal.SIGINT, self.handle_interrupt)

    def handle_interrupt(self, signum, frame):
        """Ctrl+C 처리"""
        self.is_paused = True
        print(f"\n\n⏸️  대화가 일시 중단되었습니다.")

    def print_header(self):
        """헤더 출력"""
        print("\n" + "="*80)
        print("🤖 TAB 실제 AI 대화 시스템 (Real AI Agent Conversation)")
        print("="*80)
        print("실제 Claude Code CLI와 OpenAI Codex CLI가 서로 대화합니다!")
        print("Ctrl+C로 언제든 개입 가능합니다.")
        print()

    def setup_conversation(self):
        """대화 설정 with policy and approval mode configuration (T029)"""
        print("🚀 실제 AI 에이전트 대화 세션을 시작합니다!")
        print()

        # CLI 도구 확인
        if not self.check_cli_tools():
            print("❌ 필요한 CLI 도구가 설치되지 않았습니다.")
            return None

        # 주제 입력
        topic = input("💭 AI 에이전트들이 논의할 주제를 입력하세요: ").strip()
        if not topic:
            topic = "프로그래밍 관련 기술적 토론"

        # T029: Security and approval configuration
        print(f"\n🔒 보안 및 승인 설정:")
        print(f"   1. auto   - 자동 승인 (빠른 대화)")
        print(f"   2. prompt - 사용자 승인 필요 (안전한 대화)")
        print(f"   3. deny   - 모든 요청 거부 (테스트 모드)")

        approval_mode = input("승인 모드를 선택하세요 (1-3, 기본값: 1): ").strip()
        approval_modes = {"1": "auto", "2": "prompt", "3": "deny", "": "auto"}
        approval_mode = approval_modes.get(approval_mode, "auto")

        print(f"\n🛡️  보안 정책 선택:")
        print(f"   1. default          - 기본 개발 정책")
        print(f"   2. read_only_strict - 읽기 전용 엄격")
        print(f"   3. development_safe - 개발 안전 모드")

        policy_choice = input("보안 정책을 선택하세요 (1-3, 기본값: 1): ").strip()
        policy_ids = {"1": "default", "2": "read_only_strict", "3": "development_safe", "": "default"}
        policy_id = policy_ids.get(policy_choice, "default")

        # Budget and turn limits
        print(f"\n💰 예산 및 제한 설정:")
        budget_input = input("최대 예산 (USD, 기본값: 1.0): ").strip()
        budget_usd = float(budget_input) if budget_input else 1.0

        turns_input = input("최대 턴 수 (기본값: 10): ").strip()
        max_turns = int(turns_input) if turns_input else 10

        print(f"\n✅ 대화 설정 완료:")
        print(f"   📝 주제: {topic}")
        print(f"   🤖 참여 에이전트: Claude Code, Codex CLI")
        print(f"   🔒 승인 모드: {approval_mode}")
        print(f"   🛡️  보안 정책: {policy_id}")
        print(f"   💰 예산: ${budget_usd}")
        print(f"   🔄 최대 턴: {max_turns}")
        print(f"   🛑 중단: Ctrl+C로 언제든 개입 가능")

        # 세션 생성
        session_id = f"real-ai-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.session = RealAISession(session_id, topic, max_turns, budget_usd, approval_mode, policy_id)

        return session_id

    def check_cli_tools(self) -> bool:
        """CLI 도구 설치 확인"""
        print("🔍 CLI 도구 확인 중...")

        try:
            # Claude CLI 확인
            result = subprocess.run([self.claude_cli, "--version"],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"   ✅ Claude Code CLI: 설치됨")
            else:
                print(f"   ❌ Claude Code CLI: 실행 실패")
                return False
        except Exception as e:
            print(f"   ❌ Claude Code CLI: 설치되지 않음 ({e})")
            return False

        try:
            # Codex CLI 확인
            result = subprocess.run([self.codex_cli, "--version"],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"   ✅ Codex CLI: 설치됨")
            else:
                print(f"   ❌ Codex CLI: 실행 실패")
                return False
        except Exception as e:
            print(f"   ❌ Codex CLI: 설치되지 않음 ({e})")
            return False

        return True

    async def call_claude_code(self, prompt: str, context: str = "") -> Tuple[str, Dict]:
        """Claude Code CLI 호출 with policy enforcement (T029)"""
        print(f"🤖 Claude Code가 응답 준비 중...")

        # T029: Validate agent call against policy
        validation = self.session.validate_agent_call("claude_code", prompt)
        if not validation["allowed"]:
            error_msg = f"🚫 Claude Code 호출이 정책에 의해 차단됨: {validation['reason']}"
            print(error_msg)
            return error_msg, {"success": False, "error": "policy_violation", "policy_reason": validation["reason"]}

        # T029: Request approval if needed
        if validation.get("requires_approval", False):
            approval_details = {
                "agent": "claude_code",
                "action": "AI agent call",
                "prompt_length": len(prompt),
                "context_length": len(context),
                "session_turn": self.session.current_turn
            }

            approved = await self.session.request_approval("Claude Code 에이전트 호출", approval_details)
            if not approved:
                error_msg = "🚫 Claude Code 호출이 사용자에 의해 거부됨"
                print(error_msg)
                return error_msg, {"success": False, "error": "user_denied"}

        # 컨텍스트와 함께 프롬프트 구성
        full_prompt = f"""TAB 시스템에서 Codex CLI와 대화하고 있습니다.

주제: {self.session.topic}

이전 대화:
{context}

현재 메시지: {prompt}

위 내용에 대해 기술적이고 구체적으로 응답해주세요. Codex CLI와 건설적인 토론을 이어가세요."""

        try:
            # 긴 프롬프트를 임시 파일에 저장
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(full_prompt)
                temp_file_path = temp_file.name

            try:
                # Claude CLI 실행 (파일 경로로 전달)
                start_time = time.time()
                result = subprocess.run([
                    self.claude_cli,
                    f"@{temp_file_path}",
                    "--print"
                ], capture_output=True, text=True, timeout=10800)
            finally:
                # 임시 파일 삭제
                os.unlink(temp_file_path)

            duration = time.time() - start_time

            if result.returncode == 0:
                # 단순 텍스트 응답 처리
                response = result.stdout.strip()

                metadata = {
                    "duration_seconds": round(duration, 2),
                    "success": True,
                    "cli": "claude"
                }
                return response, metadata
            else:
                error_msg = f"Claude 응답 오류: {result.stderr}"
                print(f"❌ {error_msg}")
                metadata = {
                    "duration_seconds": round(duration, 2),
                    "success": False,
                    "error": error_msg,
                    "cli": "claude"
                }
                return f"[오류] Claude Code에서 응답을 생성할 수 없습니다.", metadata

        except subprocess.TimeoutExpired:
            return "[오류] Claude Code 응답 시간 초과", {"success": False, "error": "timeout"}
        except Exception as e:
            return f"[오류] Claude Code 호출 실패: {e}", {"success": False, "error": str(e)}

    async def call_codex_cli(self, prompt: str, context: str = "") -> Tuple[str, Dict]:
        """Codex CLI 호출 with JSONL session log parsing (T026) and policy enforcement (T029)"""
        print(f"🤖 Codex CLI가 응답 준비 중...")

        # T029: Validate agent call against policy
        validation = self.session.validate_agent_call("codex_cli", prompt)
        if not validation["allowed"]:
            error_msg = f"🚫 Codex CLI 호출이 정책에 의해 차단됨: {validation['reason']}"
            print(error_msg)
            return error_msg, {"success": False, "error": "policy_violation", "policy_reason": validation["reason"]}

        # T029: Request approval if needed
        if validation.get("requires_approval", False):
            approval_details = {
                "agent": "codex_cli",
                "action": "AI agent call",
                "prompt_length": len(prompt),
                "context_length": len(context),
                "session_turn": self.session.current_turn,
                "budget_remaining": self.session.budget_usd - self.session.total_cost_usd
            }

            approved = await self.session.request_approval("Codex CLI 에이전트 호출", approval_details)
            if not approved:
                error_msg = "🚫 Codex CLI 호출이 사용자에 의해 거부됨"
                print(error_msg)
                return error_msg, {"success": False, "error": "user_denied"}

        # T026: Use CodexAdapter for structured session log parsing
        try:
            # Prepare context for adapter
            conversation_history = []
            for turn in self.session.turns[-3:]:  # Last 3 turns for context
                conversation_history.append({
                    "role": "assistant" if turn["from_agent"] != "user" else "user",
                    "content": turn["content"],
                    "from_agent": turn["from_agent"],
                    "timestamp": turn["timestamp"]
                })

            adapter_context = {
                "conversation_history": conversation_history,
                "working_directory": os.getcwd(),
                "session_metadata": {
                    "session_id": self.session.session_id,
                    "topic": self.session.topic,
                    "turn_number": self.session.current_turn
                }
            }

            # Prepare constraints
            constraints = {
                "max_execution_time_ms": 180000,  # 3 minutes
                "max_cost_usd": min(0.1, self.session.budget_usd - self.session.total_cost_usd),
                "permission_mode": "auto",  # For autonomous conversation
                "allowed_tools": [],  # Let Codex decide
                "disallowed_tools": []
            }

            # Format prompt with TAB context
            full_prompt = f"""TAB 시스템에서 Claude Code와 대화하고 있습니다.

주제: {self.session.topic}

이전 대화:
{context}

현재 메시지: {prompt}

위 내용에 대해 실용적이고 구현 중심적으로 응답해주세요. Claude Code와 건설적인 토론을 이어가세요."""

            # Use CodexAdapter for structured processing
            request_id = f"codex-{self.session.session_id}-{self.session.current_turn}"
            response = await self.codex_adapter.process_request(
                request_id=request_id,
                content=full_prompt,
                context=adapter_context,
                constraints=constraints
            )

            # Convert adapter response to real_ai_tab format
            if response.status == "completed":
                metadata = {
                    "duration_seconds": response.execution_time_ms / 1000,
                    "success": True,
                    "cli": "codex",
                    "cost_usd": response.cost_usd,
                    "tokens_used": response.tokens_used,
                    "tools_used": response.tools_used,
                    "files_accessed": response.files_accessed,
                    "reasoning": response.reasoning,
                    "confidence": response.confidence
                }
                return response.content, metadata
            else:
                # Handle failed response
                error_msg = f"Codex 처리 오류: {response.error_details}"
                print(f"❌ {error_msg}")
                metadata = {
                    "duration_seconds": response.execution_time_ms / 1000 if response.execution_time_ms else 0,
                    "success": False,
                    "error": error_msg,
                    "cli": "codex"
                }
                return f"[오류] Codex CLI에서 응답을 생성할 수 없습니다: {response.error_details}", metadata

        except Exception as e:
            # Fallback to original implementation for compatibility
            print(f"⚠️ CodexAdapter 사용 실패, 기본 구현으로 폴백: {e}")
            return await self._call_codex_cli_fallback(prompt, context)

    async def _call_codex_cli_fallback(self, prompt: str, context: str = "") -> Tuple[str, Dict]:
        """Fallback implementation for Codex CLI calls"""
        # 컨텍스트와 함께 프롬프트 구성
        full_prompt = f"""TAB 시스템에서 Claude Code와 대화하고 있습니다.

주제: {self.session.topic}

이전 대화:
{context}

현재 메시지: {prompt}

위 내용에 대해 실용적이고 구현 중심적으로 응답해주세요. Claude Code와 건설적인 토론을 이어가세요."""

        try:
            # 긴 프롬프트를 임시 파일에 저장
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(full_prompt)
                temp_file_path = temp_file.name

            try:
                # Codex CLI 실행 (exec 모드로 비대화형 실행)
                start_time = time.time()
                result = subprocess.run([
                    self.codex_cli, "exec",
                    f"@{temp_file_path}"
                ], capture_output=True, text=True, timeout=10800)
            finally:
                # 임시 파일 삭제
                os.unlink(temp_file_path)

            duration = time.time() - start_time

            if result.returncode == 0:
                response = result.stdout.strip()

                # 불필요한 출력 정리
                if "Codex CLI" in response or "Session ID" in response:
                    lines = response.split('\n')
                    cleaned_lines = []
                    for line in lines:
                        if not any(skip in line.lower() for skip in
                                 ['codex cli', 'session id', 'working directory']):
                            cleaned_lines.append(line)
                    response = '\n'.join(cleaned_lines).strip()

                metadata = {
                    "duration_seconds": round(duration, 2),
                    "success": True,
                    "cli": "codex"
                }
                return response, metadata
            else:
                error_msg = f"Codex 응답 오류: {result.stderr}"
                print(f"❌ {error_msg}")
                metadata = {
                    "duration_seconds": round(duration, 2),
                    "success": False,
                    "error": error_msg,
                    "cli": "codex"
                }
                return f"[오류] Codex CLI에서 응답을 생성할 수 없습니다.", metadata

        except subprocess.TimeoutExpired:
            return "[오류] Codex CLI 응답 시간 초과", {"success": False, "error": "timeout"}
        except Exception as e:
            return f"[오류] Codex CLI 호출 실패: {e}", {"success": False, "error": str(e)}

    async def run_ai_conversation(self):
        """실제 AI 대화 실행"""
        if not self.session:
            print("❌ 세션이 설정되지 않았습니다.")
            return

        print(f"\n🔄 실제 AI 대화를 시작합니다...")
        print(f"📝 주제: {self.topic}")
        print(f"=" * 80)

        # 첫 번째 에이전트로 Claude Code 시작
        current_speaker = "claude_code"
        initial_prompt = f"다음 주제에 대해 Codex CLI와 기술적 토론을 시작해주세요: {self.session.topic}"

        turn_count = 0

        while self.session.should_continue_conversation() and not self.is_paused:
            turn_count += 1

            if current_speaker == "claude_code":
                next_speaker = "codex_cli"
                context = self.session.get_context_for_agent("claude_code")

                if turn_count == 1:
                    prompt = initial_prompt
                else:
                    # 이전 Codex 응답에 대한 반응
                    last_turn = self.session.turns[-1]
                    prompt = last_turn['content']

                response, metadata = await self.call_claude_code(prompt, context)

            else:  # codex_cli
                next_speaker = "claude_code"
                context = self.session.get_context_for_agent("codex_cli")

                # 이전 Claude 응답에 대한 반응
                last_turn = self.session.turns[-1]
                prompt = last_turn['content']

                response, metadata = await self.call_codex_cli(prompt, context)

            # 턴 추가
            turn = self.session.add_turn(current_speaker, next_speaker, response, metadata)

            # 출력
            agent_name = "Claude Code" if current_speaker == "claude_code" else "Codex CLI"
            success_indicator = "✅" if metadata.get("success", True) else "❌"
            duration = metadata.get("duration_seconds", 0)

            print(f"\n💬 턴 {turn_count} - {agent_name} {success_indicator} ({duration}초):")
            print(f"━" * 60)
            print(response)
            print(f"━" * 60)
            print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")

            # 다음 발언자로 변경
            current_speaker = next_speaker

            # 잠시 대기 (API 부하 방지)
            await asyncio.sleep(3)

            # 일시 중단 체크
            if self.is_paused:
                await self.handle_user_intervention()
                if not self.session.conversation_active:
                    break

        # 대화 종료
        await self.end_conversation()

    async def handle_user_intervention(self):
        """사용자 개입 처리"""
        while self.is_paused:
            print(f"\n⚙️  사용자 개입 모드")
            print(f"   c: 대화 계속")
            print(f"   i: 메시지 추가")
            print(f"   s: 상태 확인")
            print(f"   h: 대화 기록")
            print(f"   p: 정책 상태 확인 (T029)")
            print(f"   a: 승인 모드 변경 (T029)")
            print(f"   m: 대화 요약 후 종료")
            print(f"   q: 즉시 종료")

            try:
                choice = input("\n선택하세요: ").strip().lower()

                if choice == 'c':
                    print(f"▶️  대화를 계속 진행합니다...")
                    self.is_paused = False

                elif choice == 'i':
                    message = input("💭 AI 에이전트들에게 전달할 메시지: ").strip()
                    if message:
                        self.session.add_turn("user", "both", f"[사용자 개입] {message}")
                        print(f"✅ 메시지가 추가되었습니다.")
                        self.is_paused = False

                elif choice == 's':
                    print(f"\n📊 현재 세션 상태:")
                    print(f"   📝 주제: {self.topic}")
                    print(f"   🔄 턴 수: {len(self.session.turns)}")
                    print(f"   ⏰ 경과 시간: {datetime.now() - self.session.created_at}")

                elif choice == 'h':
                    print(f"\n📜 최근 대화 기록:")
                    recent_turns = self.session.turns[-3:]
                    for turn in recent_turns:
                        agent_name = "Claude Code" if turn['from_agent'] == "claude_code" else "Codex CLI"
                        success = "✅" if turn['metadata'].get('success', True) else "❌"
                        print(f"   {agent_name} {success}: {turn['content'][:100]}...")

                # T029: Policy status check
                elif choice == 'p':
                    print(f"\n🛡️  현재 정책 상태:")
                    print(f"   정책 ID: {self.session.policy_id}")
                    print(f"   승인 모드: {self.session.approval_mode}")
                    print(f"   대기 중인 승인: {len(self.session.pending_approvals)}")

                    policy = self.session.policy_enforcer.get_policy(self.session.policy_id)
                    if policy:
                        print(f"   정책 이름: {policy.name}")
                        print(f"   허용된 도구: {', '.join(policy.allowed_tools[:5])}{'...' if len(policy.allowed_tools) > 5 else ''}")
                        print(f"   금지된 도구: {', '.join(policy.disallowed_tools[:3])}{'...' if len(policy.disallowed_tools) > 3 else ''}")
                        print(f"   권한 모드: {policy.permission_mode}")

                # T029: Change approval mode
                elif choice == 'a':
                    print(f"\n🔒 승인 모드 변경:")
                    print(f"   현재: {self.session.approval_mode}")
                    print(f"   1. auto   - 자동 승인")
                    print(f"   2. prompt - 사용자 승인 필요")
                    print(f"   3. deny   - 모든 요청 거부")

                    new_mode = input("새 모드 선택 (1-3): ").strip()
                    mode_map = {"1": "auto", "2": "prompt", "3": "deny"}

                    if new_mode in mode_map:
                        old_mode = self.session.approval_mode
                        self.session.approval_mode = mode_map[new_mode]
                        print(f"✅ 승인 모드가 {old_mode} → {self.session.approval_mode}로 변경되었습니다.")
                    else:
                        print("❌ 잘못된 선택입니다.")

                elif choice == 'm':
                    print(f"📝 대화 요약을 생성한 후 세션을 종료합니다...")
                    await self.generate_conversation_summary()
                    self.session.conversation_active = False
                    self.is_paused = False

                elif choice == 'q':
                    print(f"🛑 대화를 즉시 종료합니다.")
                    self.session.conversation_active = False
                    self.is_paused = False

            except KeyboardInterrupt:
                print(f"\n🛑 강제 종료합니다.")
                self.session.conversation_active = False
                self.is_paused = False

    async def generate_conversation_summary(self):
        """대화 요약 생성"""
        if not self.session or not self.session.turns:
            print("❌ 요약할 대화가 없습니다.")
            return

        print(f"📝 대화 요약을 생성 중...")

        # 전체 대화 내용 수집
        conversation_text = []
        conversation_text.append(f"주제: {self.topic}")
        conversation_text.append(f"세션 ID: {self.session.session_id}")
        conversation_text.append(f"시작 시간: {self.session.created_at}")
        conversation_text.append(f"총 턴 수: {len(self.session.turns)}")
        conversation_text.append("\n" + "="*80)
        conversation_text.append("대화 내용:")
        conversation_text.append("="*80)

        for i, turn in enumerate(self.session.turns, 1):
            agent_name = "Claude Code" if turn['from_agent'] == "claude_code" else turn['from_agent'].title()
            timestamp = turn['timestamp']
            success = "✅" if turn['metadata'].get('success', True) else "❌"
            duration = turn['metadata'].get('duration_seconds', 0)

            conversation_text.append(f"\n턴 {i} - {agent_name} {success} ({duration}초)")
            conversation_text.append(f"시간: {timestamp}")
            conversation_text.append("-" * 60)
            conversation_text.append(turn['content'])
            conversation_text.append("-" * 60)

        full_conversation = "\n".join(conversation_text)

        # 요약 요청 프롬프트 생성
        summary_prompt = f"""다음은 TAB 시스템에서 진행된 AI 에이전트 간 대화입니다. 이 대화를 요약해주세요.

{full_conversation}

다음 형식으로 요약해주세요:
1. 대화 주제와 핵심 논점
2. 주요 기술적 내용과 결론
3. 각 에이전트의 주요 기여사항
4. 향후 발전 방향이나 제안사항

요약은 간결하면서도 핵심 내용을 포함해야 합니다."""

        # 마지막 발언자가 아닌 에이전트에게 요약 요청
        last_turn = self.session.turns[-1] if self.session.turns else None
        if last_turn and last_turn['from_agent'] == "claude_code":
            summary_agent = "codex_cli"
            summary_function = self.call_codex_cli
        else:
            summary_agent = "claude_code"
            summary_function = self.call_claude_code

        print(f"🤖 {summary_agent.replace('_', ' ').title()}에게 요약을 요청합니다...")

        # 요약 생성
        summary_response, metadata = await summary_function(summary_prompt, "")

        # 요약을 턴으로 추가
        self.session.add_turn(summary_agent, "user", summary_response, metadata)

        # 요약 파일 저장
        summary_filename = f"conversation_summary_{self.session.session_id}.md"

        try:
            with open(summary_filename, 'w', encoding='utf-8') as f:
                f.write(f"# TAB 대화 요약\n\n")
                f.write(f"**세션 ID**: {self.session.session_id}\n")
                f.write(f"**주제**: {self.session.topic}\n")
                f.write(f"**생성 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**요약 생성자**: {summary_agent.replace('_', ' ').title()}\n\n")
                f.write("## 요약 내용\n\n")
                f.write(summary_response)
                f.write(f"\n\n## 대화 통계\n\n")
                f.write(f"- 총 턴 수: {len(self.session.turns)}\n")
                successful_turns = sum(1 for turn in self.session.turns if turn['metadata'].get('success', True))
                f.write(f"- 성공한 턴: {successful_turns}\n")
                total_duration = sum(turn['metadata'].get('duration_seconds', 0) for turn in self.session.turns)
                f.write(f"- 총 AI 응답 시간: {total_duration:.1f}초\n")
                f.write(f"- 세션 지속 시간: {datetime.now() - self.session.created_at}\n")

            print(f"✅ 대화 요약이 '{summary_filename}' 파일로 저장되었습니다.")

            # 요약 내용 화면에도 출력
            print(f"\n📋 생성된 요약:")
            print("=" * 80)
            print(summary_response)
            print("=" * 80)

        except Exception as e:
            print(f"❌ 요약 파일 저장 실패: {e}")

    async def end_conversation(self):
        """대화 종료 처리"""
        print(f"\n" + "="*80)
        print(f"✅ 실제 AI 대화가 완료되었습니다!")
        print(f"="*80)

        if self.session:
            successful_turns = sum(1 for turn in self.session.turns
                                 if turn['metadata'].get('success', True))
            total_duration = sum(turn['metadata'].get('duration_seconds', 0)
                               for turn in self.session.turns)

            print(f"📊 대화 통계:")
            print(f"   📝 주제: {self.topic}")
            print(f"   🔄 총 턴 수: {len(self.session.turns)}")
            print(f"   ✅ 성공한 턴: {successful_turns}")
            print(f"   ⏱️  총 AI 응답 시간: {total_duration:.1f}초")
            print(f"   ⏰ 전체 세션 시간: {datetime.now() - self.session.created_at}")

async def main():
    """메인 함수"""
    tab = RealAITAB()
    tab.print_header()

    try:
        session_id = tab.setup_conversation()
        if session_id:
            await tab.run_ai_conversation()
    except KeyboardInterrupt:
        print(f"\n👋 사용자에 의해 프로그램이 종료되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n👋 프로그램이 종료되었습니다.")
    except Exception as e:
        print(f"❌ 치명적 오류: {e}")
        sys.exit(1)