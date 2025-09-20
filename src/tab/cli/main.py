"""
Main CLI application for TAB (Twin-Agent Bridge).

Provides command-line interface for serving the orchestrator and
managing the TAB system.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

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


if __name__ == '__main__':
    cli()