"""Agent loop: the core processing engine."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from loguru import logger

from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.bus.queue import MessageBus
from kabot.providers.base import LLMProvider
from kabot.agent.context import ContextBuilder
from kabot.agent.directives import DirectiveParser
from kabot.agent.tools.registry import ToolRegistry
from kabot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from kabot.agent.tools.shell import ExecTool
from kabot.agent.tools.web_search import WebSearchTool
from kabot.agent.tools.web_fetch import WebFetchTool
from kabot.agent.tools.browser import BrowserTool
from kabot.agent.tools.message import MessageTool
from kabot.agent.tools.spawn import SpawnTool
from kabot.agent.tools.cron import CronTool
from kabot.agent.tools.memory import SaveMemoryTool, GetMemoryTool, ListRemindersTool
from kabot.agent.tools.memory_search import MemorySearchTool
from kabot.agent.tools.weather import WeatherTool
from kabot.agent.tools.stock import StockTool, CryptoTool
from kabot.agent.tools.stock_analysis import StockAnalysisTool
from kabot.agent.tools.meta_graph import MetaGraphTool
from kabot.agent.tools.autoplanner import AutoPlanner
from kabot.agent.subagent import SubagentManager
from kabot.agent.router import IntentRouter, RouteDecision
from kabot.session.manager import SessionManager
from kabot.memory.chroma_memory import ChromaMemoryManager
from kabot.memory.vector_store import VectorStore
from kabot.plugins.loader import load_plugins, load_dynamic_plugins
from kabot.plugins.registry import PluginRegistry
from kabot.plugins.hooks import HookManager
from kabot.providers.registry import ModelRegistry

# Phase 8: System Internals
from kabot.core.command_router import CommandRouter, CommandContext
from kabot.core.status import StatusService, BenchmarkService
from kabot.core.doctor import DoctorService
from kabot.core.update import UpdateService, SystemControl
from kabot.core.commands_setup import register_builtin_commands

# Phase 9: Architecture Overhaul
from kabot.core.directives import DirectiveParser
from kabot.core.heartbeat import HeartbeatInjector
from kabot.core.resilience import ResilienceLayer

# Phase 12: Critical Features
from kabot.agent.truncator import ToolResultTruncator
from kabot.agent.cron_fallback_nlp import (
    REMINDER_KEYWORDS,
    WEATHER_KEYWORDS,
)
from kabot.agent.loop_core import directives_runtime as loop_directives_runtime
from kabot.agent.loop_core import execution_runtime as loop_execution_runtime
from kabot.agent.loop_core import message_runtime as loop_message_runtime
from kabot.agent.loop_core import quality_runtime as loop_quality_runtime
from kabot.agent.loop_core import routing_runtime as loop_routing_runtime
from kabot.agent.loop_core import session_flow as loop_session_flow
from kabot.agent.loop_core import tool_enforcement as loop_tool_enforcement

# Phase 13: Resilience & Security
from kabot.core.sentinel import CrashSentinel, format_recovery_message

_APPROVAL_CMD_RE = re.compile(r"^\s*/(approve|deny)(?:\s+([A-Za-z0-9_-]+))?\s*$", re.IGNORECASE)


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        config: Any = None,
        fallbacks: list[str] | None = None,
        max_iterations: int = 20,
        brave_api_key: str | None = None,
        exec_config: Any = None,
        cron_service: Any = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        enable_hybrid_memory: bool = True,
        mode_manager: Any = None,
    ):
        from kabot.config.schema import ExecToolConfig, Config
        from kabot.cron.service import CronService
        from kabot.agent.mode_manager import ModeManager
        from kabot.agent.coordinator import Coordinator

        self.config = config or Config()

        # Initialize mode manager and coordinator
        self.mode_manager = mode_manager or ModeManager(
            Path.home() / ".kabot" / "mode_config.json"
        )
        self.coordinator = Coordinator(bus, "master")
        self.bus = bus
        self.provider = provider
        self.workspace = workspace

        # Resolve model ID using the registry
        self.registry = ModelRegistry()
        raw_model = model or provider.get_default_model()
        self.model = self.registry.resolve(raw_model)
        
        # Resolve fallbacks
        self.fallbacks = [self.registry.resolve(f) for f in (fallbacks or [])]
        
        self.max_iterations = max_iterations
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.exec_auto_approve = bool(getattr(self.exec_config, "auto_approve", False))
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace

        self.context = ContextBuilder(workspace)
        self.sessions = session_manager or SessionManager(workspace)
        self.memory = ChromaMemoryManager(
            workspace / "memory_db",
            enable_hybrid_memory=enable_hybrid_memory
        )
        # Vector store for semantic memory search (Phase 7) - lazy initialization
        self._vector_store = None
        self._vector_store_path = str(workspace / "vector_db")

        # Context management (Phase 11)
        from kabot.agent.context_guard import ContextGuard
        from kabot.agent.compactor import Compactor
        self.context_guard = ContextGuard(max_tokens=128000, buffer_tokens=4000)
        self.compactor = Compactor()

        # Auth rotation (Phase 11)
        from kabot.auth.rotation import AuthRotation
        api_keys = self._collect_api_keys(provider)
        if len(api_keys) > 1:
            self.auth_rotation = AuthRotation(api_keys, cooldown_seconds=300)
            logger.info(f"Auth rotation enabled with {len(api_keys)} keys")
        else:
            self.auth_rotation = None

        self.router = IntentRouter(provider, model=self.model)
        # Phase 14: Pass bus for system event emission (will set run_id per message)
        self.tools = ToolRegistry(bus=bus, run_id=None)
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
            http_guard=getattr(getattr(self.config, "integrations", None), "http_guard", None),
            meta_config=getattr(getattr(self.config, "integrations", None), "meta", None),
        )

        # Plugin system (Phase 6)
        self.plugin_registry = PluginRegistry()
        self.hooks = HookManager()
        self._load_plugins()

        self._running = False
        self._register_default_tools()

        # Phase 8: System Internals â€” Command Router
        self.command_router = CommandRouter()
        self._status_service = StatusService(agent_loop=self)
        self._benchmark_service = BenchmarkService(provider=provider, models=self.fallbacks)
        self._doctor_service = DoctorService(workspace=workspace)
        self._update_service = UpdateService(workspace=workspace)
        self._system_control = SystemControl(workspace=workspace)
        register_builtin_commands(
            router=self.command_router,
            status_service=self._status_service,
            benchmark_service=self._benchmark_service,
            doctor_service=self._doctor_service,
            update_service=self._update_service,
            system_control=self._system_control,
        )

        # Check if we just restarted
        if self._system_control.check_restart_flag():
            logger.info("Bot restarted successfully (restart flag detected)")

        # Phase 9: Architecture Overhaul
        self.directive_parser = DirectiveParser()
        self.heartbeat = HeartbeatInjector()
        self.resilience = ResilienceLayer(
            primary_model=self.model,
            fallback_models=self.fallbacks,
        )

        # Phase 12: Critical Features
        self.truncator = ToolResultTruncator(max_tokens=128000, max_share=0.3)

        # Phase 13: Crash Recovery
        sentinel_path = Path.home() / ".kabot" / "crash.sentinel"
        self.sentinel = CrashSentinel(sentinel_path)

    def _collect_api_keys(self, provider) -> list[str]:
        """Collect all available API keys from provider."""
        keys = []
        if hasattr(provider, 'api_key') and provider.api_key:
            keys.append(provider.api_key)
        # Add support for multiple keys from config in future
        return keys

    def _load_plugins(self) -> None:
        """Load plugins from workspace and builtin directories."""
        # Load from workspace plugins directory
        workspace_plugins = self.workspace / "plugins"
        if workspace_plugins.exists():
            # Load legacy SKILL.md plugins
            loaded = load_plugins(workspace_plugins, self.plugin_registry)
            logger.info(f"Loaded {len(loaded)} SKILL.md plugins from workspace")

            # Load new plugin.json plugins with hooks
            loaded_dynamic = load_dynamic_plugins(workspace_plugins, self.plugin_registry, self.hooks)
            logger.info(f"Loaded {len(loaded_dynamic)} dynamic plugins from workspace")

        # Load from builtin plugins directory (if exists)
        builtin_plugins = Path(__file__).parent.parent / "plugins"
        if builtin_plugins.exists() and builtin_plugins != workspace_plugins:
            loaded = load_plugins(builtin_plugins, self.plugin_registry)
            logger.info(f"Loaded {len(loaded)} SKILL.md builtin plugins")

            loaded_dynamic = load_dynamic_plugins(builtin_plugins, self.plugin_registry, self.hooks)
            logger.info(f"Loaded {len(loaded_dynamic)} dynamic builtin plugins")

    @property
    def vector_store(self) -> VectorStore:
        """Lazy initialization of vector store."""
        if self._vector_store is None:
            try:
                self._vector_store = VectorStore(
                    path=self._vector_store_path,
                    collection_name="kabot_memory"
                )
                logger.info("Vector store initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize vector store: {e}")
                # Return a dummy store that does nothing
                class DummyVectorStore:
                    def search(self, query: str, k: int = 3):
                        return []
                    def add(self, documents: list[str], ids: list[str]):
                        pass
                self._vector_store = DummyVectorStore()
        return self._vector_store

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        self.tools.register(ReadFileTool(allowed_dir=allowed_dir))
        self.tools.register(WriteFileTool(allowed_dir=allowed_dir))
        self.tools.register(EditFileTool(allowed_dir=allowed_dir))
        self.tools.register(ListDirTool(allowed_dir=allowed_dir))

        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.restrict_to_workspace,
            auto_approve=self.exec_auto_approve,
        ))

        self.tools.register(WebSearchTool(
            api_key=self.config.tools.web.search.api_key,
            max_results=self.config.tools.web.search.max_results,
            provider=self.config.tools.web.search.provider,
            perplexity_api_key=self.config.tools.web.search.perplexity_api_key,
            perplexity_model=self.config.tools.web.search.perplexity_model,
            xai_api_key=self.config.tools.web.search.xai_api_key,
            xai_model=self.config.tools.web.search.xai_model,
            cache_ttl_minutes=self.config.tools.web.search.cache_ttl_minutes,
        ))
        self.tools.register(
            WebFetchTool(
                http_guard=getattr(getattr(self.config, "integrations", None), "http_guard", None),
                firecrawl_api_key=self.config.tools.web.fetch.firecrawl_api_key,
                firecrawl_base_url=self.config.tools.web.fetch.firecrawl_base_url,
                cache_ttl_minutes=self.config.tools.web.fetch.cache_ttl_minutes,
            )
        )
        self.tools.register(BrowserTool())

        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)

        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)

        if self.cron_service:
            cron_tool = CronTool(self.cron_service)
            self.tools.register(cron_tool)
            self.tools.register(ListRemindersTool(cron_service=self.cron_service))

        self.tools.register(SaveMemoryTool(memory_manager=self.memory))
        self.tools.register(GetMemoryTool(memory_manager=self.memory))

        # Vector memory search tool (Phase 7)
        self.tools.register(MemorySearchTool(store=self.vector_store))

        self.tools.register(WeatherTool())
        self.tools.register(StockTool())
        self.tools.register(CryptoTool())
        self.tools.register(StockAnalysisTool())
        self.tools.register(MetaGraphTool(config=self.config))

        autoplanner = AutoPlanner(
            tool_registry=self.tools,
            message_bus=self.bus
        )
        self.tools.register(autoplanner)

        # Load plugin-based tools (Phase 6)
        self._register_plugin_tools()

    def _register_plugin_tools(self) -> None:
        """Register tools from loaded plugins."""
        plugins = self.plugin_registry.list_all()
        if not plugins:
            return

        logger.info(f"Registering tools from {len(plugins)} plugins")
        # Note: Plugin tools are currently skill-based (SKILL.md files)
        # They don't register as executable tools but as context/skills
        # Future enhancement: Support plugin-based tool registration
        # For now, plugins are loaded and available via the plugin registry

    def _get_tool_status_message(self, tool_name: str, args: dict) -> str | None:
        """Generate a user-friendly status message for a tool call."""
        try:
            if tool_name == "read_file":
                path = args.get("path") or args.get("file_path")
                return f"Reading `{path}`"
            elif tool_name == "write_file":
                path = args.get("path") or args.get("file_path")
                return f"Writing `{path}`"
            elif tool_name == "edit_file":
                path = args.get("path") or args.get("file_path")
                return f"Editing `{path}`"
            elif tool_name == "list_dir":
                path = args.get("path") or "."
                return f"Checking folder `{path}`"
            elif tool_name == "exec":
                cmd = args.get("command")
                return f"Running: `{cmd}`"
            elif tool_name == "web_search":
                query = args.get("query")
                return f"Searching: '{query}'"
            elif tool_name == "web_fetch":
                url = args.get("url")
                return f"Fetching {url}"
            elif tool_name == "autoplanner":
                goal = args.get("goal")
                return f"Planning: '{goal}'"
            elif tool_name == "spawn":
                agent_type = args.get("agent_type")
                return f"Spawning sub-agent `{agent_type}`"
            elif tool_name == "save_memory":
                return "Saving to memory"
            elif tool_name == "get_memory":
                return "Retrieving memory"
            elif tool_name == "list_reminders":
                return "Checking reminders"
            elif tool_name == "weather":
                location = args.get("location")
                return f"Checking weather in {location}"
            elif tool_name == "stock":
                symbol = args.get("symbol")
                return f"Checking stock {symbol}"
            elif tool_name == "crypto":
                coin = args.get("coin")
                return f"Checking {coin} price"
            elif tool_name == "stock_analysis":
                symbol = args.get("symbol")
                return f"Analyzing {symbol}"
            elif tool_name == "cron":
                return "Scheduling task"
            elif tool_name in ("download-manager", "download_manager"):
                return "Downloading file"
            elif tool_name == "browser":
                action = args.get("action")
                return f"Browser: {action}"
            return None
        except Exception:
            return None

    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")

        # Phase 14: Emit lifecycle start event
        from kabot.bus.events import SystemEvent
        run_id = "agent-loop"
        seq = self.bus.get_next_seq(run_id)
        await self.bus.emit_system_event(
            SystemEvent.lifecycle(run_id, seq, "start", component="agent_loop")
        )

        # Phase 13: Check for crash from previous session
        crash_data = self.sentinel.check_for_crash()
        if crash_data:
            recovery_msg = format_recovery_message(crash_data)
            logger.warning(f"Crash detected, sending recovery message")
            # Send recovery message to the crashed session if we have context
            if crash_data.get('session_id'):
                try:
                    await self.bus.publish_outbound(OutboundMessage(
                        channel="system",
                        chat_id=crash_data.get('session_id', 'unknown'),
                        content=recovery_msg
                    ))
                except Exception as e:
                    logger.error(f"Failed to send recovery message: {e}")

        # Phase 10: Emit ON_STARTUP hook
        await self.hooks.emit("ON_STARTUP")

        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

                    # Phase 14: Emit error event
                    seq = self.bus.get_next_seq(run_id)
                    await self.bus.emit_system_event(
                        SystemEvent.error(
                            run_id, seq, "processing_error", str(e),
                            session_key=msg.session_key
                        )
                    )

                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue

    def stop(self) -> None:
        self._running = False

        # Phase 14: Emit lifecycle stop event
        from kabot.bus.events import SystemEvent
        run_id = "agent-loop"
        seq = self.bus.get_next_seq(run_id)
        asyncio.create_task(
            self.bus.emit_system_event(
                SystemEvent.lifecycle(run_id, seq, "stop", component="agent_loop")
            )
        )

        # Phase 13: Clear sentinel on clean shutdown
        self.sentinel.clear_sentinel()
        logger.info("Agent loop stopping")

    async def _should_use_collaborative_mode(self, msg: InboundMessage) -> bool:
        """Check if collaborative multi-agent mode should be used for this message."""
        user_id = f"user:{msg.channel}:{msg.chat_id}"
        mode = self.mode_manager.get_mode(user_id)
        return mode == "multi"

    async def _process_collaborative(self, msg: InboundMessage) -> OutboundMessage:
        """Process message using collaborative multi-agent mode."""
        # Delegate to brainstorming agent
        task_id = await self.coordinator.delegate_task(
            task=msg.content,
            target_role="brainstorming"
        )

        # Collect results
        result = await self.coordinator.collect_results(task_id)

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=result.get("output", "Task completed"),
            reply_to=msg.message_id
        )

    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        return await loop_message_runtime.process_message(self, msg)

    @staticmethod
    def _parse_approval_command(content: str) -> tuple[str, str | None] | None:
        """Parse /approve or /deny command from user message."""
        if not content:
            return None
        match = _APPROVAL_CMD_RE.match(content.strip())
        if not match:
            return None
        action = match.group(1).lower()
        approval_id = match.group(2)
        return action, approval_id

    async def _process_pending_exec_approval(
        self,
        msg: InboundMessage,
        action: str,
        approval_id: str | None = None,
    ) -> OutboundMessage:
        return await loop_message_runtime.process_pending_exec_approval(
            self,
            msg,
            action=action,
            approval_id=approval_id,
        )

    def _route_context_for_message(self, msg: InboundMessage) -> dict[str, Any]:
        return loop_routing_runtime.route_context_for_message(self, msg)

    def _resolve_route_for_message(self, msg: InboundMessage) -> dict[str, str]:
        return loop_routing_runtime.resolve_route_for_message(self, msg)

    def _get_session_key(self, msg: InboundMessage) -> str:
        return loop_session_flow.get_session_key(self, msg)

    def _resolve_models_for_message(self, msg: InboundMessage) -> list[str]:
        return loop_routing_runtime.resolve_models_for_message(self, msg)

    def _resolve_model_for_message(self, msg: InboundMessage) -> str:
        return loop_routing_runtime.resolve_model_for_message(self, msg)

    def _resolve_agent_id_for_message(self, msg: InboundMessage) -> str:
        return loop_routing_runtime.resolve_agent_id_for_message(self, msg)

    async def _init_session(self, msg: InboundMessage) -> Any:
        return await loop_session_flow.init_session(self, msg)

    async def _run_simple_response(self, msg: InboundMessage, messages: list) -> str | None:
        return await loop_execution_runtime.run_simple_response(self, msg, messages)

    async def _run_agent_loop(self, msg: InboundMessage, messages: list, session: Any) -> str | None:
        return await loop_execution_runtime.run_agent_loop(self, msg, messages, session)

    def _self_evaluate(self, question: str, answer: str) -> tuple[bool, str | None]:
        return loop_quality_runtime.self_evaluate(self, question, answer)

    _IMMEDIATE_ACTION_PATTERNS = loop_quality_runtime.IMMEDIATE_ACTION_PATTERNS

    _REMINDER_KEYWORDS = REMINDER_KEYWORDS
    _WEATHER_KEYWORDS = WEATHER_KEYWORDS

    def _existing_schedule_titles(self) -> list[str]:
        return loop_tool_enforcement.existing_schedule_titles(self)

    def _required_tool_for_query(self, question: str) -> str | None:
        return loop_tool_enforcement.required_tool_for_query_for_loop(self, question)

    def _make_unique_schedule_title(self, base_title: str) -> str:
        return loop_tool_enforcement.make_unique_schedule_title_for_loop(self, base_title)

    def _build_group_id(self, title: str) -> str:
        return loop_tool_enforcement.build_group_id_for_loop(self, title)

    async def _execute_required_tool_fallback(self, required_tool: str, msg: InboundMessage) -> str | None:
        return await loop_tool_enforcement.execute_required_tool_fallback(self, required_tool, msg)

    async def _plan_task(self, question: str) -> str | None:
        return await loop_quality_runtime.plan_task(self, question)

    def _is_weak_model(self, model: str) -> bool:
        return loop_quality_runtime.is_weak_model(self, model)

    async def _critic_evaluate(self, question: str, answer: str, model: str | None = None) -> tuple[int, str]:
        return await loop_quality_runtime.critic_evaluate(self, question, answer, model)

    async def _log_lesson(self, question: str, feedback: str,
                          score_before: int, score_after: int) -> None:
        await loop_quality_runtime.log_lesson(self, question, feedback, score_before, score_after)

    async def _call_llm_with_fallback(self, messages: list, models: list) -> tuple[Any | None, Exception | None]:
        return await loop_execution_runtime.call_llm_with_fallback(self, messages, models)

    async def _process_tool_calls(self, msg: InboundMessage, messages: list, response: Any, session: Any) -> list:
        return await loop_execution_runtime.process_tool_calls(self, msg, messages, response, session)

    def _format_tool_result(self, result: Any) -> str:
        return loop_execution_runtime.format_tool_result(self, result)

    async def _finalize_session(self, msg: InboundMessage, session: Any, final_content: str | None) -> OutboundMessage:
        return await loop_session_flow.finalize_session(self, msg, session, final_content)

    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        return await loop_message_runtime.process_system_message(self, msg)

    async def process_direct(self, content: str, session_key: str = "cli:direct", channel: str = "cli", chat_id: str = "direct") -> str:
        msg = InboundMessage(channel=channel, sender_id="user", chat_id=chat_id, content=content, _session_key=session_key)
        response = await self._process_message(msg)
        return response.content if response else ""

    async def process_isolated(
        self, content: str,
        channel: str = "cli",
        chat_id: str = "direct",
        job_id: str = ""
    ) -> str:
        return await loop_message_runtime.process_isolated(
            self,
            content,
            channel=channel,
            chat_id=chat_id,
            job_id=job_id,
        )

    # Phase 12: Directives Behavior Implementation
    def _apply_think_mode(self, messages: list, session: Any) -> list:
        return loop_directives_runtime.apply_think_mode(self, messages, session)

    def _should_log_verbose(self, session: Any) -> bool:
        return loop_directives_runtime.should_log_verbose(self, session)

    def _format_verbose_output(self, tool_name: str, tool_result: str, tokens_used: int) -> str:
        return loop_directives_runtime.format_verbose_output(self, tool_name, tool_result, tokens_used)

    def _get_tool_permissions(self, session: Any) -> dict:
        return loop_directives_runtime.get_tool_permissions(self, session)