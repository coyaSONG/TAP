"""Codex CLI agent adapter with exec mode integration."""

import asyncio
import json
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import tempfile
import os
import glob
from pathlib import Path

from tab.services.base_agent_adapter import BaseAgentAdapter, AgentResponse, ProcessingStatus
from tab.models.agent_adapter import AgentAdapter, AgentStatus


class CodexAdapter(BaseAgentAdapter):
    """Agent adapter for Codex CLI with exec mode support."""

    def __init__(self, agent_config: AgentAdapter):
        """Initialize Codex adapter.

        Args:
            agent_config: Agent configuration
        """
        super().__init__(agent_config)
        self._session_logs: Dict[str, List[str]] = {}  # session_id -> log_files mapping

    async def process_request(
        self,
        request_id: str,
        content: str,
        context: Dict[str, Any],
        constraints: Dict[str, Any]
    ) -> AgentResponse:
        """Process a request using Codex CLI.

        Args:
            request_id: Unique request identifier
            content: Request content to process
            context: Conversation context and metadata
            constraints: Policy constraints and limits

        Returns:
            AgentResponse with processing results
        """
        start_time = datetime.now(timezone.utc)
        self._status = ProcessingStatus.PROCESSING

        try:
            # Validate constraints
            violations = self._validate_constraints(constraints)
            if violations:
                return AgentResponse(
                    request_id=request_id,
                    status="failed",
                    content=f"Constraint violations: {', '.join(violations)}",
                    error_details="Policy constraint validation failed"
                )

            # Build Codex command
            command = await self._build_command(content, context, constraints)

            # Execute with timeout
            timeout_ms = constraints.get('max_execution_time_ms', 180000)  # Codex default: 3 minutes
            timeout_seconds = timeout_ms / 1000

            result = await self._execute_with_timeout(
                self._execute_codex_command(command, context),
                timeout_seconds,
                request_id
            )

            # Parse response from session logs
            response_content, metadata = await self._parse_codex_response(result, context)

            # Calculate execution time and cost
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            cost_usd = metadata.get('cost_usd', 0.0)
            tokens_used = metadata.get('tokens_used', 0)

            # Extract convergence signals
            convergence_signals = self._extract_convergence_signals(response_content, metadata)

            self._status = ProcessingStatus.IDLE

            return AgentResponse(
                request_id=request_id,
                status="completed",
                content=response_content,
                reasoning=metadata.get('reasoning', ''),
                confidence=metadata.get('confidence', 0.75),
                next_action_suggested=metadata.get('next_action', ''),
                evidence=metadata.get('evidence', []),
                execution_time_ms=int(execution_time),
                cost_usd=cost_usd,
                tokens_used=tokens_used,
                tools_used=metadata.get('tools_used', []),
                files_accessed=metadata.get('files_accessed', []),
                convergence_signals=convergence_signals
            )

        except asyncio.TimeoutError:
            self._status = ProcessingStatus.TIMEOUT
            return AgentResponse(
                request_id=request_id,
                status="timeout",
                content="Request timed out",
                error_details=f"Execution exceeded {timeout_seconds}s limit"
            )

        except Exception as e:
            self._status = ProcessingStatus.ERROR
            self.logger.error(f"Codex CLI execution failed: {str(e)}")
            return AgentResponse(
                request_id=request_id,
                status="failed",
                content=f"Execution failed: {str(e)}",
                error_details=str(e)
            )

    async def _build_command(
        self,
        content: str,
        context: Dict[str, Any],
        constraints: Dict[str, Any]
    ) -> List[str]:
        """Build Codex CLI command with appropriate options.

        Args:
            content: Request content
            context: Conversation context
            constraints: Policy constraints

        Returns:
            Command arguments list
        """
        command = ["codex", "exec"]

        # Approval mode from constraints
        permission_mode = constraints.get('permission_mode', 'prompt')
        if permission_mode == 'auto':
            command.extend(["--approval-mode", "auto"])
        elif permission_mode == 'deny':
            command.extend(["--approval-mode", "deny"])
        else:
            command.extend(["--approval-mode", "prompt"])

        # Working directory
        working_dir = context.get('working_directory')
        if working_dir:
            command.extend(["--work-dir", working_dir])

        # Budget constraints
        max_cost = constraints.get('max_cost_usd', 1.0)
        command.extend(["--budget", str(max_cost)])

        # Tool restrictions
        allowed_tools = constraints.get('allowed_tools', [])
        if allowed_tools:
            command.extend(["--allowed-tools", ",".join(allowed_tools)])

        disallowed_tools = constraints.get('disallowed_tools', [])
        if disallowed_tools:
            command.extend(["--disallowed-tools", ",".join(disallowed_tools)])

        # Add conversation context if available
        conversation_history = context.get('conversation_history', [])
        if conversation_history:
            context_content = self._format_conversation_context(conversation_history, content)
            command.append(context_content)
        else:
            command.append(content)

        return command

    def _format_conversation_context(
        self,
        conversation_history: List[Dict[str, Any]],
        current_content: str
    ) -> str:
        """Format conversation history for Codex CLI.

        Args:
            conversation_history: Previous conversation turns
            current_content: Current request content

        Returns:
            Formatted context string
        """
        context_parts = ["Previous conversation context:"]

        # Include last few turns for context
        recent_turns = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history

        for i, turn in enumerate(recent_turns):
            role = turn.get('role', 'assistant')
            content = turn.get('content', '')
            from_agent = turn.get('from_agent', 'unknown')

            context_parts.append(f"\n{i+1}. {from_agent} ({role}): {content[:200]}...")

        context_parts.extend([
            "\n\nCurrent request:",
            current_content,
            "\nPlease consider the conversation context when responding."
        ])

        return '\n'.join(context_parts)

    async def _execute_codex_command(
        self,
        command: List[str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute Codex CLI command and return result.

        Args:
            command: Command to execute
            context: Execution context

        Returns:
            Execution result dictionary
        """
        self.logger.info(f"Executing Codex CLI: {' '.join(command[:3])}...")

        # Set up environment
        env = os.environ.copy()

        # Configure Codex home directory for session logs
        codex_home = env.get('CODEX_HOME', os.path.expanduser('~/.codex'))
        env['CODEX_HOME'] = codex_home

        # Add working directory to environment if specified
        working_dir = context.get('working_directory')
        if working_dir:
            env['PWD'] = working_dir

        # Execute command
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=working_dir
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='ignore')
            raise RuntimeError(f"Codex CLI failed (exit {process.returncode}): {error_msg}")

        # Return basic execution info
        output = stdout.decode('utf-8', errors='ignore')
        return {
            'output': output,
            'error': stderr.decode('utf-8', errors='ignore'),
            'returncode': process.returncode,
            'codex_home': codex_home
        }

    async def _parse_codex_response(
        self,
        codex_result: Dict[str, Any],
        context: Dict[str, Any]
    ) -> tuple[str, Dict[str, Any]]:
        """Parse Codex CLI response by reading session logs.

        Args:
            codex_result: Result from Codex CLI execution
            context: Execution context

        Returns:
            Tuple of (response_content, metadata)
        """
        # Find the most recent session log
        codex_home = codex_result.get('codex_home', os.path.expanduser('~/.codex'))
        session_log_pattern = os.path.join(codex_home, 'sessions', '**', 'rollout-*.jsonl')

        try:
            # Find all session log files
            log_files = glob.glob(session_log_pattern, recursive=True)

            if not log_files:
                # No session logs found, use stdout
                return codex_result.get('output', ''), {'cost_usd': 0.0, 'tokens_used': 0}

            # Get the most recent log file
            latest_log = max(log_files, key=os.path.getmtime)

            # Parse the session log
            content, metadata = await self._parse_session_log(latest_log)

            # Store log file for this session
            session_id = context.get('session_metadata', {}).get('session_id')
            if session_id:
                if session_id not in self._session_logs:
                    self._session_logs[session_id] = []
                self._session_logs[session_id].append(latest_log)

            return content, metadata

        except Exception as e:
            self.logger.warning(f"Failed to parse session logs: {str(e)}")
            # Fallback to stdout
            return codex_result.get('output', ''), {'cost_usd': 0.0, 'tokens_used': 0}

    async def _parse_session_log(self, log_file_path: str) -> tuple[str, Dict[str, Any]]:
        """Parse Codex session log file.

        Args:
            log_file_path: Path to session log file

        Returns:
            Tuple of (content, metadata)
        """
        content_parts = []
        metadata = {
            'cost_usd': 0.0,
            'tokens_used': 0,
            'tools_used': [],
            'files_accessed': [],
            'reasoning': '',
            'confidence': 0.75,
            'next_action': ''
        }

        try:
            with open(log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        log_entry = json.loads(line)
                        entry_type = log_entry.get('type', '')

                        if entry_type == 'assistant_message':
                            # Assistant response content
                            message_content = log_entry.get('content', '')
                            content_parts.append(message_content)

                        elif entry_type == 'tool_call':
                            # Tool usage tracking
                            tool_name = log_entry.get('tool', {}).get('name', '')
                            if tool_name and tool_name not in metadata['tools_used']:
                                metadata['tools_used'].append(tool_name)

                        elif entry_type == 'file_access':
                            # File access tracking
                            file_path = log_entry.get('path', '')
                            if file_path and file_path not in metadata['files_accessed']:
                                metadata['files_accessed'].append(file_path)

                        elif entry_type == 'cost_update':
                            # Cost tracking
                            cost_data = log_entry.get('cost', {})
                            metadata['cost_usd'] += cost_data.get('usd', 0.0)
                            metadata['tokens_used'] += cost_data.get('tokens', 0)

                        elif entry_type == 'execution_complete':
                            # Final execution metadata
                            exec_meta = log_entry.get('metadata', {})
                            metadata.update({
                                'duration_ms': exec_meta.get('duration_ms', 0),
                                'success': exec_meta.get('success', True)
                            })

                    except json.JSONDecodeError:
                        # Skip malformed JSON lines
                        continue

        except Exception as e:
            self.logger.error(f"Error reading session log {log_file_path}: {str(e)}")

        # Combine content
        content = '\n'.join(content_parts)

        # Extract additional metadata from content
        if content:
            metadata['reasoning'] = self._extract_reasoning_from_content(content)
            metadata['confidence'] = self._estimate_confidence_from_content(content)
            metadata['next_action'] = self._suggest_next_action_from_content(content)

        return content, metadata

    def _extract_reasoning_from_content(self, content: str) -> str:
        """Extract reasoning from Codex response content.

        Args:
            content: Response content

        Returns:
            Extracted reasoning
        """
        lines = content.split('\n')
        reasoning_lines = []

        reasoning_markers = [
            "because", "since", "the reason", "analysis",
            "explanation", "rationale", "this is due to"
        ]

        for line in lines:
            line_lower = line.lower()
            if any(marker in line_lower for marker in reasoning_markers):
                reasoning_lines.append(line.strip())

        return ' '.join(reasoning_lines[:2])  # First 2 reasoning lines

    def _estimate_confidence_from_content(self, content: str) -> float:
        """Estimate confidence from Codex response content.

        Args:
            content: Response content

        Returns:
            Confidence score between 0.0 and 1.0
        """
        content_lower = content.lower()

        # Codex-specific confidence indicators
        high_confidence = [
            'identified', 'confirmed', 'verified', 'found',
            'successfully', 'correctly', 'definitely'
        ]

        low_confidence = [
            'might', 'possibly', 'uncertain', 'unclear',
            'appears to be', 'seems like', 'potentially'
        ]

        high_count = sum(1 for term in high_confidence if term in content_lower)
        low_count = sum(1 for term in low_confidence if term in content_lower)

        # Base confidence for Codex
        confidence = 0.75

        # Adjust based on indicators
        confidence += high_count * 0.08
        confidence -= low_count * 0.12

        return max(0.0, min(1.0, confidence))

    def _suggest_next_action_from_content(self, content: str) -> str:
        """Suggest next action from Codex response content.

        Args:
            content: Response content

        Returns:
            Suggested next action
        """
        content_lower = content.lower()

        if 'fix' in content_lower or 'patch' in content_lower:
            return "Apply the proposed fix"
        elif 'test' in content_lower or 'validate' in content_lower:
            return "Run tests to validate"
        elif 'reproduce' in content_lower:
            return "Verify bug reproduction"
        elif 'analyze' in content_lower or 'investigate' in content_lower:
            return "Continue analysis"
        else:
            return "Review the findings"

    async def health_check(self, deep_check: bool = False) -> Dict[str, Any]:
        """Perform health check on Codex CLI.

        Args:
            deep_check: Whether to perform comprehensive health check

        Returns:
            Health status information
        """
        try:
            # Basic health check - verify Codex CLI is available
            process = await asyncio.create_subprocess_exec(
                'codex', '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)

            if process.returncode == 0:
                version = stdout.decode('utf-8', errors='ignore').strip()

                health_info = {
                    'status': 'healthy',
                    'version': version,
                    'capabilities': self.config.capabilities,
                    'uptime_seconds': int((datetime.now(timezone.utc) - self._last_health_check).total_seconds())
                }

                if deep_check:
                    # Perform a simple test execution
                    try:
                        test_command = [
                            'codex', 'exec',
                            '--approval-mode', 'auto',
                            '--budget', '0.01',
                            'Say hello'
                        ]

                        test_process = await asyncio.create_subprocess_exec(
                            *test_command,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )

                        test_stdout, test_stderr = await asyncio.wait_for(
                            test_process.communicate(),
                            timeout=15.0
                        )

                        if test_process.returncode == 0:
                            health_info['deep_check'] = 'passed'
                        else:
                            health_info['status'] = 'degraded'
                            health_info['deep_check'] = 'failed'
                            health_info['last_error'] = test_stderr.decode('utf-8', errors='ignore')

                    except asyncio.TimeoutError:
                        health_info['status'] = 'degraded'
                        health_info['deep_check'] = 'timeout'

                return health_info

            else:
                return {
                    'status': 'unhealthy',
                    'version': 'unknown',
                    'capabilities': [],
                    'last_error': stderr.decode('utf-8', errors='ignore')
                }

        except Exception as e:
            return {
                'status': 'unhealthy',
                'version': 'unknown',
                'capabilities': [],
                'last_error': str(e)
            }

    async def reset_session(self, session_id: str, preserve_context: bool = False) -> Dict[str, Any]:
        """Reset Codex session state.

        Args:
            session_id: Session to reset
            preserve_context: Whether to preserve conversation context

        Returns:
            Reset operation results
        """
        result = await super().reset_session(session_id, preserve_context)

        # Clean up session logs if not preserving context
        if not preserve_context and session_id in self._session_logs:
            self._session_logs.pop(session_id, None)

        return result