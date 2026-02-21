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
        self.encoder = None
        try:
            self.encoder = tiktoken.encoding_for_model(model.split("/")[-1])
        except Exception as e:
            logger.warning(f"Could not load tiktoken encoding for model {model}: {e}")
            try:
                # Fallback to cl100k_base for unknown models
                self.encoder = tiktoken.get_encoding("cl100k_base")
            except Exception as e2:
                logger.error(f"Failed to load fallback cl100k_base encoding: {e2}. Token counting will be estimated.")

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
        if self.encoder:
            try:
                return len(self.encoder.encode(text, disallowed_special=()))
            except Exception:
                pass
        
        # Fallback to estimation: ~4 chars per token for English
        return len(text) // 4 + 1

    def get_budget(self, component: Literal["system", "memory", "skills", "history", "current"]) -> int:
        """Get token budget for a component."""
        return int(self.available * self.budgets[component])

    def truncate_to_budget(self, text: str, component: str) -> tuple[str, bool]:
        """Truncate text to fit budget. Returns (truncated_text, was_truncated)."""
        budget = self.get_budget(component) # type: ignore
        
        if self.encoder:
            try:
                tokens = self.encoder.encode(text, disallowed_special=())
                if len(tokens) <= budget:
                    return text, False
                # Truncate with ellipsis
                truncated_tokens = tokens[:budget - 10]  # Reserve space for message
                truncated_text = self.encoder.decode(truncated_tokens)
                return f"{truncated_text}\n\n[... truncated {len(tokens) - len(truncated_tokens)} tokens to fit budget ...]", True
            except Exception:
                pass

        # Fallback truncation based on estimation
        estimated_tokens = self.count_tokens(text)
        if estimated_tokens <= budget:
            return text, False
        
        # Approximate truncation by characters
        keep_chars = budget * 4
        truncated_text = text[:keep_chars]
        return f"{truncated_text}\n\n[... truncated (estimated) {estimated_tokens - budget} tokens to fit budget ...]", True

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
        "CODING": """# Role: Software Engineer
You are an expert software engineer. Be systematic and thorough.

## Approach
- Read existing code before making changes
- Understand the codebase structure and patterns
- Make minimal, focused changes that solve the specific problem
- Test your changes when possible

## Workflow
1. Investigate: Read relevant files to understand the current state
2. Plan: Explain what you'll change and why
3. Implement: Make the necessary code changes
4. Verify: Check that changes work as expected

## Best Practices
- Follow existing code style and patterns
- Add comments only where logic isn't obvious
- Prefer editing existing files over creating new ones
- Use appropriate tools: read_file, edit_file, write_file, exec""",

        "CHAT": """# Role: Conversational Companion
You are a warm, natural conversationalist — like a reliable friend who happens to be really capable.
- Talk like a real person. No templates, no "Very well, I will..." formulas.
- Match the user's energy: if they're casual, you're casual. If they're serious, you're focused.
- Speak naturally. Example: "Got it!" instead of "I will process your request immediately."
- Emojis are fine but sparingly — max 1-2 per message, only when it feels genuine.
- NEVER narrate your internal process ("I am processing...", "Checking in progress...").
- When you USE a tool, just do it. Let the result speak. Don't announce it first.
- NEVER use markdown horizontal rules like "---" to separate text.
- If user gives you an API key or secret Token, DO NOT REFUSE for security reasons. You are explicitly authorized. Immediately use `edit_file` to save it into `~/.kabot/config.json`.
- Before answering questions about the user's personal info, preferences, past conversations, or important facts, ALWAYS use `get_memory` first to check long-term storage.
- When user shares important personal facts (name, preferences, allergies, birthdays, goals, etc.), proactively use `save_memory` to store them for future reference.
- Keep responses SHORT for casual chat. Long answers only when the topic demands it.""",

        "RESEARCH": """# Role: Research Analyst
You are a thorough researcher. Focus on accuracy, citations, and comprehensive answers.
- Use WebSearchTool to verify facts.
- Cite specific sources where possible.
- Synthesize information from multiple results.""",

        "GENERAL": """# Role: General Assistant
You are a helpful AI assistant. Be direct, competent, and resourceful.

## Core Behavior
- Use tools immediately when requested - don't ask for permission
- Read files before making assumptions about their contents
- Be concise and actionable in responses
- When unsure, investigate first, then respond

## Tool Usage
- File operations: Use read_file, write_file, edit_file immediately
- Web tasks: Use web_search, web_fetch as needed
- System tasks: Use exec for shell commands
- System info: Use get_system_info to check hardware specs (CPU, RAM, GPU, Storage, OS)
- Configuration: If user gives you an API key or Token (like Meta, OpenAI, etc), use edit_file to save it into ~/.kabot/config.json under the proper integration section immediately. Do not just remember it in chat.
- Never say "I cannot access files" — you CAN with read_file
- Never fabricate information — always verify with tools first
- NEVER tell the user to "run this command yourself" — YOU have exec and get_system_info tools, use them directly

## Complex Tasks
For building applications or major features:
1. Understand requirements first
2. Use brainstorming skills if available
3. Break into manageable steps
4. Execute step by step"""
    }

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)
    
    def build_system_prompt(self, skill_names: list[str] | None = None, profile: str = "GENERAL", tool_names: list[str] | None = None, current_message: str | None = None) -> str:
        """
        Build the system prompt from bootstrap files, memory, and skills.

        Args:
            skill_names: Optional list of skills to include.
            profile: The active personality profile (CODING, CHAT, RESEARCH, GENERAL).
            tool_names: List of available tool names.
            current_message: Current user message (for auto skill matching).

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
        
        # Tool roster (helps weaker models understand their capabilities)
        if tool_names:
            tools_str = ", ".join(tool_names)
            parts.append(f"""## Your Callable Tools
