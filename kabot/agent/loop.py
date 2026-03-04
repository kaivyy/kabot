"""Agent loop: the core processing engine."""

import asyncio
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

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
from kabot.agent.tools.registry import ToolRegistry

# Phase 12: Critical Features
from kabot.agent.truncator import ToolResultTruncator
from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.bus.queue import MessageBus

# Phase 8: System Internals
from kabot.core.command_router import CommandRouter
from kabot.core.commands_setup import register_builtin_commands

# Phase 9: Architecture Overhaul
from kabot.core.directives import DirectiveParser
from kabot.core.doctor import DoctorService
from kabot.core.heartbeat import HeartbeatInjector
from kabot.core.msg_context import MsgContext
from kabot.core.resilience import ResilienceLayer
from kabot.core.status import BenchmarkService, StatusService
from kabot.core.update import SystemControl, UpdateService

# Phase 13: Resilience & Security
from kabot.core.sentinel import CrashSentinel, format_recovery_message


from kabot.plugins.hooks import HookManager
from kabot.plugins.loader import load_dynamic_plugins, load_plugins
from kabot.plugins.registry import PluginRegistry
from kabot.providers.base import LLMProvider
from kabot.providers.registry import ModelRegistry
from kabot.session.manager import SessionManager

_APPROVAL_CMD_RE = re.compile(r"^\s*/(approve|deny)(?:\s+([A-Za-z0-9_-]+))?\s*$", re.IGNORECASE)

if TYPE_CHECKING:
    from kabot.agent.context import ContextBuilder


