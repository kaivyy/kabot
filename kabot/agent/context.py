"""Context builder for assembling agent prompts."""

import base64
import mimetypes
import platform
from pathlib import Path
from typing import Any, Literal

import tiktoken
from loguru import logger

from kabot.agent.memory import MemoryStore
from kabot.agent.skills import SkillsLoader


class TokenBudget:
    """Manages token budgets for different context components."""

    def __init__(self, model: str = "gpt-4", max_context: int = 128000):
        # Use tiktoken for accurate token counting
        try:
            self.encoder = tiktoken.encoding_for_model(model.split("/")[-1])
        except KeyError:
            # Fallback to cl100k_base for unknown models
            self.encoder = tiktoken.get_encoding("cl100k_base")

        self.max_context = max_context
        # Reserve 20% for response + safety margin
        self.available = int(max_context * 0.8)

        # Budget allocation (percentages of available tokens)
        self.budgets = {
            "system": 0.30,      # 30% - System prompt, identity, profile
            "memory": 0.15,      # 15% - Memory context
            "skills": 0.15,      # 15% - Skills (always + summary)
            "history": 0.30,     # 30% - Conversation history
            "current": 0.10,     # 10% - Current message + media
        }

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if not text:
            return 0
        return len(self.encoder.encode(text, disallowed_special=()))

    def get_budget(self, component: Literal["system", "memory", "skills", "history", "current"]) -> int:
        """Get token budget for a component."""
        return int(self.available * self.budgets[component])

    def truncate_to_budget(self, text: str, component: str) -> tuple[str, bool]:
        """Truncate text to fit budget. Returns (truncated_text, was_truncated)."""
        budget = self.get_budget(component) # type: ignore
        tokens = self.encoder.encode(text, disallowed_special=())

        if len(tokens) <= budget:
            return text, False

        # Truncate with ellipsis
        truncated_tokens = tokens[:budget - 10]  # Reserve space for message
        truncated_text = self.encoder.decode(truncated_tokens)
        return f"{truncated_text}\n\n[... truncated {len(tokens) - len(truncated_tokens)} tokens to fit budget ...]", True

    def truncate_history(self, messages: list[dict], budget: int) -> list[dict]:
        """Truncate conversation history to fit budget, keeping most recent."""
        # Always keep system message (index 0)
        if len(messages) <= 1:
            return messages

        # Count from most recent backwards
        kept_messages = []
        token_count = 0

        for msg in reversed(messages[1:]):  # Skip system message
            msg_text = str(msg.get("content", ""))
            msg_tokens = self.count_tokens(msg_text)

            if token_count + msg_tokens > budget:
                break

            kept_messages.insert(0, msg)
            token_count += msg_tokens

        return [messages[0]] + kept_messages


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.

    Assembles bootstrap files, memory, skills, and conversation history
    into a coherent prompt for the LLM.
    """

    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md"]

    PROFILES = {
        "CODING": """# Role: Senior Software Engineer
You are an expert software engineer. Focus on code quality, correctness, and best practices.
- When writing code, ensure it is production-ready, typed, and documented.
- Prefer editing existing files over creating new ones.
- Use the ReadFileTool to inspect code before modifying it.

GUIDED WORKFLOW:
If the user asks to build a complex application or feature from scratch (e.g. "Create a Todo App"):
1. DO NOT start writing code immediately.
2. OFFER to start with the **Brainstorming** phase to clarify requirements.
3. EXPLAIN the workflow: Brainstorm -> Design -> Plan -> Execute.
4. LOAD the relevant skill file (e.g., `kabot/skills/brainstorming/SKILL.md`) using `read_file`.""",

        "CHAT": """# Role: Friendly Assistant
You are a warm, engaging AI assistant. Focus on conversation and personality.
- Be concise but friendly.
- You don't need to be overly technical unless asked.
- Feel free to use a more casual tone.""",

        "RESEARCH": """# Role: Research Analyst
You are a thorough researcher. Focus on accuracy, citations, and comprehensive answers.
- Use WebSearchTool to verify facts.
- Cite specific sources where possible.
- Synthesize information from multiple results.""",

        "GENERAL": """# Role: General Assistant
You are a helpful AI assistant capable of handling various tasks.

GUIDED WORKFLOW:
If the user asks to build a complex application or feature from scratch (e.g. "Create a Todo App"):
1. DO NOT start writing code immediately.
2. OFFER to start with the **Brainstorming** phase to clarify requirements.
3. EXPLAIN the workflow: Brainstorm -> Design -> Plan -> Execute.
4. LOAD the relevant skill file (e.g., `kabot/skills/brainstorming/SKILL.md`) using `read_file`."""
    }

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)
    
    def build_system_prompt(self, skill_names: list[str] | None = None, profile: str = "GENERAL") -> str:
        """
        Build the system prompt from bootstrap files, memory, and skills.

        Args:
            skill_names: Optional list of skills to include.
            profile: The active personality profile (CODING, CHAT, RESEARCH, GENERAL).

        Returns:
            Complete system prompt.
        """
        parts = []

        # Core identity
        parts.append(self._get_identity())

        # Profile instruction
        if profile in self.PROFILES:
            parts.append(self.PROFILES[profile])

        # Bootstrap files
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)
        
        # Memory context
        memory = self.memory.get_memory_context()
        if memory:
            parts.append(f"# Memory\n\n{memory}")
        
        # Skills - progressive loading
        # 1. Always-loaded skills: include full content
        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")
        
        # 2. Available skills: only show summary (agent uses read_file to load)
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"""# Skills

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.

