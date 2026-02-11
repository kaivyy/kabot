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
        max_iterations: int = 20,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        cron_service: "CronService | None" = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
    ):
        from kabot.config.schema import ExecToolConfig
        from kabot.cron.service import CronService
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        
        self.context = ContextBuilder(workspace)
        self.sessions = session_manager or SessionManager(workspace)
        self.memory = ChromaMemoryManager(workspace / "memory_db")
        self.router = IntentRouter(provider)
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
        # File tools (restrict to workspace if configured)
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        self.tools.register(ReadFileTool(allowed_dir=allowed_dir))
        self.tools.register(WriteFileTool(allowed_dir=allowed_dir))
        self.tools.register(EditFileTool(allowed_dir=allowed_dir))
        self.tools.register(ListDirTool(allowed_dir=allowed_dir))
        
        # Shell tool
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.restrict_to_workspace,
        ))
        
        # Web tools
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(WebFetchTool())
        
        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)
        
        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)
        
        # Cron tool (for scheduling)
        if self.cron_service:
            cron_tool = CronTool(self.cron_service)
            self.tools.register(cron_tool)

            # Memory tools that depend on cron service
            self.tools.register(ListRemindersTool(cron_service=self.cron_service))

        # Memory tools (for personal memory/diary)
        self.tools.register(SaveMemoryTool(memory_manager=self.memory))
        self.tools.register(GetMemoryTool(memory_manager=self.memory))

        # Weather tool
        self.tools.register(WeatherTool())

        # Stock and Crypto tools
        self.tools.register(StockTool())
        self.tools.register(CryptoTool())
        self.tools.register(StockAnalysisTool())

        # AutoPlanner (must be last to have access to all tools)
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
                return f"📖 Membaca file `{path}`..."
            elif tool_name == "write_file":
                path = args.get("path") or args.get("file_path")
                return f"📝 Menulis file `{path}`..."
            elif tool_name == "edit_file":
                path = args.get("path") or args.get("file_path")
                return f"✏️ Mengedit file `{path}`..."
            elif tool_name == "list_dir":
                path = args.get("path") or "."
                return f"📂 Mengecek folder `{path}`..."
            elif tool_name == "exec":
                cmd = args.get("command")
                return f"💻 Menjalankan: `{cmd}`..."
            elif tool_name == "web_search":
                query = args.get("query")
                return f"🔍 Searching: '{query}'..."
            elif tool_name == "web_fetch":
                url = args.get("url")
                return f"🌐 Mengunduh konten dari {url}..."
            elif tool_name == "autoplanner":
                goal = args.get("goal")
                return f"🧠 Merencanakan: '{goal}'..."
            elif tool_name == "spawn":
                agent_type = args.get("agent_type")
                return f"🤖 Memanggil sub-agent `{agent_type}`..."
            elif tool_name == "save_memory":
                return "💾 Menyimpan ingatan..."
            elif tool_name == "get_memory":
                return "🧠 Mengingat kembali..."
            elif tool_name == "list_reminders":
                return "📋 Mengecek pengingat..."
            elif tool_name == "weather":
                location = args.get("location")
                return f"🌤️ Mengecek cuaca di {location}..."
            elif tool_name == "stock":
                symbol = args.get("symbol")
                return f"📈 Mengecek saham {symbol}..."
            elif tool_name == "crypto":
                coin = args.get("coin")
                return f"₿ Mengecek harga {coin}..."
            elif tool_name == "stock_analysis":
                symbol = args.get("symbol")
                return f"📊 Menganalisis saham {symbol}..."
            elif tool_name == "cron":
                return "⏰ Mengatur jadwal..."
            elif tool_name in ("download-manager", "download_manager"):
                return "📥 Mengunduh file..."
            return None
        except Exception:
            return None

    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")
        
        while self._running:
            try:
                # Wait for next message
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                
                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue
    
    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")
    
    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a single inbound message.
        
        Args:
            msg: The inbound message to process.
        
        Returns:
            The response message, or None if no response needed.
        """
        # Handle system messages (subagent announces)
        # The chat_id contains the original "channel:chat_id" to route back to
        if msg.channel == "system":
            return await self._process_system_message(msg)
        
        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}: {preview}")

        # Get or create session
        session = self.sessions.get_or_create(msg.session_key)

        # Initialize memory session
        self.memory.create_session(
            session_id=msg.session_key,
            channel=msg.channel,
            chat_id=msg.chat_id,
            user_id=msg.sender_id
        )

        # Store user message in memory
        await self.memory.add_message(
            session_id=msg.session_key,
            role="user",
            content=msg.content
        )

        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id)
        
        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(msg.channel, msg.chat_id)

        # Update memory tool contexts for session tracking
        save_memory_tool = self.tools.get("save_memory")
        if save_memory_tool:
            save_memory_tool.set_context(msg.session_key)

        get_memory_tool = self.tools.get("get_memory")
        if get_memory_tool:
            get_memory_tool.set_context(msg.session_key)

        list_reminders_tool = self.tools.get("list_reminders")
        if list_reminders_tool:
            list_reminders_tool.set_context(msg.session_key)

        # Get conversation context from memory manager (prevents amnesia)
        conversation_history = self.memory.get_conversation_context(
            session_id=msg.session_key,
            max_messages=30
        )

        # Classify intent
        intent = await self.router.classify(msg.content)
        logger.info(f"Detected intent for {msg.session_key}: {intent}")

        # Build initial messages
        messages = self.context.build_messages(
            history=conversation_history,
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
            profile=intent,
        )

        # Agent loop
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Call LLM
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )
            
            # Handle tool calls
            if response.has_tool_calls:
                # Add assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)  # Must be JSON string
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )

                # Store assistant message with tool calls in memory
                # Manually convert ToolCallRequest dataclass to dict to avoid 'model_dump' error
                tool_calls_data = []
                for tc in response.tool_calls:
                    tool_calls_data.append({
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments
                    })

                await self.memory.add_message(
                    session_id=msg.session_key,
                    role="assistant",
                    content=response.content or "",
                    tool_calls=tool_calls_data
                )

                # Execute tools
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info(f"Tool call: {tool_call.name}({args_str[:200]})")

                    # BROADCAST STATUS UPDATE (Live Feedback)
                    # Send a short "Thinking..." message to the user before executing the tool
                    status_message = self._get_tool_status_message(tool_call.name, tool_call.arguments)
                    if status_message:
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=f"_{status_message}_", # Italic for status
                            metadata={"type": "status_update"}
                        ))

                    result = await self.tools.execute(tool_call.name, tool_call.arguments)

                    # Truncate result for LLM context if too long (prevents 400 Bad Request)
                    # Limit to ~2000 chars to be ultra-safe for free models with small context
                    result_str = str(result)
                    MAX_TOOL_OUTPUT = 2000
                    if len(result_str) > MAX_TOOL_OUTPUT:
                        result_for_llm = result_str[:MAX_TOOL_OUTPUT] + f"\n... (truncated, {len(result_str) - MAX_TOOL_OUTPUT} more characters)"
                    else:
                        result_for_llm = result_str

                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result_for_llm
                    )

                    # Store tool result in memory (prevents amnesia - unlike OpenClaw!)
                    await self.memory.add_message(
                        session_id=msg.session_key,
                        role="tool",
                        content=str(result),
                        tool_results=[{
                            "tool_call_id": tool_call.id,
                            "name": tool_call.name,
                            "result": str(result)[:1000]  # Limit size but keep full context
                        }]
                    )
            else:
                # No tool calls, we're done
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "I've completed processing but have no response to give."
        
        # Log response preview
        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info(f"Response to {msg.channel}:{msg.sender_id}: {preview}")

        # Save to memory manager (prevents amnesia - full context preserved!)
        await self.memory.add_message(
            session_id=msg.session_key,
            role="assistant",
            content=final_content
        )

        # Also save to legacy session for compatibility
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            metadata=msg.metadata or {},  # Pass through for channel-specific needs (e.g. Slack thread_ts)
        )
    
    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).
        
        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.
        """
        logger.info(f"Processing system message from {msg.sender_id}")
        
        # Parse origin from chat_id (format: "channel:chat_id")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # Fallback
            origin_channel = "cli"
            origin_chat_id = msg.chat_id
        
        # Use the origin session for context
        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id)
        
        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(origin_channel, origin_chat_id)

        # Update memory tool contexts for system messages too
        save_memory_tool = self.tools.get("save_memory")
        if save_memory_tool:
            save_memory_tool.set_context(session_key)

        get_memory_tool = self.tools.get("get_memory")
        if get_memory_tool:
            get_memory_tool.set_context(session_key)

        list_reminders_tool = self.tools.get("list_reminders")
        if list_reminders_tool:
            list_reminders_tool.set_context(session_key)

        # Build messages with the announce content
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            channel=origin_channel,
            chat_id=origin_chat_id,
        )
        
        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )
            
            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )
                
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info(f"Tool call: {tool_call.name}({args_str[:200]})")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "Background task completed."
        
        # Save to session (mark as system message in history)
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content
        )
    
    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
    ) -> str:
        """
        Process a message directly (for CLI or cron usage).
        
        Args:
            content: The message content.
            session_key: Session identifier.
            channel: Source channel (for context).
            chat_id: Source chat ID (for context).
        
        Returns:
            The agent's response.
        """
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content
        )
        
        response = await self._process_message(msg)
        return response.content if response else ""