def __getattr__(name: str) -> Any:
    """Lazy compatibility exports for legacy module consumers."""
    if name == "ContextBuilder":
        from kabot.agent.context import ContextBuilder

        return ContextBuilder
    if name == "HybridMemoryManager":
        from kabot.memory import HybridMemoryManager

        return HybridMemoryManager
    if name == "IntentRouter":
        from kabot.agent.router import IntentRouter

        return IntentRouter
    if name == "SubagentManager":
        from kabot.agent.subagent import SubagentManager

        return SubagentManager
    raise AttributeError(f"module 'kabot.agent.loop' has no attribute '{name}'")


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
        from kabot.agent.context import ContextBuilder
        from kabot.agent.coordinator import Coordinator
        from kabot.agent.router import IntentRouter
        from kabot.agent.subagent import SubagentManager
        from kabot.agent.mode_manager import ModeManager
        from kabot.config.schema import Config, ExecToolConfig

        self.config = config or Config()
        self.runtime_resilience = getattr(getattr(self.config, "runtime", None), "resilience", None)
        self.runtime_performance = getattr(getattr(self.config, "runtime", None), "performance", None)
        self.runtime_observability = getattr(getattr(self.config, "runtime", None), "observability", None)
        self.runtime_quotas = getattr(getattr(self.config, "runtime", None), "quotas", None)
        self._boot_started_at = time.perf_counter()
        self._startup_ready_at: float | None = None
        self._cold_start_reported = False
        self._memory_warmup_task: asyncio.Task | None = None
        self._memory_warmup_started_at: float | None = None
        self._memory_warmup_completed_at: float | None = None
        self._memory_warmup_attempted: bool = False
        self._optional_tools_task: asyncio.Task | None = None
        self._optional_tools_loaded: bool = False
        self._pending_memory_tasks: set[asyncio.Task] = set()
        self._tool_payload_cache: dict[str, tuple[float, str]] = {}
        self._tool_call_id_cache: dict[str, tuple[float, str]] = {}

        # Initialize mode manager and coordinator
        self.mode_manager = mode_manager or ModeManager(
            Path.home() / ".kabot" / "mode_config.json"
        )
        self.coordinator = Coordinator(bus, "master")
        self.bus = bus
        configure_inbound_queue = getattr(self.bus, "configure_inbound_queue", None)
        if callable(configure_inbound_queue):
            runtime_queue = getattr(getattr(self.config, "runtime", None), "queue", None)
            try:
                configure_inbound_queue(runtime_queue)
            except Exception as exc:
                logger.warning(f"Failed to configure inbound queue policy: {exc}")
        self.provider = provider
        self.workspace = workspace

        # Resolve model ID using the registry
        self.registry = ModelRegistry()
        raw_model = model or provider.get_default_model()
        self.model = self.registry.resolve(raw_model)

        # Resolve fallbacks
        self.fallbacks = [self.registry.resolve(f) for f in (fallbacks or [])]
        self.last_model_used = self.model
        self.last_fallback_used = False
        self.last_model_chain = [self.model, *self.fallbacks]

        self.max_iterations = max_iterations
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.exec_auto_approve = bool(getattr(self.exec_config, "auto_approve", False))
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace

        self._context_builder_cls = ContextBuilder
        self.context = ContextBuilder(
            workspace,
            skills_config=self.config.skills,
            memory_config=self.config.memory,
        )
        self._context_builders: dict[str, "ContextBuilder"] = {
            str(workspace.expanduser().resolve()): self.context
        }
        self.sessions = session_manager or SessionManager(workspace)
        from kabot.memory.memory_factory import MemoryFactory
        from kabot.config.loader import load_config
        _cfg_obj = load_config()
        # Convert Pydantic model to dict for MemoryFactory
        _cfg = _cfg_obj.model_dump() if hasattr(_cfg_obj, 'model_dump') else _cfg_obj.dict()
        # Allow constructor param to override config
        if not enable_hybrid_memory:
            _cfg.setdefault("memory", {})["enable_hybrid_search"] = False
        self.memory = MemoryFactory.create(_cfg, workspace)
        # Vector store for semantic memory search (Phase 7) - lazy initialization
        self._vector_store = None
        self._vector_store_path = str(workspace / "vector_db")

        # Context management (Phase 11)
        from kabot.agent.compactor import Compactor
        from kabot.agent.context_guard import ContextGuard
        from kabot.agent.loop_core.tool_loop_detection import LoopDetector
        self.context_guard = ContextGuard(max_tokens=128000, buffer_tokens=4000)
        self.compactor = Compactor()
        self.loop_detector = LoopDetector(history_size=30, warning_threshold=10, critical_threshold=20)

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
            web_search_config=self.config.tools.web.search,
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
        self._status_service = None
        self._benchmark_service = None
        self._doctor_service = None
        self._update_service = None
        self._system_control = None
        register_builtin_commands(
            router=self.command_router,
            status_service=self.status_service,
            benchmark_service=self.benchmark_service,
            doctor_service=self.doctor_service,
            update_service=self.update_service,
            system_control=self.system_control,
        )

        # Check if we just restarted
        if self._system_control.check_restart_flag():
            logger.info("Bot restarted successfully (restart flag detected)")

        # Phase 9: Architecture Overhaul
        from kabot.core.directives import DirectiveParser
        self.directive_parser = DirectiveParser()
        self.heartbeat = HeartbeatInjector()
        self.heartbeat.set_publisher(self._publish_heartbeat_event)
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

    async def _publish_heartbeat_event(self, ctx: MsgContext) -> None:
        from kabot.bus.events import InboundMessage
        channel = ctx.event_data.get("target_channel") or "cli"
        chat_id = ctx.event_data.get("target_chat") or "direct"
        msg = InboundMessage(
            channel=channel,
            sender_id="system",
            chat_id=chat_id,
            content=ctx.body,
            timestamp=ctx.timestamp,
            metadata={
                "system_event": True,
                "event_type": ctx.event_type or "",
                "event_data": ctx.event_data or {},
            },
        )
        await self.bus.publish_inbound(msg)

    @staticmethod
    def _resolve_recovery_target(crash_data: dict[str, Any] | None) -> tuple[str, str] | None:
        """Resolve outbound channel/chat target for crash recovery message."""
        if not isinstance(crash_data, dict):
            return None

        def _is_reserved(channel: str) -> bool:
            base_channel = channel.split(":", 1)[0].lower()
            return base_channel in {"agent", "background", "system"}

        def _parse_from_message_id(raw: Any) -> tuple[str, str] | None:
            if not isinstance(raw, str):
                return None
            parts = [part.strip() for part in raw.split(":")]
            if len(parts) < 3:
                return None
            # message_id shape: <channel>:<chat_id>:<sender_id>
            # channel may itself include ":" for instance-aware routing.
            channel = ":".join(parts[:-2]).lower()
            chat_id = parts[-2]
            if not channel or not chat_id:
                return None
            if _is_reserved(channel):
                return None
            return channel, chat_id

        def _parse_from_session_id(raw: Any) -> tuple[str, str] | None:
            if not isinstance(raw, str):
                return None
            parts = [part.strip() for part in raw.split(":")]
            if len(parts) < 2:
                return None
            channel = parts[0].lower()
            chat_id = parts[1]
            if not channel or not chat_id:
                return None
            if _is_reserved(channel):
                return None
            return channel, chat_id

        target = _parse_from_message_id(crash_data.get("message_id"))
        if target:
            return target
        return _parse_from_session_id(crash_data.get("session_id"))

    @property
    def status_service(self) -> Any:
        if self._status_service is None:
            from kabot.core.status import StatusService
            self._status_service = StatusService(self)
        return self._status_service

    @property
    def benchmark_service(self) -> Any:
        if self._benchmark_service is None:
            from kabot.core.status import BenchmarkService
            self._benchmark_service = BenchmarkService(self.provider)
        return self._benchmark_service

    @property
    def doctor_service(self) -> Any:
        if self._doctor_service is None:
            from kabot.core.doctor import DoctorService
            self._doctor_service = DoctorService(self.workspace)
        return self._doctor_service

    @property
    def update_service(self) -> Any:
        if self._update_service is None:
            from kabot.core.update import UpdateService
            self._update_service = UpdateService(self.workspace)
        return self._update_service

    @property
    def system_control(self) -> Any:
        if self._system_control is None:
            from kabot.core.update import SystemControl
            self._system_control = SystemControl(self.workspace)
        return self._system_control

    @property
    def vector_store(self) -> Any:
        if self._vector_store is None:
            from kabot.memory.vector_store import VectorStore
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

    def _resolve_workspace_for_agent(self, agent_id: str | None) -> Path:
        """Resolve workspace path for a routed agent, with safe fallback to root workspace."""
        if not agent_id:
            return self.workspace
        try:
            from kabot.agent.agent_scope import resolve_agent_workspace

            resolved = resolve_agent_workspace(self.config, agent_id)
            return resolved or self.workspace
        except Exception as exc:
            logger.warning(f"Failed to resolve workspace for agent '{agent_id}': {exc}")
            return self.workspace

    def _context_for_workspace(self, workspace: Path) -> "ContextBuilder":
        """Return cached ContextBuilder for workspace or create one lazily."""
        key = str(workspace.expanduser().resolve())
        context = self._context_builders.get(key)
        if context is not None:
            return context
        context = self._context_builder_cls(
            workspace,
            skills_config=self.config.skills,
            memory_config=self.config.memory,
        )
        self._context_builders[key] = context
        return context

    def _resolve_context_for_message(self, msg: InboundMessage) -> "ContextBuilder":
        """Resolve context builder bound to routed agent workspace for this message."""
        agent_id = self._resolve_agent_id_for_message(msg)
        workspace = self._resolve_workspace_for_agent(agent_id)
        return self._context_for_workspace(workspace)

    def _resolve_context_for_channel_chat(self, channel: str, chat_id: str) -> "ContextBuilder":
        """Resolve context builder for synthetic/system flows using channel/chat route."""
        probe = InboundMessage(
            channel=channel,
            sender_id="system",
            chat_id=chat_id,
            content="",
        )
        return self._resolve_context_for_message(probe)

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        from kabot.agent.tools.autoplanner import AutoPlanner
        from kabot.agent.tools.browser import BrowserTool
        from kabot.agent.tools.cron import CronTool
        from kabot.agent.tools.filesystem import (
            EditFileTool,
            ListDirTool,
            ReadFileTool,
            WriteFileTool,
        )
        from kabot.agent.tools.knowledge import KnowledgeLearnTool
        from kabot.agent.tools.memory import GetMemoryTool, ListRemindersTool, SaveMemoryTool
        from kabot.agent.tools.memory_search import MemorySearchTool
        from kabot.agent.tools.message import MessageTool
        from kabot.agent.tools.meta_graph import MetaGraphTool
        from kabot.agent.tools.shell import ExecTool
        from kabot.agent.tools.spawn import SpawnTool
        from kabot.agent.tools.speedtest import SpeedtestTool
        from kabot.agent.tools.stock import CryptoTool, StockTool
        from kabot.agent.tools.stock_analysis import StockAnalysisTool
        from kabot.agent.tools.weather import WeatherTool
        from kabot.agent.tools.web_fetch import WebFetchTool
        from kabot.agent.tools.web_search import WebSearchTool

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
            policy_preset=str(getattr(self.exec_config, "policy_preset", "strict")),
        ))

        # Optional Google Suite tools are loaded in background after startup
        # to keep cold-start path responsive.
        self.tools.register(KnowledgeLearnTool(workspace=self.workspace))

        self.tools.register(WebSearchTool(
            api_key=self.config.tools.web.search.api_key,
            max_results=self.config.tools.web.search.max_results,
            provider=self.config.tools.web.search.provider,
            perplexity_api_key=self.config.tools.web.search.perplexity_api_key,
            perplexity_model=self.config.tools.web.search.perplexity_model,
            xai_api_key=self.config.tools.web.search.xai_api_key,
            xai_model=self.config.tools.web.search.xai_model,
            kimi_api_key=self.config.tools.web.search.kimi_api_key,
            kimi_model=self.config.tools.web.search.kimi_model,
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
        self.tools.register(SpeedtestTool())
        self.tools.register(BrowserTool())

        from kabot.agent.tools.system import SystemInfoTool, ProcessMemoryTool
        self.tools.register(SystemInfoTool())
        self.tools.register(ProcessMemoryTool())

        from kabot.agent.tools.update import CheckUpdateTool, SystemUpdateTool
        self.tools.register(CheckUpdateTool())
        self.tools.register(SystemUpdateTool())

        from kabot.agent.tools.cleanup import CleanupTool
        self.tools.register(CleanupTool())

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
        self.tools.register(MemorySearchTool(store=lambda: self.vector_store))

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

    def _build_optional_tools(self) -> list[Any]:
        """Build optional heavy tools in a worker thread."""
        from kabot.agent.tools.google_suite import (
            GmailTool,
            GoogleCalendarTool,
            GoogleDocsTool,
            GoogleDriveTool,
        )
        from kabot.agent.tools.graph_memory import GraphMemoryTool

        return [
            GmailTool(),
            GoogleCalendarTool(),
            GoogleDriveTool(),
            GoogleDocsTool(),
            GraphMemoryTool(memory_manager=self.memory),
        ]

    async def _load_optional_tools(self) -> None:
        """Load optional heavy tools without blocking startup-critical path."""
        if self._optional_tools_loaded:
            return
        started_at = time.perf_counter()
        try:
            optional_tools = await asyncio.to_thread(self._build_optional_tools)
            for tool in optional_tools:
                if not self.tools.has(tool.name):
                    self.tools.register(tool)
            self._optional_tools_loaded = True
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            logger.info(
                f"optional_tools_loaded count={len(optional_tools)} duration_ms={elapsed_ms}"
            )
        except Exception as exc:
            logger.warning(f"Optional tools load skipped: {exc}")

    def _ensure_optional_tools_task(self) -> None:
        """Schedule optional tool loading once."""
        if self._optional_tools_loaded:
            return
        if self._optional_tools_task and not self._optional_tools_task.done():
            return
        self._optional_tools_task = asyncio.create_task(self._load_optional_tools())

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
            elif tool_name == "get_process_memory":
                return "Checking RAM usage by process"
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
            elif tool_name == "graph_memory":
                return "Querying graph memory"
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

    async def _warmup_memory(self):
        """Background warmup of embedding model so first message is fast."""
        self._memory_warmup_attempted = True
        self._memory_warmup_started_at = time.perf_counter()
        try:
            timeout_ms = int(getattr(self.runtime_performance, "embed_warmup_timeout_ms", 1200))
            if timeout_ms > 0:
                await asyncio.wait_for(self.memory.warmup(), timeout=timeout_ms / 1000.0)
            else:
                await self.memory.warmup()
            self._memory_warmup_completed_at = time.perf_counter()
            warmup_ms = int((self._memory_warmup_completed_at - self._memory_warmup_started_at) * 1000)
            logger.info(f"memory_warmup_ms={warmup_ms}")
        except asyncio.TimeoutError:
            logger.warning("Memory warmup timeout reached; continuing with lazy loading")
        except Exception as e:
            logger.warning(f"Memory warmup failed (will lazy-load later): {e}")

    def _ensure_memory_warmup_task(self) -> None:
        """Start memory warmup task once (non-blocking)."""
        if self._memory_warmup_attempted:
            return
        if self._memory_warmup_task and not self._memory_warmup_task.done():
            return
        self._memory_warmup_task = asyncio.create_task(self._warmup_memory())

    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        defer_warmup = bool(getattr(self.runtime_performance, "defer_memory_warmup", True))
        if not defer_warmup:
            self._ensure_memory_warmup_task()
        else:
            logger.info("Memory warmup deferred (fast-first-response mode)")
        self._ensure_optional_tools_task()

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
            logger.warning("Crash detected, sending recovery message")
            recovery_target = self._resolve_recovery_target(crash_data)
            if recovery_target:
                channel, chat_id = recovery_target
                try:
                    await self.bus.publish_outbound(
                        OutboundMessage(channel=channel, chat_id=chat_id, content=recovery_msg)
                    )
                except Exception as e:
                    logger.error(f"Failed to send recovery message: {e}")
            else:
                logger.warning(
                    "Skipping recovery message: no valid channel/chat target in crash data "
                    f"(session_id={crash_data.get('session_id')}, message_id={crash_data.get('message_id')})"
                )

        # Phase 10: Emit ON_STARTUP hook
        await self.hooks.emit("ON_STARTUP")
        self._startup_ready_at = time.perf_counter()
        startup_ready_ms = int((self._startup_ready_at - self._boot_started_at) * 1000)
        logger.info(f"startup_ready_ms={startup_ready_ms}")

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

        # Best-effort cancel pending async memory writes.
        for task in list(self._pending_memory_tasks):
            if not task.done():
                task.cancel()
        self._pending_memory_tasks.clear()

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

        content = "Task completed"
        if isinstance(result, dict):
            content = str(result.get("output") or result.get("summary") or content)
        elif isinstance(result, list):
            outputs = []
            for item in result:
                if isinstance(item, dict):
                    outputs.append(str(item.get("output") or item.get("summary") or ""))
                else:
                    outputs.append(str(item))
            compacted = [o for o in outputs if o]
            if compacted:
                content = "\n\n".join(compacted)
        else:
            content = str(result)

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=content,
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