{skills_summary}""")
        
        return "\n\n---\n\n".join(parts)
    
    def _get_identity(self) -> str:
        """Get the core identity section."""
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"
        
        return f"""# kabot 🐈

You are kabot, a helpful AI assistant. You have access to tools that allow you to:
- Read, write, and edit files
- Execute shell commands
- Search the web and fetch web pages
- Send messages to users on chat channels
- Spawn subagents for complex background tasks

## Current Time
{now}

## Runtime
{runtime}

## Workspace
Your workspace is at: {workspace_path}
- Memory files: {workspace_path}/memory/MEMORY.md
- Daily notes: {workspace_path}/memory/YYYY-MM-DD.md
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md

## Communication Style
- **Be Responsive**: Don't just do things silently. Tell the user what you have done after finishing a task.
- **Narrate Actions**: When performing multi-step tasks (like downloading then sending), briefly mention the completion of each step.
- **Confirm Completion**: Always end task-based interactions with a clear confirmation.

IMPORTANT: When responding to direct questions or conversations, reply directly with your text response.
Only use the 'message' tool when you need to send a message to a specific chat channel (like WhatsApp).
For normal conversation, just respond with text - do not call the message tool.

Always be helpful, accurate, and concise.
CRITICAL: If you need to use a tool (like downloading files, checking weather, etc.), use the tool IMMEDIATELY in your first response.
DO NOT send a text-only response saying "I will do this" without actually calling the tool.
You can include explanatory text alongside the tool call in the same response."""
    
    def _load_bootstrap_files(self) -> str:
        """Load all bootstrap files from workspace."""
        parts = []
        
        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")
        
        return "\n\n".join(parts) if parts else ""
    
    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        profile: str = "GENERAL",
        model: str = "gpt-4",
        max_context: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build the complete message list for an LLM call with token budget management.

        Args:
            history: Previous conversation messages.
            current_message: The new user message.
            skill_names: Optional skills to include.
            media: Optional list of local file paths for images/media.
            channel: Current channel (telegram, feishu, etc.).
            chat_id: Current chat/user ID.
            profile: Intent profile for system prompt customization.
            model: Model name for token counting (default: gpt-4)
            max_context: Override max context window (auto-detected from model if None)

        Returns:
            List of messages including system prompt.
        """
        # Initialize token budget
        budget = TokenBudget(model, max_context or self._get_model_context(model))

        messages = []

        # System prompt
        system_prompt = self.build_system_prompt(skill_names, profile)
        if channel and chat_id:
            system_prompt += f"\n\n## Current Session\nChannel: {channel}\nChat ID: {chat_id}"

        system_prompt, was_truncated = budget.truncate_to_budget(system_prompt, "system")
        if was_truncated:
            logger.warning("System prompt truncated to fit token budget")

        messages.append({"role": "system", "content": system_prompt})

        # History with smart truncation (keep most recent)
        history_budget = budget.get_budget("history")
        truncated_history = budget.truncate_history(history, history_budget)

        if len(truncated_history) < len(history):
            dropped = len(history) - len(truncated_history)
            logger.warning(f"Dropped {dropped} oldest messages to fit token budget")

        messages.extend(truncated_history)

        # Current message (with optional image attachments)
        user_content = self._build_user_content(current_message, media)
        messages.append({"role": "user", "content": user_content})

        # Final validation
        total_tokens = sum(budget.count_tokens(str(m.get("content", ""))) for m in messages)
        logger.info(f"Context: {total_tokens}/{budget.max_context} tokens ({total_tokens/budget.max_context*100:.1f}%)")

        if total_tokens > budget.available:
            logger.error(f"Context overflow: {total_tokens} > {budget.available} tokens!")

        return messages

    def _get_model_context(self, model: str) -> int:
        """Get context window size for a model."""
        model_lower = model.lower()

        # Common context windows
        if "gpt-4-turbo" in model_lower or "gpt-4o" in model_lower:
            return 128000
        elif "gpt-4" in model_lower:
            return 8192
        elif "gpt-3.5" in model_lower:
            return 16385
        elif "claude-opus" in model_lower or "claude-sonnet" in model_lower:
            return 200000
        elif "gemini-1.5-pro" in model_lower:
            return 2000000
        elif "gemini" in model_lower:
            return 1000000
        else:
            return 128000  # Safe default

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """Build user message content with optional base64-encoded images."""
        if not media:
            return text
        
        images = []
        for path in media:
            p = Path(path)
            mime, _ = mimetypes.guess_type(path)
            if not p.is_file() or not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(p.read_bytes()).decode()
            images.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        
        if not images:
            return text
        return images + [{"type": "text", "text": text}]
    
    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str
    ) -> list[dict[str, Any]]:
        """
        Add a tool result to the message list.
        
        Args:
            messages: Current message list.
            tool_call_id: ID of the tool call.
            tool_name: Name of the tool.
            result: Tool execution result.
        
        Returns:
            Updated message list.
        """
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result
        })
        return messages
    
    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        reasoning_content: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Add an assistant message to the message list.
        
        Args:
            messages: Current message list.
            content: Message content.
            tool_calls: Optional tool calls.
            reasoning_content: Thinking output (Kimi, DeepSeek-R1, etc.).
        
        Returns:
            Updated message list.
        """
        msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
        
        if tool_calls:
            msg["tool_calls"] = tool_calls
        
        # Thinking models reject history without this
        if reasoning_content:
            msg["reasoning_content"] = reasoning_content
        
        messages.append(msg)
        return messages
