"""
Main CLI application for TAB (Twin-Agent Bridge).

Provides command-line interface for serving the orchestrator and
managing the TAB system.
"""

import asyncio
import logging
import signal
import sys
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import click
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

from tab.lib.config import initialize_config, get_config, ConfigurationError
from tab.lib.logging_config import setup_logging, get_audit_logger
from tab.lib.observability import initialize_telemetry, shutdown_telemetry
from tab.lib.metrics import initialize_metrics
from tab.services.mcp_orchestrator_server import create_mcp_server
from tab.services.conversation_orchestrator import ConversationOrchestrator
from tab.services.session_manager import SessionManager
from tab.services.policy_enforcer import PolicyEnforcer
from tab.models.conversation_session import ConversationSession
from tab.models.policy_configuration import PolicyConfiguration


logger = logging.getLogger("tab.cli")
audit_logger = get_audit_logger()


class TABApplication:
    """Main TAB application manager."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config_manager = None
        self.app: Optional[FastAPI] = None
        self.orchestrator: Optional[ConversationOrchestrator] = None
        self.session_manager: Optional[SessionManager] = None
        self.policy_enforcer: Optional[PolicyEnforcer] = None
        self._shutdown_event = asyncio.Event()

    async def initialize(self) -> None:
        """Initialize the TAB application."""
        try:
            # Load configuration
            logger.info("Initializing TAB application")
            self.config_manager = initialize_config(self.config_path)
            config = self.config_manager.get_config()

            # Setup logging
            setup_logging(config.logging.dict())
            logger.info("Logging configured")

            # Initialize observability
            telemetry_manager = initialize_telemetry(config.observability.dict())
            meter = telemetry_manager.get_meter()
            initialize_metrics(meter)
            logger.info("Observability initialized")

            # Initialize core services
            self.session_manager = SessionManager(config.session)
            self.policy_enforcer = PolicyEnforcer(config.policies)
            self.orchestrator = ConversationOrchestrator(
                session_manager=self.session_manager,
                policy_enforcer=self.policy_enforcer,
                agent_configs=config.agents
            )

            # Create FastAPI application
            self.app = create_mcp_server(self.orchestrator)

            # Log successful initialization
            audit_logger.log_session_event(
                event_type="system_startup",
                session_id="system",
                action="initialize",
                result="success",
                metadata={
                    "config_path": config.config_file_path,
                    "agents_configured": list(config.agents.keys()),
                    "policies_configured": list(config.policies.keys())
                }
            )

            logger.info("TAB application initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize TAB application: {e}")
            audit_logger.log_session_event(
                event_type="system_startup",
                session_id="system",
                action="initialize",
                result="failed",
                metadata={"error": str(e)}
            )
            raise

    async def shutdown(self) -> None:
        """Gracefully shutdown the TAB application."""
        logger.info("Shutting down TAB application")

        try:
            # Stop orchestrator
            if self.orchestrator:
                await self.orchestrator.shutdown()

            # Stop session manager
            if self.session_manager:
                await self.session_manager.shutdown()

            # Shutdown observability
            shutdown_telemetry()

            audit_logger.log_session_event(
                event_type="system_shutdown",
                session_id="system",
                action="shutdown",
                result="success"
            )

            logger.info("TAB application shutdown completed")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            audit_logger.log_session_event(
                event_type="system_shutdown",
                session_id="system",
                action="shutdown",
                result="failed",
                metadata={"error": str(e)}
            )

    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown")
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def run_server(
        self,
        host: str = "localhost",
        port: int = 8000,
        workers: int = 1,
        reload: bool = False
    ) -> None:
        """Run the TAB server."""
        await self.initialize()

        if not self.app:
            raise RuntimeError("Application not initialized")

        config = get_config()

        # Use config values with CLI overrides
        final_host = host if host != "localhost" else config.server.host
        final_port = port if port != 8000 else config.server.port
        final_workers = workers if workers != 1 else config.server.workers

        logger.info(f"Starting TAB server on {final_host}:{final_port}")

        # Setup signal handlers
        self.setup_signal_handlers()

        # Create server config
        server_config = uvicorn.Config(
            app=self.app,
            host=final_host,
            port=final_port,
            workers=final_workers if not reload else 1,
            reload=reload,
            log_config=None,  # Use our custom logging
            access_log=False   # Disable uvicorn access log
        )

        server = uvicorn.Server(server_config)

        # Run server with shutdown handling
        try:
            await asyncio.create_task(self._run_with_shutdown(server))
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            await self.shutdown()

    async def _run_with_shutdown(self, server: uvicorn.Server) -> None:
        """Run server with shutdown event handling."""
        server_task = asyncio.create_task(server.serve())
        shutdown_task = asyncio.create_task(self._shutdown_event.wait())

        try:
            done, pending = await asyncio.wait(
                [server_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # If shutdown was triggered, stop the server
            if shutdown_task in done:
                server.should_exit = True
                if not server_task.done():
                    await server_task

        except Exception as e:
            logger.error(f"Error in server execution: {e}")
            raise


# CLI Commands

@click.group()
@click.option('--config', '-c', help='Configuration file path')
@click.option('--debug', is_flag=True, help='Enable debug mode')
@click.pass_context
def cli(ctx, config, debug):
    """Twin-Agent Bridge (TAB) CLI."""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config
    ctx.obj['debug'] = debug

    if debug:
        logging.basicConfig(level=logging.DEBUG)


@cli.command()
@click.option('--host', default='localhost', help='Host to bind to')
@click.option('--port', default=8000, type=int, help='Port to bind to')
@click.option('--workers', default=1, type=int, help='Number of worker processes')
@click.option('--reload', is_flag=True, help='Enable auto-reload for development')
@click.pass_context
def serve(ctx, host, port, workers, reload):
    """Start the TAB orchestrator server."""
    try:
        app = TABApplication(config_path=ctx.obj.get('config_path'))
        asyncio.run(app.run_server(host=host, port=port, workers=workers, reload=reload))
    except ConfigurationError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error starting server: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def validate(ctx):
    """Validate the TAB configuration."""
    try:
        config_manager = initialize_config(ctx.obj.get('config_path'))
        config = config_manager.get_config()
        warnings = config_manager.validate_config()

        click.echo("Configuration validation completed successfully!")
        click.echo(f"Configuration file: {config.config_file_path}")
        click.echo(f"Service: {config.observability.service_name}")
        click.echo(f"Environment: {config.observability.environment}")
        click.echo(f"Agents configured: {len(config.agents)}")
        click.echo(f"Policies configured: {len(config.policies)}")

        if warnings:
            click.echo("\nWarnings:")
            for warning in warnings:
                click.echo(f"  - {warning}")
        else:
            click.echo("\nNo warnings found.")

    except ConfigurationError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error validating configuration: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--agent-id', help='Show status for specific agent')
@click.pass_context
def status(ctx, agent_id):
    """Show TAB system status."""
    try:
        config_manager = initialize_config(ctx.obj.get('config_path'))
        config = config_manager.get_config()

        click.echo("TAB System Status")
        click.echo("================")
        click.echo(f"Service: {config.observability.service_name}")
        click.echo(f"Version: {config.observability.service_version}")
        click.echo(f"Environment: {config.observability.environment}")
        click.echo(f"Configuration: {config.config_file_path}")

        if agent_id:
            if agent_id in config.agents:
                agent_config = config.agents[agent_id]
                click.echo(f"\nAgent: {agent_id}")
                click.echo(f"  Type: {agent_config.agent_type}")
                click.echo(f"  Name: {agent_config.name}")
                click.echo(f"  Version: {agent_config.version}")
                click.echo(f"  Enabled: {agent_config.enabled}")
                click.echo(f"  Command: {agent_config.command_path}")
            else:
                click.echo(f"Agent '{agent_id}' not found", err=True)
                sys.exit(1)
        else:
            click.echo(f"\nAgents ({len(config.agents)}):")
            for aid, agent_config in config.agents.items():
                status_indicator = "✓" if agent_config.enabled else "✗"
                click.echo(f"  {status_indicator} {aid} ({agent_config.agent_type})")

            click.echo(f"\nPolicies ({len(config.policies)}):")
            for pid, policy_config in config.policies.items():
                click.echo(f"  - {pid} ({policy_config.permission_mode})")

    except ConfigurationError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error getting status: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.pass_context
def export_config(ctx, output):
    """Export the current configuration."""
    try:
        config_manager = initialize_config(ctx.obj.get('config_path'))
        config = config_manager.get_config()

        config_dict = config.dict()

        if output:
            import yaml
            with open(output, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            click.echo(f"Configuration exported to: {output}")
        else:
            import yaml
            click.echo(yaml.dump(config_dict, default_flow_style=False, indent=2))

    except ConfigurationError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error exporting configuration: {e}", err=True)
        sys.exit(1)


# Conversation Management Commands

@cli.group()
@click.pass_context
def conversation(ctx):
    """Conversation management commands."""
    pass


@conversation.command('start')
@click.argument('topic')
@click.option('--agents', '-a', multiple=True, help='Agent IDs to participate (can specify multiple)')
@click.option('--policy', '-p', default='default', help='Policy configuration to apply')
@click.option('--max-turns', '-t', default=8, type=int, help='Maximum conversation turns')
@click.option('--budget', '-b', default=1.0, type=float, help='Maximum cost budget in USD')
@click.option('--working-dir', '-w', type=click.Path(exists=True), help='Working directory for agents')
@click.option('--output-format', '-f', type=click.Choice(['json', 'yaml', 'text']), default='text', help='Output format')
@click.pass_context
def start_conversation(ctx, topic, agents, policy, max_turns, budget, working_dir, output_format):
    """Start a new conversation between agents."""
    try:
        # Initialize TAB application
        app = TABApplication(config_path=ctx.obj.get('config_path'))
        result = asyncio.run(_start_conversation_impl(
            app, topic, list(agents), policy, max_turns, budget, working_dir, output_format
        ))

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        elif output_format == 'yaml':
            click.echo(yaml.dump(result, default_flow_style=False, indent=2))
        else:
            click.echo(f"Started conversation: {result['session_id']}")
            click.echo(f"Topic: {result['topic']}")
            click.echo(f"Participants: {', '.join(result['participants'])}")
            click.echo(f"Policy: {result['policy_applied']}")
            click.echo(f"Max turns: {result['max_turns']}")
            click.echo(f"Budget: ${result['budget_usd']:.2f}")
            click.echo(f"Status: {result['status']}")
            click.echo(f"Created at: {result['created_at']}")

    except Exception as e:
        click.echo(f"Error starting conversation: {e}", err=True)
        sys.exit(1)


@conversation.command('send')
@click.argument('session_id')
@click.argument('message')
@click.option('--to-agent', '-t', help='Target agent ID (default: auto)')
@click.option('--attach', '-a', multiple=True, help='File attachments (can specify multiple)')
@click.option('--output-format', '-f', type=click.Choice(['json', 'yaml', 'text']), default='text', help='Output format')
@click.pass_context
def send_message(ctx, session_id, message, to_agent, attach, output_format):
    """Send a message in an active conversation."""
    try:
        app = TABApplication(config_path=ctx.obj.get('config_path'))
        result = asyncio.run(_send_message_impl(
            app, session_id, message, to_agent, list(attach), output_format
        ))

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        elif output_format == 'yaml':
            click.echo(yaml.dump(result, default_flow_style=False, indent=2))
        else:
            click.echo(f"Turn ID: {result['turn_id']}")
            click.echo(f"From: {result['response']['from_agent']}")
            click.echo(f"Response: {result['response']['content']}")
            click.echo(f"Session status: {result['session_status']}")
            if result.get('convergence_detected'):
                click.echo("🎯 Convergence detected!")

    except Exception as e:
        click.echo(f"Error sending message: {e}", err=True)
        sys.exit(1)


@conversation.command('status')
@click.argument('session_id')
@click.option('--include-history', is_flag=True, help='Include full conversation history')
@click.option('--output-format', '-f', type=click.Choice(['json', 'yaml', 'text']), default='text', help='Output format')
@click.pass_context
def conversation_status(ctx, session_id, include_history, output_format):
    """Get conversation status and history."""
    try:
        app = TABApplication(config_path=ctx.obj.get('config_path'))
        result = asyncio.run(_get_conversation_status_impl(
            app, session_id, include_history, output_format
        ))

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        elif output_format == 'yaml':
            click.echo(yaml.dump(result, default_flow_style=False, indent=2))
        else:
            click.echo(f"Session ID: {result['session_id']}")
            click.echo(f"Status: {result['status']}")
            click.echo(f"Participants: {', '.join(result['participants'])}")
            click.echo(f"Current turn: {result['current_turn']}")
            click.echo(f"Total cost: ${result['total_cost_usd']:.4f}")
            click.echo(f"Budget remaining: ${result['budget_remaining']['cost_usd']:.4f}")
            click.echo(f"Turns remaining: {result['budget_remaining']['turns']}")
            click.echo(f"Created: {result['created_at']}")
            click.echo(f"Updated: {result['updated_at']}")

            if include_history and 'turn_history' in result:
                click.echo("\nConversation History:")
                click.echo("=" * 50)
                for turn in result['turn_history']:
                    click.echo(f"Turn {turn.get('turn_number', '?')}: {turn['from_agent']} → {turn['to_agent']}")
                    click.echo(f"  {turn['content'][:100]}{'...' if len(turn['content']) > 100 else ''}")
                    click.echo(f"  Time: {turn['timestamp']}")
                    click.echo()

    except Exception as e:
        click.echo(f"Error getting conversation status: {e}", err=True)
        sys.exit(1)


@conversation.command('list')
@click.option('--status', type=click.Choice(['active', 'completed', 'failed', 'timeout']), help='Filter by status')
@click.option('--limit', '-l', default=10, type=int, help='Maximum number of sessions to show')
@click.option('--output-format', '-f', type=click.Choice(['json', 'yaml', 'text']), default='text', help='Output format')
@click.pass_context
def list_conversations(ctx, status, limit, output_format):
    """List conversation sessions."""
    try:
        app = TABApplication(config_path=ctx.obj.get('config_path'))
        result = asyncio.run(_list_conversations_impl(app, status, limit, output_format))

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        elif output_format == 'yaml':
            click.echo(yaml.dump(result, default_flow_style=False, indent=2))
        else:
            click.echo(f"Found {len(result['sessions'])} sessions:")
            click.echo()
            for session in result['sessions']:
                status_icon = {
                    'active': '🟢',
                    'completed': '✅',
                    'failed': '❌',
                    'timeout': '⏰'
                }.get(session['status'], '⚪')

                click.echo(f"{status_icon} {session['session_id'][:8]}... - {session['status']}")
                click.echo(f"   Topic: {session.get('topic', 'N/A')[:60]}{'...' if len(session.get('topic', '')) > 60 else ''}")
                click.echo(f"   Participants: {', '.join(session['participants'])}")
                click.echo(f"   Turns: {session['current_turn']}, Cost: ${session['total_cost_usd']:.4f}")
                click.echo(f"   Created: {session['created_at']}")
                click.echo()

    except Exception as e:
        click.echo(f"Error listing conversations: {e}", err=True)
        sys.exit(1)


@conversation.command('export')
@click.argument('session_id')
@click.option('--format', type=click.Choice(['json', 'csv', 'jsonl']), default='json', help='Export format')
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--include-security', is_flag=True, help='Include security audit events')
@click.pass_context
def export_audit(ctx, session_id, format, output, include_security):
    """Export conversation audit log."""
    try:
        app = TABApplication(config_path=ctx.obj.get('config_path'))
        result = asyncio.run(_export_audit_impl(
            app, session_id, format, output, include_security
        ))

        if output:
            with open(output, 'w') as f:
                f.write(result['audit_data'])
            click.echo(f"Audit log exported to: {output}")
            click.echo(f"Format: {result['format']}")
            click.echo(f"Records: {result['record_count']}")
            click.echo(f"Security events included: {result['security_events_included']}")
        else:
            click.echo(result['audit_data'])

    except Exception as e:
        click.echo(f"Error exporting audit log: {e}", err=True)
        sys.exit(1)


# Implementation functions for conversation commands

async def _start_conversation_impl(
    app: TABApplication,
    topic: str,
    agents: List[str],
    policy: str,
    max_turns: int,
    budget: float,
    working_dir: Optional[str],
    output_format: str
) -> Dict[str, Any]:
    """Implementation for start conversation command."""
    await app.initialize()

    # Default agents if none specified
    if not agents:
        agents = ['claude_code', 'codex_cli']

    # Create conversation session
    session = await app.orchestrator.create_conversation(
        topic=topic,
        participants=agents,
        policy_id=policy,
        max_turns=max_turns,
        budget_usd=budget,
        working_directory=working_dir
    )

    return {
        'session_id': session.session_id,
        'topic': session.topic,
        'participants': session.participants,
        'policy_applied': session.policy_config.name if session.policy_config else policy,
        'max_turns': max_turns,
        'budget_usd': budget,
        'status': session.status,
        'created_at': session.created_at.isoformat()
    }


async def _send_message_impl(
    app: TABApplication,
    session_id: str,
    message: str,
    to_agent: Optional[str],
    attachments: List[str],
    output_format: str
) -> Dict[str, Any]:
    """Implementation for send message command."""
    await app.initialize()

    # Convert file paths to attachment objects
    attachment_objects = []
    for file_path in attachments:
        path = Path(file_path)
        if path.exists():
            attachment_objects.append({
                'path': str(path),
                'type': 'file',
                'size': path.stat().st_size
            })

    # Send message via orchestrator
    result = await app.orchestrator.send_message(
        session_id=session_id,
        content=message,
        to_agent=to_agent or 'auto',
        attachments=attachment_objects
    )

    return result


async def _get_conversation_status_impl(
    app: TABApplication,
    session_id: str,
    include_history: bool,
    output_format: str
) -> Dict[str, Any]:
    """Implementation for get conversation status command."""
    await app.initialize()

    # Get session status from session manager
    status = await app.session_manager.get_session_status(
        session_id=session_id,
        include_history=include_history
    )

    return status


async def _list_conversations_impl(
    app: TABApplication,
    status_filter: Optional[str],
    limit: int,
    output_format: str
) -> Dict[str, Any]:
    """Implementation for list conversations command."""
    await app.initialize()

    # Get sessions from session manager
    sessions = await app.session_manager.list_sessions(
        status_filter=status_filter,
        limit=limit
    )

    return {'sessions': sessions}


async def _export_audit_impl(
    app: TABApplication,
    session_id: str,
    format: str,
    output: Optional[str],
    include_security: bool
) -> Dict[str, Any]:
    """Implementation for export audit command."""
    await app.initialize()

    # Export audit data
    audit_data = await app.session_manager.export_audit_log(
        session_id=session_id,
        format=format,
        include_security_events=include_security
    )

    return {
        'audit_data': audit_data['data'],
        'format': format,
        'record_count': audit_data['record_count'],
        'exported_at': datetime.now().isoformat(),
        'security_events_included': include_security
    }


# Agent Management Commands

@cli.group()
@click.pass_context
def agent(ctx):
    """Agent management commands."""
    pass


@agent.command('list')
@click.option('--include-capabilities', is_flag=True, help='Include agent capabilities')
@click.option('--output-format', '-f', type=click.Choice(['json', 'yaml', 'text']), default='text', help='Output format')
@click.pass_context
def list_agents(ctx, include_capabilities, output_format):
    """List available agents and their status."""
    try:
        app = TABApplication(config_path=ctx.obj.get('config_path'))
        result = asyncio.run(_list_agents_impl(app, include_capabilities, output_format))

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        elif output_format == 'yaml':
            click.echo(yaml.dump(result, default_flow_style=False, indent=2))
        else:
            click.echo(f"Found {len(result['agents'])} agents:")
            click.echo()
            for agent in result['agents']:
                status_icon = {
                    'available': '✅',
                    'busy': '🟡',
                    'failed': '❌',
                    'maintenance': '🔧'
                }.get(agent['status'], '⚪')

                click.echo(f"{status_icon} {agent['agent_id']} ({agent['type']})")
                click.echo(f"   Name: {agent['name']}")
                click.echo(f"   Version: {agent['version']}")
                click.echo(f"   Status: {agent['status']}")
                click.echo(f"   Last health check: {agent['last_health_check']}")

                if include_capabilities and 'capabilities' in agent:
                    click.echo(f"   Capabilities: {', '.join(agent['capabilities'])}")
                click.echo()

    except Exception as e:
        click.echo(f"Error listing agents: {e}", err=True)
        sys.exit(1)


@agent.command('health')
@click.argument('agent_id')
@click.option('--deep-check', is_flag=True, help='Perform deep health check')
@click.option('--output-format', '-f', type=click.Choice(['json', 'yaml', 'text']), default='text', help='Output format')
@click.pass_context
def agent_health(ctx, agent_id, deep_check, output_format):
    """Check agent health and readiness."""
    try:
        app = TABApplication(config_path=ctx.obj.get('config_path'))
        result = asyncio.run(_agent_health_impl(app, agent_id, deep_check, output_format))

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        elif output_format == 'yaml':
            click.echo(yaml.dump(result, default_flow_style=False, indent=2))
        else:
            status_icon = {
                'healthy': '✅',
                'degraded': '🟡',
                'unhealthy': '❌'
            }.get(result['status'], '⚪')

            click.echo(f"Agent {agent_id} Health: {status_icon} {result['status']}")
            click.echo(f"Version: {result['version']}")
            click.echo(f"Uptime: {result['uptime_seconds']} seconds")
            click.echo(f"Capabilities: {', '.join(result['capabilities'])}")

            if 'resource_usage' in result:
                res = result['resource_usage']
                click.echo(f"Resource Usage:")
                click.echo(f"  CPU: {res.get('cpu_percent', 0):.1f}%")
                click.echo(f"  Memory: {res.get('memory_mb', 0):.1f} MB")
                click.echo(f"  Active sessions: {res.get('active_sessions', 0)}")

            if result.get('last_error'):
                click.echo(f"Last error: {result['last_error']}")

    except Exception as e:
        click.echo(f"Error checking agent health: {e}", err=True)
        sys.exit(1)


# Policy Management Commands

@cli.group()
@click.pass_context
def policy(ctx):
    """Policy management commands."""
    pass


@policy.command('list')
@click.option('--output-format', '-f', type=click.Choice(['json', 'yaml', 'text']), default='text', help='Output format')
@click.pass_context
def list_policies(ctx, output_format):
    """List available security policies."""
    try:
        app = TABApplication(config_path=ctx.obj.get('config_path'))
        result = asyncio.run(_list_policies_impl(app, output_format))

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        elif output_format == 'yaml':
            click.echo(yaml.dump(result, default_flow_style=False, indent=2))
        else:
            click.echo(f"Found {len(result['policies'])} policies:")
            click.echo()
            for policy in result['policies']:
                click.echo(f"📋 {policy['policy_id']}")
                click.echo(f"   Name: {policy['name']}")
                click.echo(f"   Description: {policy['description']}")
                click.echo(f"   Permission mode: {policy['permission_mode']}")
                click.echo(f"   Allowed tools: {len(policy.get('allowed_tools', []))}")
                click.echo(f"   Disallowed tools: {len(policy.get('disallowed_tools', []))}")
                click.echo()

    except Exception as e:
        click.echo(f"Error listing policies: {e}", err=True)
        sys.exit(1)


@policy.command('show')
@click.argument('policy_id')
@click.option('--output-format', '-f', type=click.Choice(['json', 'yaml', 'text']), default='text', help='Output format')
@click.pass_context
def show_policy(ctx, policy_id, output_format):
    """Show detailed policy configuration."""
    try:
        app = TABApplication(config_path=ctx.obj.get('config_path'))
        result = asyncio.run(_show_policy_impl(app, policy_id, output_format))

        if output_format == 'json':
            click.echo(json.dumps(result, indent=2))
        elif output_format == 'yaml':
            click.echo(yaml.dump(result, default_flow_style=False, indent=2))
        else:
            policy = result['policy']
            click.echo(f"Policy: {policy['policy_id']}")
            click.echo(f"Name: {policy['name']}")
            click.echo(f"Description: {policy['description']}")
            click.echo(f"Permission mode: {policy['permission_mode']}")
            click.echo()

            click.echo("Allowed tools:")
            for tool in policy.get('allowed_tools', []):
                click.echo(f"  ✅ {tool}")
            click.echo()

            click.echo("Disallowed tools:")
            for tool in policy.get('disallowed_tools', []):
                click.echo(f"  ❌ {tool}")
            click.echo()

            if 'resource_limits' in policy:
                limits = policy['resource_limits']
                click.echo("Resource limits:")
                for key, value in limits.items():
                    click.echo(f"  {key}: {value}")
                click.echo()

            if 'file_access_rules' in policy:
                click.echo("File access rules:")
                for rule in policy['file_access_rules']:
                    click.echo(f"  {rule}")
                click.echo()

    except Exception as e:
        click.echo(f"Error showing policy: {e}", err=True)
        sys.exit(1)


# Implementation functions for agent and policy commands

async def _list_agents_impl(
    app: TABApplication,
    include_capabilities: bool,
    output_format: str
) -> Dict[str, Any]:
    """Implementation for list agents command."""
    await app.initialize()

    # Get agent list from orchestrator
    agents = await app.orchestrator.list_agents(include_capabilities=include_capabilities)
    return {'agents': agents}


async def _agent_health_impl(
    app: TABApplication,
    agent_id: str,
    deep_check: bool,
    output_format: str
) -> Dict[str, Any]:
    """Implementation for agent health command."""
    await app.initialize()

    # Get agent health from orchestrator
    health = await app.orchestrator.check_agent_health(agent_id=agent_id, deep_check=deep_check)
    return health


async def _list_policies_impl(
    app: TABApplication,
    output_format: str
) -> Dict[str, Any]:
    """Implementation for list policies command."""
    await app.initialize()

    # Get policies from policy enforcer
    policies = await app.policy_enforcer.list_policies()
    return {'policies': policies}


async def _show_policy_impl(
    app: TABApplication,
    policy_id: str,
    output_format: str
) -> Dict[str, Any]:
    """Implementation for show policy command."""
    await app.initialize()

    # Get specific policy from policy enforcer
    policy = await app.policy_enforcer.get_policy(policy_id=policy_id)
    return {'policy': policy}


if __name__ == '__main__':
    cli()