"""Claude Code agent adapter with headless mode integration."""

import asyncio
import json
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import tempfile
import os

from tab.services.base_agent_adapter import BaseAgentAdapter, AgentResponse, ProcessingStatus
from tab.models.agent_adapter import AgentAdapter, AgentStatus


class ClaudeCodeAdapter(BaseAgentAdapter):
    """Agent adapter for Claude Code CLI with headless mode support."""

    def __init__(self, agent_config: AgentAdapter):
        """Initialize Claude Code adapter.

        Args:
            agent_config: Agent configuration
        """
        super().__init__(agent_config)
        self._session_store: Dict[str, str] = {}  # session_id -> claude_session_id mapping

    async def process_request(
        self,
        request_id: str,
        content: str,
        context: Dict[str, Any],
        constraints: Dict[str, Any]
    ) -> AgentResponse:
        """Process a request using Claude Code CLI.

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

            # Build Claude Code command
            command = await self._build_command(content, context, constraints)

            # Execute with timeout
            timeout_ms = constraints.get('max_execution_time_ms', 120000)
            timeout_seconds = timeout_ms / 1000

            result = await self._execute_with_timeout(
                self._execute_claude_command(command, context),
                timeout_seconds,
                request_id
            )

            # Parse response
            response_content, metadata = self._parse_claude_response(result)

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
                confidence=metadata.get('confidence', 0.8),
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
            self.logger.error(f"Claude Code execution failed: {str(e)}")
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
        """Build Claude Code command with appropriate options.

        Args:
            content: Request content
            context: Conversation context
            constraints: Policy constraints

        Returns:
            Command arguments list
        """
        command = ["claude"]

        # Use headless mode with stream-json output
        command.extend(["--output-format", "stream-json"])

        # Session management
        session_metadata = context.get('session_metadata', {})
        session_id = session_metadata.get('session_id')

        if session_id and session_id in self._session_store:
            # Resume existing session
            claude_session_id = self._session_store[session_id]
            command.extend(["--resume", claude_session_id])
        else:
            # Create new session
            if session_id:
                # Generate session ID for Claude
                claude_session_id = f"tab-{session_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                self._session_store[session_id] = claude_session_id
                command.extend(["--session-id", claude_session_id])

        # Working directory constraints
        working_dir = context.get('working_directory')
        if working_dir:
            command.extend(["--work-dir", working_dir])

        # File access constraints
        allowed_files = context.get('allowed_files', [])
        if allowed_files:
            # Create file list for Claude Code
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for file_path in allowed_files:
                    f.write(f"{file_path}\n")
                command.extend(["--allowed-files", f.name])

        # Cost budget
        max_cost = constraints.get('max_cost_usd', 0.1)
        command.extend(["--budget", str(max_cost)])

        # Add the actual prompt
        command.extend(["-p", content])

        return command

    async def _execute_claude_command(
        self,
        command: List[str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute Claude Code command and return parsed result.

        Args:
            command: Command to execute
            context: Execution context

        Returns:
            Parsed command output
        """
        self.logger.info(f"Executing Claude Code: {' '.join(command[:3])}...")

        # Set up environment
        env = os.environ.copy()

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
            raise RuntimeError(f"Claude Code failed (exit {process.returncode}): {error_msg}")

        # Parse stream-json output
        output = stdout.decode('utf-8', errors='ignore')
        return self._parse_stream_json_output(output)

    def _parse_stream_json_output(self, output: str) -> Dict[str, Any]:
        """Parse Claude Code stream-json output.

        Args:
            output: Raw output from Claude Code

        Returns:
            Parsed result dictionary
        """
        result = {
            'content': '',
            'cost_usd': 0.0,
            'tokens_used': 0,
            'duration_ms': 0,
            'session_id': '',
            'success': True
        }

        lines = output.strip().split('\n')
        content_lines = []

        for line in lines:
            if not line.strip():
                continue

            try:
                data = json.loads(line)
                msg_type = data.get('type', '')

                if msg_type == 'content':
                    # Accumulate content
                    content_lines.append(data.get('content', ''))

                elif msg_type == 'result':
                    # Final result with metadata
                    result.update({
                        'cost_usd': data.get('total_cost_usd', 0.0),
                        'duration_ms': data.get('duration_ms', 0),
                        'session_id': data.get('session_id', ''),
                        'success': data.get('subtype') == 'success'
                    })

                elif msg_type == 'usage':
                    # Token usage information
                    result['tokens_used'] = data.get('tokens', 0)

                elif msg_type == 'error':
                    # Error information
                    result['success'] = False
                    result['error'] = data.get('message', 'Unknown error')

            except json.JSONDecodeError:
                # Non-JSON line, treat as content
                content_lines.append(line)

        result['content'] = '\n'.join(content_lines)
        return result

    def _parse_claude_response(self, claude_result: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        """Parse Claude Code response and extract metadata.

        Args:
            claude_result: Result from Claude Code execution

        Returns:
            Tuple of (response_content, metadata)
        """
        content = claude_result.get('content', '')

        metadata = {
            'cost_usd': claude_result.get('cost_usd', 0.0),
            'tokens_used': claude_result.get('tokens_used', 0),
            'duration_ms': claude_result.get('duration_ms', 0),
            'session_id': claude_result.get('session_id', ''),
            'reasoning': self._extract_reasoning(content),
            'confidence': self._estimate_confidence(content),
            'tools_used': self._extract_tools_used(content),
            'files_accessed': self._extract_files_accessed(content),
            'next_action': self._suggest_next_action(content)
        }

        return content, metadata

    def _extract_reasoning(self, content: str) -> str:
        """Extract reasoning from Claude's response.

        Args:
            content: Response content

        Returns:
            Extracted reasoning or empty string
        """
        # Look for common reasoning patterns
        reasoning_markers = [
            "because", "since", "due to", "the reason",
            "analysis shows", "evidence indicates", "this suggests"
        ]

        lines = content.split('\n')
        reasoning_lines = []

        for line in lines:
            line_lower = line.lower()
            if any(marker in line_lower for marker in reasoning_markers):
                reasoning_lines.append(line.strip())

        return ' '.join(reasoning_lines[:3])  # First 3 reasoning lines

    def _estimate_confidence(self, content: str) -> float:
        """Estimate confidence level from response content.

        Args:
            content: Response content

        Returns:
            Confidence score between 0.0 and 1.0
        """
        content_lower = content.lower()

        # High confidence indicators
        high_confidence_terms = [
            'definitely', 'certainly', 'clearly', 'obviously',
            'confirmed', 'verified', 'established'
        ]

        # Low confidence indicators
        low_confidence_terms = [
            'might', 'could', 'possibly', 'perhaps',
            'uncertain', 'unclear', 'ambiguous'
        ]

        high_count = sum(1 for term in high_confidence_terms if term in content_lower)
        low_count = sum(1 for term in low_confidence_terms if term in content_lower)

        # Base confidence
        confidence = 0.7

        # Adjust based on indicators
        confidence += high_count * 0.1
        confidence -= low_count * 0.15

        return max(0.0, min(1.0, confidence))

    def _extract_tools_used(self, content: str) -> List[str]:
        """Extract tools used from Claude's response.

        Args:
            content: Response content

        Returns:
            List of tool names used
        """
        # Common Claude Code tools
        claude_tools = [
            'Read', 'Write', 'Edit', 'Bash', 'Grep', 'Glob',
            'MultiEdit', 'WebFetch', 'Task'
        ]

        tools_used = []
        content_lines = content.split('\n')

        for line in content_lines:
            for tool in claude_tools:
                if tool in line and ('invoke' in line or 'tool' in line.lower()):
                    if tool not in tools_used:
                        tools_used.append(tool)

        return tools_used

    def _extract_files_accessed(self, content: str) -> List[str]:
        """Extract files accessed from Claude's response.

        Args:
            content: Response content

        Returns:
            List of file paths accessed
        """
        import re

        # Look for file path patterns
        file_patterns = [
            r'(?:src|tests?|config)/[^\s]+\.(?:py|js|ts|json|yaml|yml|md)',
            r'/[^\s]+\.(?:py|js|ts|json|yaml|yml|md)',
            r'[^\s]+\.(?:py|js|ts|json|yaml|yml|md)'
        ]

        files_accessed = []

        for pattern in file_patterns:
            matches = re.findall(pattern, content)
            files_accessed.extend(matches)

        # Remove duplicates and return
        return list(set(files_accessed))

    def _suggest_next_action(self, content: str) -> str:
        """Suggest next action based on Claude's response.

        Args:
            content: Response content

        Returns:
            Suggested next action
        """
        content_lower = content.lower()

        if 'test' in content_lower or 'verify' in content_lower:
            return "Run tests to verify the changes"
        elif 'implement' in content_lower or 'create' in content_lower:
            return "Proceed with implementation"
        elif 'review' in content_lower or 'check' in content_lower:
            return "Review the proposed changes"
        elif 'error' in content_lower or 'fix' in content_lower:
            return "Address the identified issues"
        else:
            return "Continue with the conversation"

    async def health_check(self, deep_check: bool = False) -> Dict[str, Any]:
        """Perform health check on Claude Code CLI.

        Args:
            deep_check: Whether to perform comprehensive health check

        Returns:
            Health status information
        """
        try:
            # Basic health check - verify Claude Code is available
            process = await asyncio.create_subprocess_exec(
                'claude', '--version',
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
                    # Perform a simple test request
                    try:
                        test_command = ['claude', '--output-format', 'stream-json', '-p', 'Hello, are you working?']
                        test_process = await asyncio.create_subprocess_exec(
                            *test_command,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )

                        test_stdout, test_stderr = await asyncio.wait_for(
                            test_process.communicate(),
                            timeout=10.0
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