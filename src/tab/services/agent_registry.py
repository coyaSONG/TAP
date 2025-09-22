"""Agent registry for dynamic agent loading and management.

Provides centralized agent registration, discovery, and lifecycle management
supporting multiple loading strategies including entry points and plugins.
"""

import asyncio
import importlib
import logging
import time
from typing import Dict, List, Optional, Type, Any, Set
from datetime import datetime
from contextlib import asynccontextmanager

from src.tab.models.agent_config import (
    DynamicAgentConfig, AgentRegistration, AgentLoadingStrategy,
    AgentLoadingResult, AgentPluginManifest
)
from src.tab.lib.async_adapter import ThreadPoolAdapter, sync_to_async


logger = logging.getLogger(__name__)


class AgentLoadingError(Exception):
    """Raised when agent loading fails."""
    pass


class AgentRegistry:
    """Registry for dynamic agent loading and management."""

    def __init__(self, thread_pool_adapter: Optional[ThreadPoolAdapter] = None):
        self.logger = logging.getLogger(__name__)
        self.thread_pool = thread_pool_adapter or ThreadPoolAdapter()

        # Agent registrations
        self._registrations: Dict[str, AgentRegistration] = {}
        self._agent_classes: Dict[str, Type] = {}
        self._plugin_manifests: Dict[str, AgentPluginManifest] = {}

        # Loading state
        self._loading_tasks: Dict[str, asyncio.Task] = {}
        self._discovery_cache: Dict[str, List[str]] = {}
        self._last_discovery_time: Optional[datetime] = None

    async def register_agent(
        self,
        config: DynamicAgentConfig,
        force_reload: bool = False
    ) -> AgentLoadingResult:
        """Register and load an agent with given configuration.

        Args:
            config: Agent configuration
            force_reload: Whether to force reload if already registered

        Returns:
            Agent loading result
        """
        start_time = time.time()
        agent_id = config.agent_id

        try:
            # Check if already registered
            if agent_id in self._registrations and not force_reload:
                existing = self._registrations[agent_id]
                if existing.is_healthy:
                    return AgentLoadingResult(
                        agent_id=agent_id,
                        success=True,
                        loading_strategy_used=config.loading_strategy,
                        load_time_ms=(time.time() - start_time) * 1000,
                        agent_class=str(self._agent_classes.get(agent_id)),
                        discovered_capabilities=existing.discovered_capabilities
                    )

            # Load agent based on strategy
            agent_class = await self._load_agent_class(config)

            # Validate agent class
            await self._validate_agent_class(agent_class, config)

            # Discover capabilities
            capabilities = await self._discover_capabilities(agent_class, config)

            # Create registration
            registration = AgentRegistration(
                agent_id=agent_id,
                config=config,
                registration_time=datetime.utcnow(),
                health_status="healthy",
                discovered_capabilities=capabilities
            )

            # Store registration
            self._registrations[agent_id] = registration
            self._agent_classes[agent_id] = agent_class

            load_time = (time.time() - start_time) * 1000
            self.logger.info(f"Agent {agent_id} registered successfully in {load_time:.2f}ms")

            return AgentLoadingResult(
                agent_id=agent_id,
                success=True,
                loading_strategy_used=config.loading_strategy,
                load_time_ms=load_time,
                agent_class=str(agent_class),
                discovered_capabilities=capabilities
            )

        except Exception as e:
            load_time = (time.time() - start_time) * 1000
            self.logger.error(f"Failed to register agent {agent_id}: {e}")

            return AgentLoadingResult(
                agent_id=agent_id,
                success=False,
                loading_strategy_used=config.loading_strategy,
                load_time_ms=load_time,
                error_type=type(e).__name__,
                error_message=str(e)
            )

    async def _load_agent_class(self, config: DynamicAgentConfig) -> Type:
        """Load agent class based on loading strategy."""
        strategy = config.loading_strategy

        if strategy == AgentLoadingStrategy.BUILTIN:
            return await self._load_builtin_agent(config)
        elif strategy == AgentLoadingStrategy.ENTRY_POINT:
            return await self._load_entry_point_agent(config)
        elif strategy == AgentLoadingStrategy.MODULE_CLASS:
            return await self._load_module_class_agent(config)
        elif strategy == AgentLoadingStrategy.PLUGIN:
            return await self._load_plugin_agent(config)
        else:
            raise AgentLoadingError(f"Unsupported loading strategy: {strategy}")

    async def _load_builtin_agent(self, config: DynamicAgentConfig) -> Type:
        """Load built-in agent type."""
        builtin_agents = {
            "claude_code": "src.tab.services.claude_code_adapter.ClaudeCodeAdapter",
            "codex_cli": "src.tab.services.codex_adapter.CodexAdapter",
            "generic": "src.tab.services.base_agent_adapter.BaseAgentAdapter"
        }

        agent_type = config.agent_type
        if agent_type not in builtin_agents:
            # For dynamic agent types, use generic adapter
            module_path = "src.tab.services.base_agent_adapter"
            class_name = "BaseAgentAdapter"
        else:
            module_class = builtin_agents[agent_type]
            module_path, class_name = module_class.rsplit('.', 1)

        return await self._import_class(module_path, class_name)

    async def _load_entry_point_agent(self, config: DynamicAgentConfig) -> Type:
        """Load agent from entry point."""
        entry_point = config.entry_point
        if not entry_point:
            raise AgentLoadingError("Entry point name is required")

        # Use thread pool for entry point discovery
        @sync_to_async(timeout=10.0, operation_name=f"load_entry_point_{entry_point}")
        def discover_entry_point():
            try:
                import pkg_resources
                for ep in pkg_resources.iter_entry_points('tab.agents', entry_point):
                    return ep.load()
                raise AgentLoadingError(f"Entry point '{entry_point}' not found")
            except ImportError:
                # Fallback for newer Python versions
                try:
                    from importlib.metadata import entry_points
                    eps = entry_points(group='tab.agents')
                    for ep in eps:
                        if ep.name == entry_point:
                            return ep.load()
                    raise AgentLoadingError(f"Entry point '{entry_point}' not found")
                except ImportError:
                    raise AgentLoadingError("Entry point loading not supported")

        return await discover_entry_point()

    async def _load_module_class_agent(self, config: DynamicAgentConfig) -> Type:
        """Load agent from module and class name."""
        module_path = config.module_path
        class_name = config.class_name

        if not module_path or not class_name:
            raise AgentLoadingError("Module path and class name are required")

        return await self._import_class(module_path, class_name)

    async def _load_plugin_agent(self, config: DynamicAgentConfig) -> Type:
        """Load agent from plugin package."""
        plugin_package = config.plugin_package
        if not plugin_package:
            raise AgentLoadingError("Plugin package name is required")

        # Load plugin manifest
        manifest = await self._load_plugin_manifest(plugin_package)
        self._plugin_manifests[config.agent_id] = manifest

        # Find appropriate entry point
        agent_type = config.agent_type
        if agent_type not in manifest.entry_points:
            raise AgentLoadingError(f"Agent type '{agent_type}' not found in plugin manifest")

        entry_point = manifest.entry_points[agent_type]
        module_path, class_name = entry_point.rsplit('.', 1)

        return await self._import_class(module_path, class_name)

    async def _import_class(self, module_path: str, class_name: str) -> Type:
        """Import class from module path."""
        @sync_to_async(timeout=5.0, operation_name=f"import_{module_path}")
        def import_module_class():
            try:
                module = importlib.import_module(module_path)
                agent_class = getattr(module, class_name)
                if not isinstance(agent_class, type):
                    raise AgentLoadingError(f"{class_name} is not a class")
                return agent_class
            except ImportError as e:
                raise AgentLoadingError(f"Failed to import {module_path}: {e}")
            except AttributeError as e:
                raise AgentLoadingError(f"Class {class_name} not found in {module_path}: {e}")

        return await import_module_class()

    async def _load_plugin_manifest(self, plugin_package: str) -> AgentPluginManifest:
        """Load plugin manifest from package."""
        @sync_to_async(timeout=5.0, operation_name=f"load_manifest_{plugin_package}")
        def load_manifest():
            try:
                import json
                manifest_module = importlib.import_module(f"{plugin_package}.manifest")
                if hasattr(manifest_module, 'MANIFEST'):
                    manifest_data = manifest_module.MANIFEST
                elif hasattr(manifest_module, 'get_manifest'):
                    manifest_data = manifest_module.get_manifest()
                else:
                    raise AgentLoadingError("No manifest found in plugin")

                return AgentPluginManifest(**manifest_data)
            except ImportError as e:
                raise AgentLoadingError(f"Failed to load plugin manifest: {e}")

        return await load_manifest()

    async def _validate_agent_class(self, agent_class: Type, config: DynamicAgentConfig) -> None:
        """Validate that agent class meets requirements."""
        # Check if it's a subclass of BaseAgentAdapter (if available)
        try:
            from src.tab.services.base_agent_adapter import BaseAgentAdapter
            if not issubclass(agent_class, BaseAgentAdapter):
                raise AgentLoadingError(f"Agent class must inherit from BaseAgentAdapter")
        except ImportError:
            # BaseAgentAdapter not available, skip validation
            pass

        # Check required methods exist
        required_methods = ['initialize', 'start', 'stop', 'process_message']
        for method in required_methods:
            if not hasattr(agent_class, method):
                self.logger.warning(f"Agent class {agent_class.__name__} missing method: {method}")

    async def _discover_capabilities(self, agent_class: Type, config: DynamicAgentConfig) -> List[str]:
        """Discover agent capabilities."""
        capabilities = list(config.static_capabilities)

        if config.capability_discovery:
            # Try to discover capabilities from agent class
            if hasattr(agent_class, 'get_capabilities'):
                try:
                    discovered = await self._call_agent_method(agent_class, 'get_capabilities')
                    if isinstance(discovered, list):
                        capabilities.extend(discovered)
                except Exception as e:
                    self.logger.warning(f"Failed to discover capabilities: {e}")

            # Add default capabilities based on agent type
            type_capabilities = {
                "claude_code": ["code_analysis", "file_operations"],
                "codex_cli": ["code_generation", "execution"],
                "generic": ["text_processing"]
            }

            if config.agent_type in type_capabilities:
                capabilities.extend(type_capabilities[config.agent_type])

        return list(set(capabilities))  # Remove duplicates

    async def _call_agent_method(self, agent_class: Type, method_name: str, *args, **kwargs) -> Any:
        """Call agent method safely."""
        if hasattr(agent_class, method_name):
            method = getattr(agent_class, method_name)
            if asyncio.iscoroutinefunction(method):
                return await method(*args, **kwargs)
            else:
                return await self.thread_pool.run_in_thread(method, *args, **kwargs)
        else:
            raise AttributeError(f"Method {method_name} not found")

    async def get_agent_class(self, agent_id: str) -> Optional[Type]:
        """Get registered agent class by ID."""
        return self._agent_classes.get(agent_id)

    async def get_registration(self, agent_id: str) -> Optional[AgentRegistration]:
        """Get agent registration by ID."""
        return self._registrations.get(agent_id)

    async def list_agents(self, include_unhealthy: bool = False) -> List[AgentRegistration]:
        """List registered agents."""
        agents = list(self._registrations.values())
        if not include_unhealthy:
            agents = [agent for agent in agents if agent.is_healthy]
        return agents

    async def health_check(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Perform health check on agents."""
        if agent_id:
            registration = self._registrations.get(agent_id)
            if not registration:
                return {"healthy": False, "error": "Agent not found"}

            # Perform health check on specific agent
            try:
                agent_class = self._agent_classes.get(agent_id)
                if agent_class and hasattr(agent_class, 'health_check'):
                    result = await self._call_agent_method(agent_class, 'health_check')
                    registration.health_status = "healthy" if result else "unhealthy"
                    registration.last_health_check = datetime.utcnow()
                    return {"healthy": result}
                else:
                    return {"healthy": True, "note": "No health check method available"}
            except Exception as e:
                registration.health_status = "unhealthy"
                registration.last_error = str(e)
                return {"healthy": False, "error": str(e)}
        else:
            # Check all agents
            results = {}
            for agent_id in self._registrations:
                results[agent_id] = await self.health_check(agent_id)
            return results

    async def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent."""
        if agent_id not in self._registrations:
            return False

        try:
            # Stop agent if it has stop method
            agent_class = self._agent_classes.get(agent_id)
            if agent_class and hasattr(agent_class, 'stop'):
                await self._call_agent_method(agent_class, 'stop')
        except Exception as e:
            self.logger.warning(f"Error stopping agent {agent_id}: {e}")

        # Remove from registrations
        del self._registrations[agent_id]
        if agent_id in self._agent_classes:
            del self._agent_classes[agent_id]
        if agent_id in self._plugin_manifests:
            del self._plugin_manifests[agent_id]

        self.logger.info(f"Agent {agent_id} unregistered")
        return True

    async def shutdown(self) -> None:
        """Shutdown registry and all registered agents."""
        self.logger.info("Shutting down agent registry")

        # Cancel loading tasks
        for task in self._loading_tasks.values():
            if not task.done():
                task.cancel()

        # Wait for tasks to complete
        if self._loading_tasks:
            await asyncio.gather(*self._loading_tasks.values(), return_exceptions=True)

        # Unregister all agents
        agent_ids = list(self._registrations.keys())
        for agent_id in agent_ids:
            await self.unregister_agent(agent_id)

        # Shutdown thread pool
        await self.thread_pool.shutdown()

        self.logger.info("Agent registry shutdown complete")

    @asynccontextmanager
    async def managed_agent(self, config: DynamicAgentConfig):
        """Context manager for automatic agent cleanup."""
        result = await self.register_agent(config)
        if not result.success:
            raise AgentLoadingError(f"Failed to load agent: {result.error_message}")

        try:
            yield self._registrations[config.agent_id]
        finally:
            await self.unregister_agent(config.agent_id)