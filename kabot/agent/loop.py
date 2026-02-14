"""Agent loop: the core processing engine."""

import asyncio
import json
from pathlib import Path
from typing import Any

from loguru import logger

from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.bus.queue import MessageBus
from kabot.providers.base import LLMProvider
from kabot.agent.context import ContextBuilder
from kabot.agent.tools.registry import ToolRegistry
from kabot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from kabot.agent.tools.shell import ExecTool
from kabot.agent.tools.web import WebSearchTool, WebFetchTool
from kabot.agent.tools.browser import BrowserTool
from kabot.agent.tools.message import MessageTool
from kabot.agent.tools.spawn import SpawnTool
from kabot.agent.tools.cron import CronTool
from kabot.agent.tools.memory import SaveMemoryTool, GetMemoryTool, ListRemindersTool
from kabot.agent.tools.weather import WeatherTool
from kabot.agent.tools.stock import StockTool, CryptoTool
from kabot.agent.tools.stock_analysis import StockAnalysisTool
from kabot.agent.tools.autoplanner import AutoPlanner
from kabot.agent.subagent import SubagentManager
from kabot.agent.router import IntentRouter
from kabot.session.manager import SessionManager
from kabot.memory.chroma_memory import ChromaMemoryManager
from kabot.providers.registry import ModelRegistry


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
        fallbacks: list[str] | None = None,
        max_iterations: int = 20,
        brave_api_key: str | None = None,
        exec_config: Any = None,
        cron_service: Any = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        enable_hybrid_memory: bool = True,
    ):
        from kabot.config.schema import ExecToolConfig
        from kabot.cron.service import CronService
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
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace

        self.context = ContextBuilder(workspace)
        self.sessions = session_manager or SessionManager(workspace)
        self.memory = ChromaMemoryManager(
            workspace / "memory_db",
            enable_hybrid_memory=enable_hybrid_memory
        )
        self.router = IntentRouter(provider, model=self.model)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )

        self._running = False
        self._register_default_tools()

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
        ))

        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(WebFetchTool())
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
        self.tools.register(WeatherTool())
        self.tools.register(StockTool())
        self.tools.register(CryptoTool())
        self.tools.register(StockAnalysisTool())

        autoplanner = AutoPlanner(
            tool_registry=self.tools,
            message_bus=self.bus
        )
        self.tools.register(autoplanner)

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
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue

    def stop(self) -> None:
        self._running = False
        logger.info("Agent loop stopping")

    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        if msg.channel == "system":
            return await self._process_system_message(msg)

        session = await self._init_session(msg)
        conversation_history = self.memory.get_conversation_context(msg.session_key, max_messages=30)
        intent = await self.router.classify(msg.content)

        messages = self.context.build_messages(
            history=conversation_history,
            current_message=msg.content,
            media=msg.media if hasattr(msg, 'media') else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
            profile=intent,
        )

        final_content = await self._run_agent_loop(msg, messages)
        return await self._finalize_session(msg, session, final_content)

    async def _init_session(self, msg: InboundMessage) -> Any:
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}: {msg.content[:80]}...")
        session = self.sessions.get_or_create(msg.session_key)
        self.memory.create_session(msg.session_key, msg.channel, msg.chat_id, msg.sender_id)
        await self.memory.add_message(msg.session_key, "user", msg.content)

        for tool_name in ["message", "spawn", "cron"]:
            tool = self.tools.get(tool_name)
            if hasattr(tool, "set_context"):
                tool.set_context(msg.channel, msg.chat_id)

        for tool_name in ["save_memory", "get_memory", "list_reminders"]:
            tool = self.tools.get(tool_name)
            if hasattr(tool, "set_context"):
                tool.set_context(msg.session_key)
        return session

    async def _run_agent_loop(self, msg: InboundMessage, messages: list) -> str | None:
        iteration = 0
        models_to_try = [self.model] + self.fallbacks

        while iteration < self.max_iterations:
            iteration += 1
            response, error = await self._call_llm_with_fallback(messages, models_to_try)
            if not response:
                return f"Sorry, all available models failed. Last error: {str(error)}"

            if response.content:
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id, content=response.content
                ))
                messages = self.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
                if not response.has_tool_calls:
                    return response.content

            if response.has_tool_calls:
                messages = await self._process_tool_calls(msg, messages, response)
            else:
                return response.content
        return "I've completed processing but have no response to give."

    async def _call_llm_with_fallback(self, messages: list, models: list) -> tuple[Any | None, Exception | None]:
        last_error = None
        for current_model in models:
            try:
                response = await self.provider.chat(
                    messages=messages,
                    tools=self.tools.get_definitions(),
                    model=current_model
                )
                return response, None
            except Exception as e:
                logger.warning(f"Model {current_model} failed: {e}")
                last_error = e
        return None, last_error

    async def _process_tool_calls(self, msg: InboundMessage, messages: list, response: Any) -> list:
        tool_call_dicts = [
            {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
            for tc in response.tool_calls
        ]
        if not response.content:
            messages = self.context.add_assistant_message(messages, None, tool_call_dicts, reasoning_content=response.reasoning_content)

        tc_data = [{"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in response.tool_calls]
        await self.memory.add_message(msg.session_key, "assistant", response.content or "", tool_calls=tc_data)

        for tc in response.tool_calls:
            status = self._get_tool_status_message(tc.name, tc.arguments)
            if status:
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id, content=f"_{status}_", metadata={"type": "status_update"}
                ))
            result = await self.tools.execute(tc.name, tc.arguments)
            result_for_llm = self._format_tool_result(result)
            messages = self.context.add_tool_result(messages, tc.id, tc.name, result_for_llm)
            await self.memory.add_message(
                msg.session_key, "tool", str(result),
                tool_results=[{"tool_call_id": tc.id, "name": tc.name, "result": str(result)[:1000]}]
            )
        return messages

    def _format_tool_result(self, result: Any) -> str:
        res_str = str(result)
        limit = 4000
        if len(res_str) > limit:
            keep = limit // 2
            res_str = res_str[:keep] + "\n\n... [TRUNCATED] ...\n\n" + res_str[-keep:]
        return res_str

    async def _finalize_session(self, msg: InboundMessage, session: Any, final_content: str | None) -> OutboundMessage:
        if final_content and not final_content.startswith("I've completed"):
            await self.memory.add_message(msg.session_key, "assistant", final_content)

        if not msg.session_key.startswith("background:"):
            session.add_message("user", msg.content)
            if final_content:
                session.add_message("assistant", final_content)
            self.sessions.save(session)

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
        
        final_content = await self._run_agent_loop(msg, messages)
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        if final_content: session.add_message("assistant", final_content)
        self.sessions.save(session)
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

        # Run simple response (no planning for isolated jobs)
        final_content = await self._run_agent_loop(msg, messages)
        return final_content or ""