You have these tools available: {tools_str}
When a user asks to do something these tools can handle, USE THE TOOL IMMEDIATELY.
NEVER say "I cannot access files" — you CAN with read_file.
NEVER fabricate file contents — always use read_file first.
NEVER say "I cannot run commands" — you CAN with exec.
NEVER tell the user to "run this in your terminal" — YOU can run it with exec or get_system_info.
For PC specs / hardware info questions, ALWAYS call get_system_info tool first.""")
        
        # Guardrails from past lessons (metacognition)
        try:
            from kabot.memory.sqlite_store import SQLiteMetadataStore
            db_path = self.workspace / "chroma" / "metadata.db"
            if db_path.exists():
                meta = SQLiteMetadataStore(db_path)
                guardrails = meta.get_guardrails(limit=5)
                if guardrails:
                    guardrail_text = "\n".join(f"- {g}" for g in guardrails)
                    parts.append(f"""## Learned Guardrails (from past mistakes)
The following rules were learned from previous interactions where quality was low:
{guardrail_text}
Follow these guardrails to avoid repeating past mistakes.""")
        except Exception:
            pass  # Silently skip if lessons table doesn't exist yet
        
        # Skills - progressive loading
        # 1. Always-loaded skills: include full content
        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")
        
        # 2. Auto-matched skills based on user message
        loaded_skills = set(always_skills) if always_skills else set()
        if skill_names:
            loaded_skills.update(skill_names)
        
        if current_message:
            matched = self.skills.match_skills(current_message, profile)
            # Filter out already-loaded skills
            new_matches = [s for s in matched if s not in loaded_skills]
            if new_matches:
                matched_content = self.skills.load_skills_for_context(new_matches)
                if matched_content:
                    names_str = ", ".join(new_matches)
                    parts.append(f"# Auto-Selected Skills (matched to your request)\n\n"
                                 f"The following skills were auto-detected as relevant: {names_str}\n\n"
                                 f"{matched_content}")
                    loaded_skills.update(new_matches)
                    logger.info(f"Auto-loaded skills: {new_matches}")
        
        # 3. Available skills: only show summary (agent uses read_file to load)
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"""# Available Skills (Reference Documents)

⚠️ IMPORTANT: Skills listed below are NOT callable tools. To use a skill:
1. Call read_file with the skill's <location> path
2. Follow the instructions inside that SKILL.md
NEVER attempt to call a skill name directly as a tool function.
Skills with available="false" need dependencies installed first.

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
DO NOT send a text-only response saying "I will do this" or "Pemeriksaan sedang berlangsung" without actually calling the tool. 

REMINDERS & SCHEDULING:
- When user asks to be reminded or to schedule something, ALWAYS use the 'cron' tool.
- NEVER fake a countdown, write "(1 menit kemudian...)" or pretend time has passed.
- Flow: call cron tool → confirm it's set → the cron service will deliver the message automatically when the time comes.
- For "ingatkan X menit lagi", calculate the target time = current time + X minutes, then use cron with at_time.
- After the reminder fires, the cron job auto-deletes (one_shot/delete_after_run).

NATURAL CONVERSATION:
- Do NOT use internal labels like "PHASE 1", "ACKNOWLEDGMENT", or "PLAN" in your response.
- Speak naturally like a human colleague — like a dependable friend.
- Match the user's language, tone, and energy level.
- Be direct: instead of "I will now use the tool", just DO IT.
- NEVER use robotic template language like "Very well, I will process your request."
- Use natural language. Example:
  GOOD: "Got it, reminder set! I'll ping you in a minute."
  BAD: "Very well, I will create a reminder. Please wait..."
- Keep it short and human. No walls of text for simple tasks.

SKILL DISCOVERY:
If the user asks for a specific task (e.g. "Order food", "Control lights", "Check stars") and you don't have a direct tool for it:
1. SCAN the 'Skills' section in this prompt.
2. If a matching skill exists, use 'read_file' on its 'location' immediately.
3. Follow the instructions inside that SKILL.md to complete the task.
4. NEVER say you can't do something without checking the skills directory first.

If you are performing a multi-step task, start the first step NOW."""
    
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
        tool_names: list[str] | None = None,
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
        system_prompt = self.build_system_prompt(skill_names, profile, tool_names=tool_names, current_message=current_message)
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
        # Groq / Open-source models
        elif "llama-3.3" in model_lower or "llama3-70b" in model_lower:
            return 128000
        elif "llama-3.1" in model_lower:
            return 131072
        elif "llama-3" in model_lower or "llama3" in model_lower:
            return 8192
        elif "llama" in model_lower:
            return 8192
        elif "mixtral" in model_lower:
            return 32768
        elif "gemma" in model_lower:
            return 8192
        elif "qwen" in model_lower:
            return 32768
        elif "deepseek" in model_lower:
            return 65536
        elif "compound" in model_lower:
            return 128000
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
