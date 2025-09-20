"""MCP server implementation for orchestrator tools."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

from tab.services.conversation_orchestrator import ConversationOrchestrator
from tab.models.conversation_session import ConversationSession
from tab.models.audit_record import AuditRecord, EventType


logger = logging.getLogger(__name__)


# MCP Request/Response Models
class MCPRequest(BaseModel):
    """Base MCP request model."""

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: Union[str, int] = Field(..., description="Request ID")
    method: str = Field(..., description="Method name")
    params: Dict[str, Any] = Field(default_factory=dict, description="Method parameters")


class MCPResponse(BaseModel):
    """Base MCP response model."""

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: Union[str, int] = Field(..., description="Request ID")
    result: Optional[Dict[str, Any]] = Field(None, description="Success result")
    error: Optional[Dict[str, Any]] = Field(None, description="Error details")


class MCPError(BaseModel):
    """MCP error details."""

    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional error data")


# Tool-specific request/response models
class StartConversationRequest(BaseModel):
    """Request schema for start_conversation tool."""

    topic: str = Field(..., min_length=1, max_length=1000, description="Initial question or task description")
    participants: List[str] = Field(..., min_items=2, max_items=5, description="List of agent identifiers")
    policy_id: str = Field(default="default", description="Policy configuration to apply")
    max_turns: int = Field(default=8, ge=1, le=20, description="Maximum conversation turns allowed")
    budget_usd: float = Field(default=1.0, ge=0.01, le=10.0, description="Maximum cost budget in USD")


class StartConversationResponse(BaseModel):
    """Response schema for start_conversation tool."""

    session_id: str = Field(..., description="Unique session identifier")
    status: str = Field(..., description="Session creation status")
    participants: List[str] = Field(..., description="Confirmed participant agents")
    policy_applied: str = Field(..., description="Applied policy configuration")
    created_at: str = Field(..., description="Session creation timestamp")


class SendMessageRequest(BaseModel):
    """Request schema for send_message tool."""

    session_id: str = Field(..., description="Target conversation session")
    content: str = Field(..., min_length=1, max_length=10000, description="Message content to send")
    to_agent: str = Field(default="auto", description="Target agent identifier")
    attachments: List[Dict[str, Any]] = Field(default_factory=list, max_items=10, description="Optional file attachments")


class SendMessageResponse(BaseModel):
    """Response schema for send_message tool."""

    turn_id: str = Field(..., description="Unique turn identifier")
    response: Dict[str, Any] = Field(..., description="Agent response")
    session_status: str = Field(..., description="Updated session status")
    convergence_detected: bool = Field(default=False, description="Whether conversation convergence was detected")


class GetSessionStatusRequest(BaseModel):
    """Request schema for get_session_status tool."""

    session_id: str = Field(..., description="Session identifier to query")
    include_history: bool = Field(default=False, description="Whether to include full turn history")


class ListAgentsRequest(BaseModel):
    """Request schema for list_agents tool."""

    include_capabilities: bool = Field(default=False, description="Whether to include agent capabilities")


class ExportAuditLogRequest(BaseModel):
    """Request schema for export_audit_log tool."""

    session_id: str = Field(..., description="Session to export audit log for")
    format: str = Field(default="json", description="Export format")
    include_security_events: bool = Field(default=True, description="Whether to include security audit events")


class MCPOrchestratorServer:
    """MCP server for Twin-Agent Bridge orchestrator tools."""

    def __init__(self, orchestrator: Optional[ConversationOrchestrator] = None):
        """Initialize MCP server.

        Args:
            orchestrator: Conversation orchestrator instance
        """
        self.logger = logging.getLogger(__name__)
        self.orchestrator = orchestrator or ConversationOrchestrator()
        self.audit_records: List[AuditRecord] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the MCP server."""
        if not self._initialized:
            await self.orchestrator.initialize()
            self._initialized = True
            self.logger.info("MCP orchestrator server initialized")

    async def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP request.

        Args:
            request_data: Raw request data

        Returns:
            MCP response
        """
        try:
            # Parse MCP request
            request = MCPRequest(**request_data)

            # Route to appropriate tool handler
            if request.method == "tools/call":
                return await self._handle_tool_call(request)
            elif request.method == "tools/list":
                return await self._handle_tools_list(request)
            elif request.method == "resources/list":
                return await self._handle_resources_list(request)
            elif request.method == "prompts/list":
                return await self._handle_prompts_list(request)
            else:
                return self._create_error_response(
                    request.id,
                    -32601,  # Method not found
                    f"Unknown method: {request.method}"
                )

        except ValidationError as e:
            return self._create_error_response(
                request_data.get("id", "unknown"),
                -32602,  # Invalid params
                f"Request validation failed: {str(e)}"
            )
        except Exception as e:
            self.logger.error(f"Unexpected error handling request: {str(e)}")
            return self._create_error_response(
                request_data.get("id", "unknown"),
                -32603,  # Internal error
                f"Internal server error: {str(e)}"
            )

    async def _handle_tool_call(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle tool call request.

        Args:
            request: MCP request

        Returns:
            Tool call response
        """
        params = request.params
        tool_name = params.get("name")
        tool_arguments = params.get("arguments", {})

        try:
            if tool_name == "start_conversation":
                result = await self._start_conversation(tool_arguments)
            elif tool_name == "send_message":
                result = await self._send_message(tool_arguments)
            elif tool_name == "get_session_status":
                result = await self._get_session_status(tool_arguments)
            elif tool_name == "list_agents":
                result = await self._list_agents(tool_arguments)
            elif tool_name == "export_audit_log":
                result = await self._export_audit_log(tool_arguments)
            else:
                return self._create_error_response(
                    request.id,
                    -32601,
                    f"Unknown tool: {tool_name}"
                )

            return self._create_success_response(request.id, result)

        except ValidationError as e:
            return self._create_error_response(
                request.id,
                -32602,
                f"Invalid arguments for {tool_name}: {str(e)}"
            )
        except Exception as e:
            self.logger.error(f"Error in tool {tool_name}: {str(e)}")
            return self._create_error_response(
                request.id,
                -32603,
                f"Tool execution failed: {str(e)}"
            )

    async def _start_conversation(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle start_conversation tool call.

        Args:
            arguments: Tool arguments

        Returns:
            Tool result
        """
        # Validate arguments
        req = StartConversationRequest(**arguments)

        # Create audit record
        audit_record = AuditRecord(
            event_type=EventType.ACTION,
            action="start_conversation",
            metadata={
                "topic": req.topic,
                "participants": req.participants,
                "policy_id": req.policy_id,
                "max_turns": req.max_turns,
                "budget_usd": req.budget_usd
            }
        )
        self.audit_records.append(audit_record)

        # Start conversation
        result = await self.orchestrator.start_conversation(
            topic=req.topic,
            participants=req.participants,
            policy_id=req.policy_id,
            max_turns=req.max_turns,
            budget_usd=req.budget_usd
        )

        # Update audit record with result
        audit_record.result = "success" if result.get("status") == "active" else "failed"
        audit_record.metadata.update({
            "session_id": result.get("session_id"),
            "status": result.get("status")
        })

        return result

    async def _send_message(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle send_message tool call.

        Args:
            arguments: Tool arguments

        Returns:
            Tool result
        """
        # Validate arguments
        req = SendMessageRequest(**arguments)

        # Create audit record
        audit_record = AuditRecord(
            session_id=req.session_id,
            event_type=EventType.ACTION,
            action="send_message",
            metadata={
                "content_length": len(req.content),
                "to_agent": req.to_agent,
                "attachment_count": len(req.attachments)
            }
        )
        self.audit_records.append(audit_record)

        # Send message
        result = await self.orchestrator.send_message(
            session_id=req.session_id,
            content=req.content,
            to_agent=req.to_agent,
            attachments=req.attachments
        )

        # Update audit record with result
        audit_record.result = "success" if "error" not in result else "failed"
        audit_record.metadata.update({
            "turn_id": result.get("turn_id"),
            "session_status": result.get("session_status"),
            "convergence_detected": result.get("convergence_detected", False)
        })

        return result

    async def _get_session_status(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_session_status tool call.

        Args:
            arguments: Tool arguments

        Returns:
            Tool result
        """
        # Validate arguments
        req = GetSessionStatusRequest(**arguments)

        # Create audit record
        audit_record = AuditRecord(
            session_id=req.session_id,
            event_type=EventType.ACTION,
            action="get_session_status",
            metadata={
                "include_history": req.include_history
            }
        )
        self.audit_records.append(audit_record)

        # Get session status
        try:
            result = await self.orchestrator.get_session_status(
                session_id=req.session_id,
                include_history=req.include_history
            )
            audit_record.result = "success"
            return result

        except ValueError as e:
            audit_record.result = "failed"
            audit_record.metadata["error"] = str(e)
            raise

    async def _list_agents(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list_agents tool call.

        Args:
            arguments: Tool arguments

        Returns:
            Tool result
        """
        # Validate arguments
        req = ListAgentsRequest(**arguments)

        # Create audit record
        audit_record = AuditRecord(
            event_type=EventType.ACTION,
            action="list_agents",
            metadata={
                "include_capabilities": req.include_capabilities
            }
        )
        self.audit_records.append(audit_record)

        # List agents
        result = await self.orchestrator.list_agents(
            include_capabilities=req.include_capabilities
        )

        audit_record.result = "success"
        audit_record.metadata["agent_count"] = len(result.get("agents", []))

        return result

    async def _export_audit_log(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle export_audit_log tool call.

        Args:
            arguments: Tool arguments

        Returns:
            Tool result
        """
        # Validate arguments
        req = ExportAuditLogRequest(**arguments)

        # Filter audit records for session
        session_records = [
            record for record in self.audit_records
            if record.session_id == req.session_id or
            (record.session_id is None and req.session_id in str(record.metadata))
        ]

        # Filter security events if requested
        if req.include_security_events:
            filtered_records = session_records
        else:
            filtered_records = [
                record for record in session_records
                if record.event_type != EventType.SECURITY
            ]

        # Format audit data
        if req.format == "json":
            audit_data = json.dumps([
                record.model_dump() for record in filtered_records
            ], indent=2, default=str)
        elif req.format == "jsonl":
            audit_data = "\n".join([
                record.model_dump_json() for record in filtered_records
            ])
        elif req.format == "csv":
            # Simple CSV format
            lines = ["timestamp,event_type,action,result,session_id"]
            for record in filtered_records:
                lines.append(f"{record.timestamp},{record.event_type},{record.action},{record.result},{record.session_id or ''}")
            audit_data = "\n".join(lines)
        else:
            raise ValueError(f"Unsupported format: {req.format}")

        return {
            "audit_data": audit_data,
            "format": req.format,
            "record_count": len(filtered_records),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "security_events_included": req.include_security_events
        }

    async def _handle_tools_list(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle tools list request.

        Args:
            request: MCP request

        Returns:
            Tools list response
        """
        tools = [
            {
                "name": "start_conversation",
                "description": "Start a new multi-agent conversation session",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "minLength": 1, "maxLength": 1000},
                        "participants": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 5},
                        "policy_id": {"type": "string", "default": "default"},
                        "max_turns": {"type": "integer", "minimum": 1, "maximum": 20, "default": 8},
                        "budget_usd": {"type": "number", "minimum": 0.01, "maximum": 10.0, "default": 1.0}
                    },
                    "required": ["topic", "participants"]
                }
            },
            {
                "name": "send_message",
                "description": "Send a message in an active conversation",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "content": {"type": "string", "minLength": 1, "maxLength": 10000},
                        "to_agent": {"type": "string", "default": "auto"},
                        "attachments": {"type": "array", "maxItems": 10}
                    },
                    "required": ["session_id", "content"]
                }
            },
            {
                "name": "get_session_status",
                "description": "Get current status and history of a conversation session",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "include_history": {"type": "boolean", "default": False}
                    },
                    "required": ["session_id"]
                }
            },
            {
                "name": "list_agents",
                "description": "List available agents and their current status",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "include_capabilities": {"type": "boolean", "default": False}
                    }
                }
            },
            {
                "name": "export_audit_log",
                "description": "Export audit log for a conversation session",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "format": {"type": "string", "enum": ["json", "csv", "jsonl"], "default": "json"},
                        "include_security_events": {"type": "boolean", "default": True}
                    },
                    "required": ["session_id"]
                }
            }
        ]

        return self._create_success_response(request.id, {"tools": tools})

    async def _handle_resources_list(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle resources list request.

        Args:
            request: MCP request

        Returns:
            Resources list response
        """
        resources = [
            {
                "uri": "tab://sessions/{session_id}",
                "name": "Conversation Session",
                "description": "Access to conversation session data",
                "mimeType": "application/json"
            },
            {
                "uri": "tab://agents/{agent_id}/health",
                "name": "Agent Health Status",
                "description": "Real-time agent health information",
                "mimeType": "application/json"
            }
        ]

        return self._create_success_response(request.id, {"resources": resources})

    async def _handle_prompts_list(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle prompts list request.

        Args:
            request: MCP request

        Returns:
            Prompts list response
        """
        prompts = [
            {
                "name": "conversation_summary",
                "description": "Generate a summary of a conversation session",
                "arguments": [
                    {"name": "session_id", "description": "Session to summarize", "required": True}
                ]
            },
            {
                "name": "convergence_analysis",
                "description": "Analyze conversation for convergence patterns",
                "arguments": [
                    {"name": "session_id", "description": "Session to analyze", "required": True}
                ]
            }
        ]

        return self._create_success_response(request.id, {"prompts": prompts})

    def _create_success_response(self, request_id: Union[str, int], result: Dict[str, Any]) -> Dict[str, Any]:
        """Create successful MCP response.

        Args:
            request_id: Request ID
            result: Response result

        Returns:
            MCP response
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }

    def _create_error_response(
        self,
        request_id: Union[str, int],
        error_code: int,
        error_message: str,
        error_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create error MCP response.

        Args:
            request_id: Request ID
            error_code: Error code
            error_message: Error message
            error_data: Additional error data

        Returns:
            MCP error response
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": error_code,
                "message": error_message,
                "data": error_data
            }
        }

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Direct tool call interface for testing.

        Args:
            tool_name: Name of tool to call
            arguments: Tool arguments

        Returns:
            Tool result
        """
        request_data = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        response = await self.handle_request(request_data)

        if "error" in response:
            raise ValueError(f"Tool call failed: {response['error']['message']}")

        return response["result"]

    async def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get session by ID for testing.

        Args:
            session_id: Session identifier

        Returns:
            ConversationSession if found
        """
        return self.orchestrator._sessions.get(session_id)

    async def shutdown(self) -> None:
        """Shutdown the MCP server."""
        self.logger.info("Shutting down MCP orchestrator server")
        await self.orchestrator.shutdown()
        self.logger.info("MCP orchestrator server shut down")