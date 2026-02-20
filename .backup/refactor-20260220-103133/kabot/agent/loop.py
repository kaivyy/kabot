"""Agent loop: the core processing engine."""

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
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

        # Phase 8: System Internals — Command Router
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

        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(
            WebFetchTool(
                http_guard=getattr(getattr(self.config, "integrations", None), "http_guard", None)
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


        if msg.channel == "system":
            return await self._process_system_message(msg)

        approval_action = self._parse_approval_command(msg.content)
        if approval_action:
            action, approval_id = approval_action
            return await self._process_pending_exec_approval(msg, action=action, approval_id=approval_id)

        # Phase 8: Intercept slash commands BEFORE routing to LLM
        if self.command_router.is_command(msg.content):
            ctx = CommandContext(
                message=msg.content,
                args=[],
                sender_id=msg.sender_id,
                channel=msg.channel,
                chat_id=msg.chat_id,
                session_key=msg.session_key,
                agent_loop=self,
            )
            result = await self.command_router.route(msg.content, ctx)
            if result:
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=result,
                )

        session = await self._init_session(msg)

        # Phase 9: Parse directives from message body
        clean_body, directives = self.directive_parser.parse(msg.content)
        effective_content = clean_body or msg.content

        # Store directives in session metadata
        if directives.raw_directives:
            active = self.directive_parser.format_active_directives(directives)
            logger.info(f"Directives active: {active}")
            
            session.metadata['directives'] = {
                'think': directives.think,
                'verbose': directives.verbose,
                'elevated': directives.elevated,
            }
            # Ensure metadata persists
            self.sessions.save(session)

        # Phase 9: Model override via directive
        if directives.model:
            logger.info(f"Directive override: model → {directives.model}")

        conversation_history = self.memory.get_conversation_context(msg.session_key, max_messages=30)

        # Router triase: SIMPLE vs COMPLEX
        decision = await self.router.route(effective_content)
        logger.info(f"Route: profile={decision.profile}, complex={decision.is_complex}")

        messages = self.context.build_messages(
            history=conversation_history,
            current_message=effective_content,
            media=msg.media if hasattr(msg, 'media') else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
            profile=decision.profile,
            tool_names=self.tools.tool_names,
        )

        if decision.is_complex:
            final_content = await self._run_agent_loop(msg, messages, session)
        else:
            final_content = await self._run_simple_response(msg, messages)

        return await self._finalize_session(msg, session, final_content)

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
        """Handle explicit approval commands for pending exec actions."""
        session = await self._init_session(msg)
        exec_tool = self.tools.get("exec")
        if not exec_tool or not hasattr(exec_tool, "consume_pending_approval"):
            return await self._finalize_session(
                msg,
                session,
                "No executable approval flow is available in this session.",
            )

        if action == "deny":
            cleared = exec_tool.clear_pending_approval(msg.session_key, approval_id)
            if cleared:
                return await self._finalize_session(
                    msg,
                    session,
                    "Pending command approval denied.",
                )
            return await self._finalize_session(
                msg,
                session,
                "No matching pending command approval found.",
            )

        pending = exec_tool.consume_pending_approval(msg.session_key, approval_id)
        if not pending:
            return await self._finalize_session(
                msg,
                session,
                "No matching pending command approval found.",
            )

        command = pending.get("command")
        if not isinstance(command, str) or not command.strip():
            return await self._finalize_session(
                msg,
                session,
                "Pending approval entry is invalid.",
            )

        working_dir = pending.get("working_dir")
        result = await exec_tool.execute(
            command=command,
            working_dir=working_dir if isinstance(working_dir, str) else None,
            _session_key=msg.session_key,
            _approved_by_user=True,
        )
        return await self._finalize_session(msg, session, result)

    def _route_context_for_message(self, msg: InboundMessage) -> dict[str, Any]:
        """Build normalized routing context from message + channel instance metadata."""
        metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
        instance_meta = metadata.get("channel_instance") if isinstance(metadata.get("channel_instance"), dict) else {}

        account_id = msg.account_id
        instance_id = instance_meta.get("id")
        if not account_id and isinstance(instance_id, (str, int)):
            account_id = str(instance_id)

        peer_kind = msg.peer_kind
        peer_id = msg.peer_id
        if not peer_kind and metadata.get("is_group") is True:
            peer_kind = "group"
        elif not peer_kind and msg.chat_id:
            peer_kind = "direct"
        if not peer_id and msg.chat_id:
            peer_id = msg.chat_id

        peer = None
        if isinstance(peer_kind, str) and peer_kind and isinstance(peer_id, str) and peer_id:
            peer = {"kind": peer_kind, "id": peer_id}

        parent_peer = msg.parent_peer if isinstance(msg.parent_peer, dict) else None

        forced_agent_id = None
        if isinstance(instance_meta.get("agent_binding"), str) and instance_meta["agent_binding"].strip():
            forced_agent_id = instance_meta["agent_binding"].strip()

        return {
            "channel": msg.channel,
            "account_id": account_id,
            "forced_agent_id": forced_agent_id,
            "peer": peer,
            "parent_peer": parent_peer,
            "guild_id": msg.guild_id,
            "team_id": msg.team_id,
            "thread_id": msg.thread_id,
        }

    def _resolve_route_for_message(self, msg: InboundMessage) -> dict[str, str]:
        """Resolve OpenClaw-compatible route for a message with instance-aware context."""
        from kabot.routing.bindings import resolve_agent_route

        ctx = self._route_context_for_message(msg)
        return resolve_agent_route(
            config=self.config,
            channel=ctx["channel"],
            account_id=ctx["account_id"],
            forced_agent_id=ctx["forced_agent_id"],
            peer=ctx["peer"],
            parent_peer=ctx["parent_peer"],
            guild_id=ctx["guild_id"],
            team_id=ctx["team_id"],
            thread_id=ctx["thread_id"],
        )

    def _get_session_key(self, msg: InboundMessage) -> str:
        """Get session key with OpenClaw-compatible agent routing."""
        route = self._resolve_route_for_message(msg)
        return route["session_key"]

    def _resolve_models_for_message(self, msg: InboundMessage) -> list[str]:
        """Resolve model chain for this message, including per-agent fallback overrides."""
        from kabot.agent.agent_scope import resolve_agent_model, resolve_agent_model_fallbacks

        route = self._resolve_route_for_message(msg)
        agent_id = route["agent_id"]

        primary = self.model
        fallback_models = list(self.fallbacks)

        agent_model = resolve_agent_model(self.config, agent_id)
        if agent_model:
            primary = self.registry.resolve(agent_model)

            # OpenClaw-compatible behavior: per-agent fallbacks override global fallbacks.
            agent_fallbacks = resolve_agent_model_fallbacks(self.config, agent_id)
            if agent_fallbacks:
                fallback_models = [self.registry.resolve(m) for m in agent_fallbacks]

        chain: list[str] = []
        seen: set[str] = set()
        for model in [primary, *fallback_models]:
            resolved = self.registry.resolve(model)
            if resolved in seen:
                continue
            seen.add(resolved)
            chain.append(resolved)
        return chain

    def _resolve_model_for_message(self, msg: InboundMessage) -> str:
        """Resolve the model to use for this message based on agent routing.

        This implements per-agent model assignment with fallbacks (OpenClaw-compatible):
        - If the agent has a model override, use it
        - If the agent has fallbacks, they override global fallbacks
        - Otherwise, use the default model (self.model)

        Args:
            msg: The inbound message to resolve model for

        Returns:
            The model string to use for this message
        """
        return self._resolve_models_for_message(msg)[0]

    def _resolve_agent_id_for_message(self, msg: InboundMessage) -> str:
        """Resolve routed agent id for this message."""
        route = self._resolve_route_for_message(msg)
        return route["agent_id"]

    async def _init_session(self, msg: InboundMessage) -> Any:
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}: {msg.content[:80]}...")

        # Get session key with agent routing and set it on the message
        # Only generate new session key if one isn't already set
        if not msg._session_key:
            session_key = self._get_session_key(msg)
            msg._session_key = session_key
        else:
            session_key = msg._session_key

        # Phase 14: Set run_id for tool event tracking
        run_id = f"msg-{session_key}-{msg.timestamp.timestamp()}"
        self.tools._run_id = run_id

        # Phase 13: Mark session active before processing (crash recovery)
        message_id = f"{msg.channel}:{msg.chat_id}:{msg.sender_id}"
        self.sentinel.mark_session_active(
            session_id=session_key,
            message_id=message_id,
            user_message=msg.content
        )

        session = self.sessions.get_or_create(session_key)
        self.memory.create_session(session_key, msg.channel, msg.chat_id, msg.sender_id)
        await self.memory.add_message(session_key, "user", msg.content)

        for tool_name in ["message", "spawn", "cron"]:
            tool = self.tools.get(tool_name)
            if hasattr(tool, "set_context"):
                logger.debug(f"Setting context for {tool_name}: {msg.channel}:{msg.chat_id}")
                tool.set_context(msg.channel, msg.chat_id)

        for tool_name in ["save_memory", "get_memory", "list_reminders"]:
            tool = self.tools.get(tool_name)
            if hasattr(tool, "set_context"):
                tool.set_context(session_key)

        # Phase 13: Set session context for spawn tool (for persistent registry)
        spawn_tool = self.tools.get("spawn")
        if spawn_tool and hasattr(spawn_tool, "set_session_context"):
            spawn_tool.set_session_context(session_key)

        return session

    async def _run_simple_response(self, msg: InboundMessage, messages: list) -> str | None:
        """Direct single-shot response for simple queries (no loop, no tools)."""
        try:
            # Resolve model for this agent
            model = self._resolve_model_for_message(msg)

            # Check for context overflow and compact if needed
            if self.context_guard.check_overflow(messages, model):
                logger.warning("Context overflow detected in simple response, compacting history")
                messages = await self.compactor.compact(
                    messages, self.provider, model, keep_recent=10
                )
                # Verify compaction was successful
                if self.context_guard.check_overflow(messages, model):
                    logger.warning("Context still over limit after compaction")

            response = await self.provider.chat(
                messages=messages,
                model=model,
            )
            return response.content or ""
        except Exception as e:
            logger.error(f"Simple response failed: {e}")
            return f"Sorry, an error occurred: {str(e)}"

    async def _run_agent_loop(self, msg: InboundMessage, messages: list, session: Any) -> str | None:
        """
        Full Planner→Executor→Critic loop for complex tasks.

        Phase 1 (Plan): Ask LLM to decompose task + success criteria
        Phase 2 (Execute): Tool calling loop (existing behavior)
        Phase 3 (Critic): Score result 0-10, retry if < 7
        """
        iteration = 0

        # Resolve model chain for this agent.
        models_to_try = self._resolve_models_for_message(msg)
        model = models_to_try[0]

        self_eval_retried = False
        critic_retried = 0
        tool_enforcement_retried = False
        required_tool = self._required_tool_for_query(msg.content)
        tools_executed = False

        # Adaptive critic system: weaker models get more lenient thresholds
        is_weak_model = self._is_weak_model(model)
        max_critic_retries = 1 if is_weak_model else 2  # Reduce retries for weak models
        critic_threshold = 5 if is_weak_model else 7    # Lower threshold for weak models

        first_score = None
        already_published = False  # Track if we already sent content to user

        # Phase 1: Planning — inject plan into context (skip for simple tool tasks)
        plan = await self._plan_task(msg.content)
        if plan:
            messages.append({"role": "user", "content": f"[SYSTEM PLAN]\n{plan}\n\nNow execute this plan step by step."})

        # Phase 12: Apply think mode before loop starts (only once)
        messages = self._apply_think_mode(messages, session)

        while iteration < self.max_iterations:
            iteration += 1

            # Check for context overflow and compact if needed
            if self.context_guard.check_overflow(messages, model):
                logger.warning("Context overflow detected, compacting history")
                messages = await self.compactor.compact(
                    messages, self.provider, model, keep_recent=10
                )
                # Verify compaction was successful
                if self.context_guard.check_overflow(messages, model):
                    logger.warning("Context still over limit after compaction")

            response, error = await self._call_llm_with_fallback(messages, models_to_try)
            if not response:
                return f"Sorry, all available models failed. Last error: {str(error)}"

            if required_tool and response.has_tool_calls:
                if any(tc.name == required_tool for tc in response.tool_calls):
                    # Required tool has been emitted; allow normal finalization turn.
                    required_tool = None
                    tool_enforcement_retried = False
            if response.has_tool_calls:
                tools_executed = True

            if required_tool and not response.has_tool_calls:
                if not tool_enforcement_retried:
                    tool_enforcement_retried = True
                    logger.warning(
                        f"Tool enforcement: expected '{required_tool}' but got text-only response (iter {iteration})"
                    )
                    if response.content:
                        messages = self.context.add_assistant_message(
                            messages, response.content, reasoning_content=response.reasoning_content
                        )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"SYSTEM: For this request, you MUST call the '{required_tool}' tool now. "
                                "Do not answer from memory or estimation. Return a tool call."
                            ),
                        }
                    )
                    continue

                fallback_result = await self._execute_required_tool_fallback(required_tool, msg)
                if fallback_result is not None:
                    logger.warning(f"Tool enforcement fallback executed for '{required_tool}'")
                    return fallback_result

            if response.content:
                # Self-evaluation: detect refusal patterns before sending to user
                if not response.has_tool_calls and not self_eval_retried:
                    passed, nudge = self._self_evaluate(msg.content, response.content)
                    if not passed and nudge:
                        self_eval_retried = True
                        logger.warning(f"Self-eval: refusal detected, retrying (iter {iteration})")
                        messages = self.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
                        messages.append({"role": "user", "content": nudge})
                        continue

                # Phase 3: Critic — score before sending final response (adaptive for weak models)
                if (
                    not response.has_tool_calls
                    and critic_retried < max_critic_retries
                    and not is_weak_model
                    and not tools_executed
                ):
                    score, feedback = await self._critic_evaluate(msg.content, response.content, model)
                    if first_score is None:
                        first_score = score

                    if score < critic_threshold and critic_retried < max_critic_retries:
                        critic_retried += 1
                        logger.warning(f"Critic: score {score}/10 (threshold: {critic_threshold}), retrying ({critic_retried}/{max_critic_retries})")
                        messages = self.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
                        messages.append({"role": "user", "content": (
                            f"[CRITIC FEEDBACK - Score: {score}/10]\n{feedback}\n\n"
                            f"Please improve your response based on this feedback."
                        )})
                        continue
                    else:
                        # Log lesson if we had to retry
                        if critic_retried > 0:
                            await self._log_lesson(
                                question=msg.content,
                                feedback=feedback,
                                score_before=first_score or 0,
                                score_after=score,
                            )

                # Only publish intermediate content if there are more tool calls coming
                if response.has_tool_calls:
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id, content=response.content
                    ))
                    already_published = True

                messages = self.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
                if not response.has_tool_calls:
                    # Final response — DON'T publish here, let _finalize_session handle it
                    return response.content

            if response.has_tool_calls:
                messages = await self._process_tool_calls(msg, messages, response, session)
            else:
                return response.content
        return "I've completed processing but have no response to give."

    def _self_evaluate(self, question: str, answer: str) -> tuple[bool, str | None]:
        """Quick heuristic: detect common failure patterns (no extra LLM call)."""
        if not answer or len(answer) < 30:
            return True, None

        answer_lower = answer.lower()

        # Multilingual refusal patterns (EN, ID, ES, FR, DE, PT, RU, JA, ZH, KO)
        refusal_patterns = [
            # English
            "i cannot", "i can't", "i don't have access", "i'm unable to",
            "i am unable to", "cannot access", "i'm not able to",
            # Indonesian
            "saya tidak bisa", "saya tidak dapat", "saya tidak memiliki akses",
            "tidak dapat mengakses",
            # Spanish
            "no puedo", "no tengo acceso",
            # French
            "je ne peux pas", "je n'ai pas accès",
            # German
            "ich kann nicht", "ich habe keinen zugriff",
            # Portuguese
            "não consigo", "não tenho acesso",
            # Russian
            "я не могу", "у меня нет доступа",
            # Japanese
            "できません", "アクセスできません",
            # Chinese
            "我无法", "我不能", "无法访问",
            # Korean
            "할 수 없", "접근할 수 없",
        ]

        has_refusal = any(p in answer_lower for p in refusal_patterns)
        if has_refusal and len(self.tools.tool_names) > 0:
            tool_list = ", ".join(self.tools.tool_names)
            return False, (
                f"SYSTEM: You said you cannot do something, but you have these tools: {tool_list}. "
                f"Use the appropriate tool instead of refusing. For example, use 'read_file' to read files, "
                f"'exec' to run commands, 'web_search' to search the web. Try again and actually use a tool."
            )

        return True, None

    # Patterns for immediate-action tasks that should NEVER go through planning
    _IMMEDIATE_ACTION_PATTERNS = [
        # Reminders / scheduling (multilingual)
        "remind", "reminder", "schedule", "alarm",
        "ingatkan", "bangunkan", "jadwalkan", "pengingat",
        "timer", "wake me",
        # Weather
        "weather", "cuaca", "suhu", "temperature",
        # Quick lookups
        "stock", "crypto", "saham", "harga",
        # Time queries
        "what time", "jam berapa",
    ]

    _REMINDER_KEYWORDS = (
        "remind", "reminder", "schedule", "alarm", "timer", "wake me",
        "ingatkan", "pengingat", "jadwalkan", "bangunkan", "set sekarang",
        "jadwal", "cron", "shift",
    )

    _WEATHER_KEYWORDS = (
        "weather", "temperature", "forecast", "cuaca", "suhu", "temperatur", "prakiraan",
    )

    def _required_tool_for_query(self, question: str) -> str | None:
        """Return required tool for immediate-action query types."""
        q_lower = (question or "").lower()
        if any(k in q_lower for k in self._WEATHER_KEYWORDS) and self.tools.has("weather"):
            return "weather"
        cron_management_ops = ("list", "lihat", "show", "hapus", "delete", "remove", "edit", "ubah", "update")
        cron_management_terms = ("reminder", "pengingat", "jadwal", "cron", "shift")
        if (
            any(op in q_lower for op in cron_management_ops)
            and any(term in q_lower for term in cron_management_terms)
            and self.tools.has("cron")
        ):
            return "cron"
        if any(k in q_lower for k in self._REMINDER_KEYWORDS) and self.tools.has("cron"):
            return "cron"
        return None

    def _extract_weather_location(self, question: str) -> str | None:
        """Extract probable weather location from user query."""
        text = (question or "").strip()
        if not text:
            return None

        match = re.search(r"(?i)\b(?:di|in)\s+([a-zA-Z][\w\s\-,'\.]{1,80})", text)
        if match:
            candidate = match.group(1).strip(" .,!?:;")
            candidate = re.sub(r"(?i)\b(hari ini|today|sekarang|now)\b", "", candidate).strip(" .,!?:;")
            if candidate:
                return " ".join(part.capitalize() for part in candidate.split())

        candidate = re.sub(
            r"(?i)\b(tolong|please|cek|check|cuaca|weather|suhu|temperature|forecast|prakiraan|hari ini|today|sekarang|now|dong|ya)\b",
            " ",
            text,
        )
        candidate = re.sub(r"\s+", " ", candidate).strip(" .,!?:;")
        if not candidate:
            return None
        return " ".join(part.capitalize() for part in candidate.split())

    def _extract_reminder_message(self, question: str) -> str:
        """Extract reminder payload text from natural-language query."""
        text = (question or "").strip()
        if not text:
            return "Reminder"

        text = re.sub(r"(?i)^(tolong|please)\s+", "", text)
        text = re.sub(
            r"(?i)\b(remind(?: me)?(?: to)?|ingatkan(?: saya)?(?: untuk)?|buat(?:kan)? pengingat|pengingat|set(?: sekarang)?)\b",
            " ",
            text,
        )
        text = re.sub(
            r"(?i)\b(?:dalam|in)?\s*\d+\s*(menit|jam|detik|hari|min(?:ute)?s?|hours?|sec(?:ond)?s?|days?)\b(?:\s+lagi)?",
            " ",
            text,
        )
        text = re.sub(
            r"(?i)\b(?:setiap|tiap|every)\s+\d+\s*(detik|menit|jam|hari|sec(?:ond)?s?|min(?:ute)?s?|hours?|days?)\b(?:\s+sekali)?",
            " ",
            text,
        )
        text = re.sub(
            r"(?i)\b(?:setiap\s+hari|tiap\s+hari|every\s+day|daily)\b(?:\s*(?:jam|pukul|at))?\s*\d{1,2}(?::\d{2})?",
            " ",
            text,
        )
        text = re.sub(
            r"(?i)\b(?:setiap|tiap|every)\s+(?:senin|selasa|rabu|kamis|jumat|sabtu|minggu|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b(?:\s*(?:jam|pukul|at))?\s*\d{1,2}(?::\d{2})?",
            " ",
            text,
        )
        text = re.sub(r"(?i)\b(lagi|from now|sekarang|now)\b", " ", text)
        text = re.sub(r"\s+", " ", text).strip(" .,!?:;")

        if not text:
            return "Reminder"
        if len(text) > 180:
            text = text[:180].rstrip()
        return text

    def _parse_time_token(self, token: str) -> tuple[int, int] | None:
        """Parse HH[:.]MM or HH token into (hour, minute)."""
        raw = (token or "").strip()
        if not raw:
            return None

        normalized = raw.replace(".", ":")
        if ":" in normalized:
            parts = normalized.split(":", 1)
            if len(parts) != 2:
                return None
            try:
                hour = int(parts[0])
                minute = int(parts[1])
            except ValueError:
                return None
        else:
            try:
                hour = int(normalized)
            except ValueError:
                return None
            minute = 0

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        return hour, minute

    def _extract_cycle_anchor_date(self, question: str) -> datetime:
        """Resolve cycle anchor date from natural-language hints."""
        now_local = datetime.now().astimezone()
        q_lower = (question or "").lower()

        explicit_iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", q_lower)
        if explicit_iso:
            try:
                date_part = datetime.strptime(explicit_iso.group(1), "%Y-%m-%d")
                return now_local.replace(
                    year=date_part.year,
                    month=date_part.month,
                    day=date_part.day,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            except ValueError:
                pass

        explicit_dmy = re.search(r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b", q_lower)
        if explicit_dmy:
            try:
                day = int(explicit_dmy.group(1))
                month = int(explicit_dmy.group(2))
                year = int(explicit_dmy.group(3))
                return now_local.replace(
                    year=year,
                    month=month,
                    day=day,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            except ValueError:
                pass

        if "lusa" in q_lower:
            return (now_local + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
        if "besok" in q_lower or "tomorrow" in q_lower:
            return (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    def _extract_explicit_schedule_title(self, question: str) -> str | None:
        """Extract explicit schedule title from phrases like 'judul ...' or 'title ...'."""
        text = (question or "").strip()
        if not text:
            return None

        match = re.search(
            r'(?i)\b(?:judul|title|nama jadwal|schedule name)\b\s*[:=]?\s*[\"\']?([^\"\',;\n]+)',
            text,
        )
        if not match:
            return None
        title = re.sub(r"\s+", " ", match.group(1)).strip(" .,!?:;")
        return title or None

    def _extract_new_schedule_title(self, question: str) -> str | None:
        """Extract rename target from phrases like 'ubah judul jadi ...'."""
        text = (question or "").strip()
        if not text:
            return None
        match = re.search(
            r'(?i)\b(?:ubah judul|rename|rename to|judul baru|new title)\b(?:\s+grp_[a-z0-9_-]+)?\s*(?:jadi|to)\s*[\"\']?([^\"\',;\n]+)',
            text,
        )
        if not match:
            match = re.search(
                r'(?i)\b(?:ubah judul|rename|rename to|judul baru|new title)\b\s*[:=]\s*[\"\']?([^\"\',;\n]+)',
                text,
            )
        if not match:
            return None
        value = re.sub(r"\s+", " ", match.group(1)).strip(" .,!?:;")
        return value or None

    def _make_unique_schedule_title(self, base_title: str) -> str:
        """Ensure group title is unique among existing cron groups."""
        base = re.sub(r"\s+", " ", (base_title or "").strip())
        if not base:
            base = "Schedule"

        existing_titles: set[str] = set()
        if self.cron_service:
            try:
                for job in self.cron_service.list_jobs(include_disabled=True):
                    title = (job.payload.group_title or "").strip()
                    if title:
                        existing_titles.add(title.casefold())
            except Exception:
                pass

        if base.casefold() not in existing_titles:
            return base

        idx = 2
        while True:
            candidate = f"{base} ({idx})"
            if candidate.casefold() not in existing_titles:
                return candidate
            idx += 1

    def _build_group_id(self, title: str) -> str:
        """Build stable unique group id from title + timestamp."""
        slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
        if not slug:
            slug = "schedule"
        slug = slug[:24]
        stamp = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        return f"grp_{slug}_{stamp % 1_000_000:06d}"

    def _extract_cycle_schedule(self, question: str) -> dict[str, Any] | None:
        """Extract complex repeating cycle schedules (shift/work/rest blocks)."""
        text = (question or "").strip()
        if not text:
            return None

        lowered = text.lower()
        # Avoid misclassifying simple reminder prompts as cycle definitions.
        if "selama" not in lowered:
            return None
        if not any(k in lowered for k in ("libur", "berulang", "repeat", "cycle", "siklus")):
            return None

        chunks = [
            chunk.strip(" .,!?:;")
            for chunk in re.split(
                r"(?i)\b(?:setelah itu|setelahnya|lalu|kemudian|dan besoknya|besoknya|terus)\b|[,;]",
                text,
            )
            if chunk and chunk.strip(" .,!?:;")
        ]
        if not chunks:
            return None

        segments: list[dict[str, Any]] = []
        for chunk in chunks:
            chunk_lower = chunk.lower()
            if "libur" in chunk_lower:
                off_match = re.search(r"(?i)\b(\d+)\s*hari\b", chunk)
                off_days = int(off_match.group(1)) if off_match else 1
                if off_days > 0:
                    segments.append({"type": "off", "days": off_days})
                continue

            days_match = re.search(r"(?i)\b(\d+)\s*hari\b", chunk)
            if not days_match:
                continue
            days = int(days_match.group(1))
            if days <= 0:
                continue

            start_time: tuple[int, int] | None = None
            end_time: tuple[int, int] | None = None

            range_match = re.search(
                r"(?i)(\d{1,2}(?:[:.]\d{2})?)\s*(?:-|sampai|hingga|to)\s*(\d{1,2}(?:[:.]\d{2})?)",
                chunk,
            )
            if range_match:
                start_time = self._parse_time_token(range_match.group(1))
                end_time = self._parse_time_token(range_match.group(2))
            else:
                single_match = re.search(
                    r"(?i)(?:jam|pukul|at)\s*(\d{1,2}(?:[:.]\d{2})?)",
                    chunk,
                )
                if single_match:
                    start_time = self._parse_time_token(single_match.group(1))
                else:
                    bare_match = re.search(r"(?i)\b(\d{1,2}(?:[:.]\d{2})?)\b", chunk)
                    if bare_match:
                        start_time = self._parse_time_token(bare_match.group(1))

            if not start_time:
                continue

            label = chunk
            label = re.sub(r"(?i)\b(\d{1,2}(?:[:.]\d{2})?)\s*(?:-|sampai|hingga|to)\s*(\d{1,2}(?:[:.]\d{2})?)\b", " ", label)
            label = re.sub(r"(?i)\b(?:jam|pukul|at)\s*\d{1,2}(?:[:.]\d{2})?\b", " ", label)
            label = re.sub(r"(?i)\b(?:selama|for)\s*\d+\s*hari\b", " ", label)
            label = re.sub(
                r"(?i)\b(?:ingatkan|ingatkan saya|jadwalkan|masuk|shift|kerja|hari ini|besok|tomorrow|lusa|berulang|repeat|terus)\b",
                " ",
                label,
            )
            label = re.sub(r"\s+", " ", label).strip(" .,!?:;")
            if not label:
                label = "Reminder"

            segments.append(
                {
                    "type": "work",
                    "days": days,
                    "label": label,
                    "start": start_time,
                    "end": end_time,
                }
            )

        if not segments:
            return None

        period_days = sum(int(seg["days"]) for seg in segments)
        if period_days < 2:
            return None

        work_segments = [seg for seg in segments if seg["type"] == "work"]
        if not work_segments:
            return None

        anchor = self._extract_cycle_anchor_date(text)
        events: list[dict[str, str]] = []
        day_offset = 0
        for seg in segments:
            days = int(seg["days"])
            if seg["type"] == "off":
                day_offset += days
                continue

            start_h, start_m = seg["start"]
            end = seg.get("end")
            label = str(seg["label"])

            for idx in range(days):
                run_date = anchor + timedelta(days=day_offset + idx)
                start_dt = run_date.replace(hour=start_h, minute=start_m, second=0, microsecond=0)

                if end:
                    end_h, end_m = end
                    end_dt = run_date.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
                    if end_dt <= start_dt:
                        end_dt += timedelta(days=1)
                    window = f"{start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d}"
                    events.append(
                        {
                            "start_at": start_dt.isoformat(timespec="seconds"),
                            "message": f"{label} mulai ({window})",
                        }
                    )
                    events.append(
                        {
                            "start_at": end_dt.isoformat(timespec="seconds"),
                            "message": f"{label} selesai ({window})",
                        }
                    )
                else:
                    events.append(
                        {
                            "start_at": start_dt.isoformat(timespec="seconds"),
                            "message": label,
                        }
                    )
            day_offset += days

        if not events:
            return None

        return {
            "period_days": period_days,
            "events": events,
        }

    def _build_cycle_title(self, question: str, period_days: int) -> str:
        """Build human-friendly unique title for cycle schedules."""
        explicit_title = self._extract_explicit_schedule_title(question)
        if explicit_title:
            return self._make_unique_schedule_title(explicit_title)

        q_lower = (question or "").lower()
        if any(k in q_lower for k in ("shift", "pagi", "sore", "malam", "masuk")):
            base = f"Shift Cycle {period_days} Hari"
        else:
            base = f"Reminder Cycle {period_days} Hari"
        return self._make_unique_schedule_title(base)

    def _extract_recurring_schedule(self, question: str) -> dict[str, Any] | None:
        """Extract recurring cron schedule from natural-language query."""
        text = (question or "").strip()
        if not text:
            return None

        # Interval schedule: "tiap 4 jam", "setiap 30 menit", "every 2 hours"
        interval_match = re.search(
            r"(?i)\b(?:setiap|tiap|every)\s+(\d+)\s*(detik|menit|jam|hari|sec(?:ond)?s?|min(?:ute)?s?|hours?|days?)\b",
            text,
        )
        if interval_match:
            amount = int(interval_match.group(1))
            unit = interval_match.group(2).lower()
            if amount > 0:
                multiplier = 0
                if unit.startswith(("detik", "sec")):
                    multiplier = 1
                elif unit.startswith(("menit", "min")):
                    multiplier = 60
                elif unit.startswith(("jam", "hour")):
                    multiplier = 3600
                elif unit.startswith(("hari", "day")):
                    multiplier = 86400

                if multiplier > 0:
                    return {
                        "every_seconds": amount * multiplier,
                        "one_shot": False,
                    }

        # Daily schedule: "setiap hari jam 09:30", "every day at 9"
        daily_match = re.search(
            r"(?i)\b(?:setiap\s+hari|tiap\s+hari|every\s+day|daily)\b(?:\s*(?:jam|pukul|at))?\s*(\d{1,2})(?::(\d{2}))?",
            text,
        )
        if daily_match:
            hour = int(daily_match.group(1))
            minute = int(daily_match.group(2) or "0")
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return {
                    "cron_expr": f"{minute} {hour} * * *",
                    "one_shot": False,
                }

        # Weekly schedule: "setiap senin jam 08:00", "every monday at 8"
        weekday_map = {
            "minggu": 0,
            "sunday": 0,
            "senin": 1,
            "monday": 1,
            "selasa": 2,
            "tuesday": 2,
            "rabu": 3,
            "wednesday": 3,
            "kamis": 4,
            "thursday": 4,
            "jumat": 5,
            "friday": 5,
            "sabtu": 6,
            "saturday": 6,
        }
        weekly_match = re.search(
            r"(?i)\b(?:setiap|tiap|every)\s+(senin|selasa|rabu|kamis|jumat|sabtu|minggu|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b(?:\s*(?:jam|pukul|at))?\s*(\d{1,2})(?::(\d{2}))?",
            text,
        )
        if weekly_match:
            day = weekday_map.get(weekly_match.group(1).lower())
            hour = int(weekly_match.group(2))
            minute = int(weekly_match.group(3) or "0")
            if day is not None and 0 <= hour <= 23 and 0 <= minute <= 59:
                return {
                    "cron_expr": f"{minute} {hour} * * {day}",
                    "one_shot": False,
                }

        return None

    async def _execute_required_tool_fallback(self, required_tool: str, msg: InboundMessage) -> str | None:
        """Deterministic fallback when the model keeps skipping required tools."""
        if required_tool == "weather":
            location = self._extract_weather_location(msg.content)
            if not location:
                return "Saya butuh lokasi untuk cek cuaca. Contoh: cek suhu Cilacap."
            result = await self.tools.execute("weather", {"location": location})
            return str(result)

        if required_tool == "cron":
            from kabot.cron.parse import parse_absolute_time_ms, parse_relative_time_ms

            q_lower = (msg.content or "").lower()
            management_ops = ("list", "lihat", "show", "hapus", "delete", "remove", "edit", "ubah", "update")
            management_terms = ("reminder", "pengingat", "jadwal", "cron", "shift")
            is_management = any(op in q_lower for op in management_ops) and any(
                term in q_lower for term in management_terms
            )

            if is_management and any(k in q_lower for k in ("list", "lihat", "show")):
                result = await self.tools.execute("cron", {"action": "list_groups"})
                return str(result)

            if is_management and any(k in q_lower for k in ("hapus", "delete", "remove")):
                group_id_match = re.search(r"\bgrp_[a-z0-9_-]+\b", q_lower)
                if group_id_match:
                    result = await self.tools.execute(
                        "cron",
                        {"action": "remove_group", "group_id": group_id_match.group(0)},
                    )
                    return str(result)

                title = self._extract_explicit_schedule_title(msg.content)
                if title:
                    result = await self.tools.execute(
                        "cron",
                        {"action": "remove_group", "title": title},
                    )
                    return str(result)

                job_id_match = re.search(r"\b[a-f0-9]{8}\b", q_lower)
                if job_id_match:
                    result = await self.tools.execute(
                        "cron",
                        {"action": "remove", "job_id": job_id_match.group(0)},
                    )
                    return str(result)

                return (
                    "Untuk hapus jadwal, sebutkan `group_id` atau judul jadwal. "
                    "Gunakan dulu: `list reminder` untuk melihat daftar grup."
                )

            if is_management and any(k in q_lower for k in ("edit", "ubah", "update")):
                selector_payload: dict[str, Any] = {}
                group_id_match = re.search(r"\bgrp_[a-z0-9_-]+\b", q_lower)
                if group_id_match:
                    selector_payload["group_id"] = group_id_match.group(0)
                else:
                    title = self._extract_explicit_schedule_title(msg.content)
                    if title:
                        selector_payload["title"] = title

                if not selector_payload:
                    return (
                        "Untuk edit jadwal, sebutkan `group_id` atau judul jadwal. "
                        "Gunakan dulu: `list reminder` untuk melihat daftar grup."
                    )

                update_payload: dict[str, Any] = {"action": "update_group", **selector_payload}
                recurring_update = self._extract_recurring_schedule(msg.content)
                if recurring_update:
                    update_payload.update(recurring_update)

                new_title = self._extract_new_schedule_title(msg.content)
                if new_title:
                    update_payload["new_title"] = self._make_unique_schedule_title(new_title)

                if len(update_payload) <= 2:
                    return (
                        "Format edit belum lengkap. Contoh: "
                        "`ubah jadwal grp_shift_a tiap 12 jam` atau "
                        "`ubah judul grp_shift_a jadi Shift Team A`."
                    )

                result = await self.tools.execute("cron", update_payload)
                return str(result)

            cycle_schedule = self._extract_cycle_schedule(msg.content)
            if cycle_schedule:
                every_seconds = int(cycle_schedule["period_days"]) * 86400
                group_title = self._build_cycle_title(msg.content, int(cycle_schedule["period_days"]))
                group_id = self._build_group_id(group_title)
                last_result: Any = None
                created_jobs = 0
                for event in cycle_schedule["events"]:
                    payload = {
                        "action": "add",
                        "message": event["message"],
                        "title": group_title,
                        "group_id": group_id,
                        "every_seconds": every_seconds,
                        "start_at": event["start_at"],
                        "one_shot": False,
                    }
                    last_result = await self.tools.execute("cron", payload)
                    created_jobs += 1
                if last_result is None:
                    return "Cycle reminder created"
                return (
                    f"Created cycle '{group_title}' (group_id: {group_id}) "
                    f"with {created_jobs} jobs; repeats every {int(cycle_schedule['period_days'])} days."
                )

            reminder_text = self._extract_reminder_message(msg.content)
            recurring_schedule = self._extract_recurring_schedule(msg.content)
            if recurring_schedule:
                default_title = f"Recurring: {reminder_text[:40]}".strip()
                group_title = self._make_unique_schedule_title(default_title)
                recurring_payload = {
                    "action": "add",
                    "message": reminder_text,
                    "title": group_title,
                    "group_id": self._build_group_id(group_title),
                    **recurring_schedule,
                }
                result = await self.tools.execute("cron", recurring_payload)
                return str(result)

            target_ms: int | None = None
            relative_ms = parse_relative_time_ms(msg.content)
            if relative_ms is not None:
                now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
                target_ms = now_ms + relative_ms
            else:
                absolute_match = re.search(
                    r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)",
                    msg.content or "",
                )
                if absolute_match:
                    target_ms = parse_absolute_time_ms(absolute_match.group(1))

            if target_ms is None:
                return (
                    "Saya belum bisa memastikan waktu pengingat. "
                    "Contoh: ingatkan 2 menit lagi makan, setiap hari jam 09:00 standup, atau tiap 4 jam minum air."
                )

            at_time = datetime.fromtimestamp(target_ms / 1000, tz=timezone.utc).astimezone().isoformat(timespec="seconds")
            result = await self.tools.execute(
                "cron",
                {
                    "action": "add",
                    "message": reminder_text,
                    "at_time": at_time,
                    "one_shot": True,
                },
            )
            return str(result)

        return None

    async def _plan_task(self, question: str) -> str | None:
        """Phase 1: Ask LLM to create a brief execution plan.
        
        Skips planning for immediate-action tasks (reminders, weather, etc.)
        that just need a single tool call.
        """
        if len(question) < 30:
            return None  # Too short to need planning

        # Skip planning for immediate-action tasks — these should call tools directly
        q_lower = question.lower()
        for pattern in self._IMMEDIATE_ACTION_PATTERNS:
            if pattern in q_lower:
                logger.info(f"Skipping plan for immediate-action task: matched '{pattern}'")
                return None

        try:
            plan_prompt = f"""Create a brief plan (max 5 steps) to answer this request.
For each step, specify:
1. What to do
2. Which tool to use (if any)
3. Success criteria

CRITICAL: If the request is for creating code, skills, or complex actions, Step 1 MUST be "Ask user for approval/details".
Do not plan to write/execute immediately.

Request: {question[:500]}

Reply with a numbered plan. Be concise."""

            response = await self.provider.chat(
                messages=[{"role": "user", "content": plan_prompt}],
                model=self.model,
                max_tokens=300,
                temperature=0.3
            )
            logger.info(f"Plan generated: {response.content[:100]}...")
            return response.content
        except Exception as e:
            logger.warning(f"Planning failed: {e}")
            return None

    def _is_weak_model(self, model: str) -> bool:
        """Check if model is considered weak and needs adaptive critic thresholds."""
        weak_models = [
            "llama-4-scout", "llama-3.1-8b", "llama-3-8b", "gemma-7b",
            "mistral-7b", "phi-3", "qwen-7b", "codellama-7b"
        ]
        model_lower = model.lower()
        return any(weak in model_lower for weak in weak_models)

    async def _critic_evaluate(self, question: str, answer: str, model: str | None = None) -> tuple[int, str]:
        """Phase 3: Score response quality 0-10 with rubric. Uses separate model for weak models."""
        try:
            # For weak models, use a stronger model for evaluation if available
            eval_model = model or self.model
            if self._is_weak_model(eval_model):
                # Try to use a stronger model for evaluation
                stronger_models = ["openai/gpt-4o", "anthropic/claude-3-5-sonnet-20241022", "openai/gpt-4o-mini"]
                for strong_model in stronger_models:
                    try:
                        # Test if this model is available
                        test_response = await self.provider.chat(
                            messages=[{"role": "user", "content": "test"}],
                            model=strong_model,
                            max_tokens=5,
                            temperature=0.0
                        )
                        eval_model = strong_model
                        logger.info(f"Using stronger model {strong_model} for critic evaluation")
                        break
                    except Exception:
                        continue
            eval_prompt = f"""Score this AI response 0-10 based on:
- Correctness: Does it accurately answer the question?
- Completeness: Is anything important missing?
- Evidence: Did it use tools/data or fabricate information?
- Clarity: Is it well-structured and clear?

Question: {question[:300]}
Response: {answer[:800]}

Reply in this EXACT format:
SCORE: X
FEEDBACK: <one sentence explaining the score>"""

            response = await self.provider.chat(
                messages=[{"role": "user", "content": eval_prompt}],
                model=eval_model,
                max_tokens=100,
                temperature=0.0
            )

            # Parse score
            import re
            score_match = re.search(r'SCORE:\s*(\d+)', response.content)
            score = int(score_match.group(1)) if score_match else 7
            score = max(0, min(10, score))  # Clamp 0-10

            feedback_match = re.search(r'FEEDBACK:\s*(.+)', response.content)
            feedback = feedback_match.group(1).strip() if feedback_match else response.content

            logger.info(f"Critic score: {score}/10 — {feedback[:80]}")
            return score, feedback

        except Exception as e:
            logger.warning(f"Critic evaluation failed: {e}")
            return 7, "Evaluation skipped"  # Pass by default on error

    async def _log_lesson(self, question: str, feedback: str,
                          score_before: int, score_after: int) -> None:
        """Log a metacognition lesson from critic-driven retries."""
        try:
            import uuid
            lesson_id = str(uuid.uuid4())[:12]
            self.memory.metadata.add_lesson(
                lesson_id=lesson_id,
                trigger=question[:200],
                mistake=f"Initial response scored {score_before}/10",
                fix=feedback[:200],
                guardrail=f"Improved to {score_after}/10 after retry",
                score_before=score_before,
                score_after=score_after,
                task_type="complex",
            )
            logger.info(f"Lesson logged: {lesson_id} ({score_before}→{score_after})")
        except Exception as e:
            logger.warning(f"Failed to log lesson: {e}")

    async def _call_llm_with_fallback(self, messages: list, models: list) -> tuple[Any | None, Exception | None]:
        last_error = None
        for current_model in models:
            try:
                # Use rotated key if available
                original_key = None
                if self.auth_rotation:
                    current_key = self.auth_rotation.current_key()
                    # Update provider key temporarily
                    if hasattr(self.provider, 'api_key'):
                        original_key = self.provider.api_key
                        self.provider.api_key = current_key

                response = await self.provider.chat(
                    messages=messages,
                    tools=self.tools.get_definitions(),
                    model=current_model
                )

                # Restore original key
                if self.auth_rotation and original_key is not None:
                    self.provider.api_key = original_key

                # Phase 9: Reset resilience on success
                self.resilience.on_success()

                return response, None
            except Exception as e:
                error_str = str(e).lower()

                # Check if auth/rate limit error
                if self.auth_rotation and hasattr(self.provider, 'api_key'):
                    if "401" in error_str or "429" in error_str or "rate" in error_str:
                        reason = "rate_limit" if "429" in error_str or "rate" in error_str else "auth_error"
                        current_key = self.auth_rotation.current_key()
                        self.auth_rotation.mark_failed(current_key, reason)

                        # Try rotating to next key
                        next_key = self.auth_rotation.rotate()
                        if next_key != current_key:
                            logger.info(f"Retrying with rotated key due to {reason}")
                            # Restore original key before retry
                            if original_key is not None:
                                self.provider.api_key = original_key
                            continue  # Retry with new key

                # Restore original key on error
                if self.auth_rotation and original_key is not None:
                    self.provider.api_key = original_key

                logger.warning(f"Model {current_model} failed: {e}")
                last_error = e
                # Phase 9: Try resilience recovery
                status_code = getattr(e, 'status_code', None)
                recovery = await self.resilience.handle_error(e, status_code=status_code)
                if recovery["action"] == "model_fallback" and recovery["new_model"]:
                    models.append(recovery["new_model"])
        return None, last_error

    async def _process_tool_calls(self, msg: InboundMessage, messages: list, response: Any, session: Any) -> list:
        tool_call_dicts = [
            {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
            for tc in response.tool_calls
        ]
        if not response.content:
            messages = self.context.add_assistant_message(messages, None, tool_call_dicts, reasoning_content=response.reasoning_content)

        tc_data = [{"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in response.tool_calls]
        await self.memory.add_message(msg.session_key, "assistant", response.content or "", tool_calls=tc_data)

        # Phase 12: Get tool permissions based on elevated mode directive
        permissions = self._get_tool_permissions(session)
        if permissions.get('auto_approve') or self.exec_auto_approve:
            logger.debug("Elevated mode active: auto_approve=True, restrict_to_workspace=False")

        exec_tool = self.tools.get("exec")
        if exec_tool and hasattr(exec_tool, "auto_approve"):
            exec_tool.auto_approve = bool(
                self.exec_auto_approve or permissions.get("auto_approve", False)
            )

        for tc in response.tool_calls:
            status = self._get_tool_status_message(tc.name, tc.arguments)
            if status:
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id, content=f"_{status}_", metadata={"type": "status_update"}
                ))
            tool_params = dict(tc.arguments)
            if tc.name == "exec":
                tool_params["_session_key"] = msg.session_key
                tool_params["_channel"] = msg.channel
                tool_params["_chat_id"] = msg.chat_id
                tool_params["_agent_id"] = self._resolve_agent_id_for_message(msg)
                tool_params["_account_id"] = msg.account_id or ""
                tool_params["_thread_id"] = msg.thread_id or ""
                tool_params["_peer_kind"] = msg.peer_kind or ""
                tool_params["_peer_id"] = msg.peer_id or ""

            result = await self.tools.execute(tc.name, tool_params)

            # Phase 12: Apply truncation after tool execution
            result_str = str(result)
            truncated_result = self.truncator.truncate(result_str, tc.name)

            # Phase 12: Add verbose mode output if enabled
            if self._should_log_verbose(session):
                token_count = self.truncator._count_tokens(result_str)
                verbose_output = self._format_verbose_output(tc.name, result_str, token_count)
                truncated_result += verbose_output

            result_for_llm = self._format_tool_result(truncated_result)
            messages = self.context.add_tool_result(messages, tc.id, tc.name, result_for_llm)
            await self.memory.add_message(
                msg.session_key, "tool", str(result),
                tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": str(result)[:1000]}]
            )
        return messages

    def _format_tool_result(self, result: Any) -> str:
        """Format tool result for LLM context.

        Note: Truncation is handled by ToolResultTruncator before this method is called.
        This method only converts the result to string format.
        """
        return str(result)

    async def _finalize_session(self, msg: InboundMessage, session: Any, final_content: str | None) -> OutboundMessage:
        if final_content and not final_content.startswith("I've completed"):
            await self.memory.add_message(msg.session_key, "assistant", final_content)

        if not msg.session_key.startswith("background:"):
            session.add_message("user", msg.content)
            if final_content:
                session.add_message("assistant", final_content)
            try:
                self.sessions.save(session)
            except Exception as exc:
                logger.warning(f"Session save failed for {msg.session_key}: {exc}")

        return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=final_content or "")

    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        logger.info(f"Processing system message from {msg.sender_id}")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel, origin_chat_id = parts[0], parts[1]
        else:
            origin_channel, origin_chat_id = "cli", msg.chat_id

        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)

        for t in ["message", "spawn", "cron"]:
            tool = self.tools.get(t)
            if hasattr(tool, "set_context"): tool.set_context(origin_channel, origin_chat_id)

        messages = self.context.build_messages(history=session.get_history(), current_message=msg.content, channel=origin_channel, chat_id=origin_chat_id)

        final_content = await self._run_agent_loop(msg, messages, session)
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        if final_content: session.add_message("assistant", final_content)
        try:
            self.sessions.save(session)
        except Exception as exc:
            logger.warning(f"Session save failed for {session_key}: {exc}")
        return OutboundMessage(channel=origin_channel, chat_id=origin_chat_id, content=final_content or "")

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
        """Process a message in a fully isolated session.

        Unlike process_direct, this:
        - Does NOT load conversation history
        - Does NOT save to conversation memory
        - Uses a temporary session that's discarded after execution
        """
        import time
        session_key = f"isolated:cron:{job_id}" if job_id else f"isolated:{int(time.time())}"
        msg = InboundMessage(
            channel=channel, sender_id="system",
            chat_id=chat_id, content=content,
            _session_key=session_key
        )

        # Set context for tools without loading history
        for tool_name in ["message", "spawn", "cron"]:
            tool = self.tools.get(tool_name)
            if hasattr(tool, "set_context"):
                tool.set_context(channel, chat_id)

        # Build messages without history — fresh context
        messages = self.context.build_messages(
            history=[],  # No history for isolated sessions
            current_message=content,
            channel=channel,
            chat_id=chat_id,
            profile="GENERAL",
            tool_names=self.tools.tool_names,
        )

        # Create a minimal session for isolated execution
        session = self.sessions.get_or_create(session_key)

        # Run simple response (no planning for isolated jobs)
        final_content = await self._run_agent_loop(msg, messages, session)
        return final_content or ""

    # Phase 12: Directives Behavior Implementation
    def _apply_think_mode(self, messages: list, session: Any) -> list:
        """Apply think mode directive by injecting reasoning prompt into message context.

        Think mode enhances the LLM's reasoning capabilities by instructing it to:
        - Show step-by-step reasoning before taking action
        - Consider edge cases and alternative approaches
        - Read related files for full context understanding
        - Explicitly explain its thought process

        This method should be called ONCE before the agent loop starts, not on every iteration,
        to avoid injecting the reasoning prompt multiple times.

        Args:
            messages: List of message dictionaries in OpenAI format
            session: Session object containing metadata with directives

        Returns:
            Modified messages list with reasoning prompt inserted at the beginning if think mode
            is active, otherwise returns messages unchanged

        Note:
            - Gracefully handles corrupted or missing directives metadata
            - Logs debug message when think mode is applied
            - Returns original messages on any error to prevent loop disruption
        """
        try:
            directives = session.metadata.get('directives', {})
            if not isinstance(directives, dict):
                logger.warning("Directives metadata corrupted, using defaults")
                directives = {}

            if not directives.get('think'):
                return messages

            reasoning_prompt = {
                "role": "system",
                "content": (
                    "Think step-by-step. Show your reasoning process explicitly before taking action. "
                    "Consider edge cases, alternative approaches, and potential issues. "
                    "When analyzing code, read related files to understand full context."
                )
            }

            messages.insert(0, reasoning_prompt)
            logger.debug("Think mode applied: reasoning prompt injected")
            return messages

        except Exception as e:
            logger.error(f"Failed to apply think mode: {e}")
            return messages

    def _should_log_verbose(self, session: Any) -> bool:
        """Check if verbose logging directive is enabled for the current session.

        Verbose mode provides detailed debug output including:
        - Tool execution details
        - Token usage statistics
        - Full tool results before truncation
        - Internal processing information

        This is useful for debugging, development, and understanding the agent's
        decision-making process.

        Args:
            session: Session object containing metadata with directives

        Returns:
            True if verbose mode is enabled, False otherwise

        Note:
            - Returns False if directives metadata is corrupted or missing
            - Returns False on any error to prevent disrupting normal operation
            - Safe to call frequently as it only reads session metadata
        """
        try:
            directives = session.metadata.get('directives', {})
            if not isinstance(directives, dict):
                return False
            return directives.get('verbose', False)
        except Exception as e:
            logger.error(f"Failed to check verbose mode: {e}")
            return False

    def _format_verbose_output(self, tool_name: str, tool_result: str, tokens_used: int) -> str:
        """Format verbose debug output for tool execution details.

        Creates a structured debug message containing tool execution information
        that can be sent to the user when verbose mode is enabled. This helps
        users understand what tools are being called, how much context they consume,
        and what results they produce.

        Args:
            tool_name: Name of the tool that was executed (e.g., "read_file", "exec")
            tool_result: The result returned by the tool (may be truncated)
            tokens_used: Estimated number of tokens consumed by the tool result

        Returns:
            Formatted string with DEBUG prefix containing tool name, token count,
            and the full result

        Example output:
            [DEBUG] Tool: read_file
            [DEBUG] Tokens: 1234
            [DEBUG] Result:
            <tool result content here>
        """
        return (
            f"\n\n[DEBUG] Tool: {tool_name}\n"
            f"[DEBUG] Tokens: {tokens_used}\n"
            f"[DEBUG] Result:\n{tool_result}\n"
        )

    def _get_tool_permissions(self, session: Any) -> dict:
        """Get tool execution permissions based on elevated directive status.

        The elevated directive grants the agent expanded permissions for tool execution,
        allowing it to perform operations that would normally be restricted. This is
        useful for administrative tasks, system maintenance, or when the user explicitly
        trusts the agent to perform sensitive operations.

        Permission levels:
        - Normal mode (elevated=False):
          * auto_approve: False - requires user confirmation for risky operations
          * restrict_to_workspace: True - limits file operations to workspace directory
          * allow_high_risk: False - blocks potentially dangerous operations

        - Elevated mode (elevated=True):
          * auto_approve: True - automatically approves tool executions
          * restrict_to_workspace: False - allows file operations outside workspace
          * allow_high_risk: True - permits high-risk operations

        Args:
            session: Session object containing metadata with directives

        Returns:
            Dictionary with permission flags:
            - auto_approve: Whether to skip confirmation prompts
            - restrict_to_workspace: Whether to limit file operations to workspace
            - allow_high_risk: Whether to allow potentially dangerous operations

        Note:
            - Returns safe defaults (all restrictions enabled) on any error
            - Elevated mode should only be used when the user explicitly requests it
            - Tools should check these permissions before executing sensitive operations
        """
        try:
            elevated = session.metadata.get('directives', {}).get('elevated', False)

            return {
                'auto_approve': elevated,
                'restrict_to_workspace': not elevated,
                'allow_high_risk': elevated
            }
        except Exception as e:
            logger.error(f"Failed to get tool permissions: {e}")
            return {
                'auto_approve': False,
                'restrict_to_workspace': True,
                'allow_high_risk': False
            }
