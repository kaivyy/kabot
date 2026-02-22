"""Memory tools for personal diary, reminders, and fact storage."""

from datetime import datetime
from typing import Any

from loguru import logger

from kabot.agent.tools.base import Tool
from kabot.memory import ChromaMemoryManager  # Uses alias for HybridMemoryManager


class SaveMemoryTool(Tool):
    """Tool to save personal memories, diary entries, or facts."""

    name = "save_memory"
    description = "Save a personal memory, diary entry, or fact for long-term storage"
    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The memory content to save"
            },
            "category": {
                "type": "string",
                "description": "Category: 'diary', 'reminder', 'fact', 'preference'",
                "enum": ["diary", "reminder", "fact", "preference"]
            },
            "importance": {
                "type": "string",
                "description": "Importance level: low, medium, high",
                "enum": ["low", "medium", "high"],
                "default": "medium"
            }
        },
        "required": ["content", "category"]
    }

    def __init__(self, memory_manager: ChromaMemoryManager = None):
        self.memory = memory_manager
        self._session_key = ""

    def set_context(self, session_key: str) -> None:
        """Set session context for memory storage."""
        self._session_key = session_key

    async def execute(self, content: str, category: str = "fact", importance: str = "medium") -> str:
        """Save memory to long-term storage."""
        try:
            if not self.memory:
                return "Error: Memory manager not available"

            # Add timestamp for diary entries
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

            if category == "diary":
                full_content = f"[{timestamp}] {content}"
            else:
                full_content = content

            # Save to memory system
            success = await self.memory.remember_fact(
                fact=full_content,
                category=category,
                session_id=self._session_key,
                confidence=1.0 if importance == "high" else 0.8
            )

            if success:
                return f"[OK] {category.title()} saved: {content[:100]}..."
            else:
                return f"[ERROR] Failed to save {category}"

        except Exception as e:
            logger.error(f"Error saving memory: {e}")
            return f"Error: {str(e)}"


class GetMemoryTool(Tool):
    """Tool to retrieve personal memories."""

    name = "get_memory"
    description = "Retrieve personal memories, diary entries, or facts"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for memories"
            },
            "category": {
                "type": "string",
                "description": "Filter by category (optional)",
                "enum": ["diary", "reminder", "fact", "preference"]
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of memories to retrieve",
                "default": 5
            }
        },
        "required": ["query"]
    }

    def __init__(self, memory_manager: ChromaMemoryManager = None):
        self.memory = memory_manager
        self._session_key = ""

    def set_context(self, session_key: str) -> None:
        """Set session context for memory retrieval."""
        self._session_key = session_key

    async def execute(self, query: str, category: str = None, limit: int = 5) -> str:
        """Retrieve memories from storage."""
        try:
            if not self.memory:
                return "Error: Memory manager not available"

            # Search memories
            memories = await self.memory.search_memory(
                query=query,
                limit=limit
            )

            if not memories:
                # FALLBACK: Provide helpful hints if nothing found
                hint = f"No memories found for: '{query}'.\n"

                # Try to list available categories to help the AI refine
                try:
                    facts = self.memory.metadata.get_facts(limit=10)
                    if facts:
                        categories = sorted(list(set(f.get('category', 'fact') for f in facts)))
                        hint += f"HINT: Try searching with categories: {', '.join(categories)}\n"

                    recent = self.memory.metadata.get_message_chain(limit=5)
                    if recent:
                        hint += "HINT: Check your keywords or use 'list_reminders' for schedules."
                except Exception:
                    pass

                return hint

            # Format results
            results = []
            for mem in memories:
                cat = mem.get("metadata", {}).get("category", "unknown")
                content = mem.get("content", "")
                results.append(f"[{cat.upper()}] {content}")

            return "\n\n".join(results)

        except Exception as e:
            logger.error(f"Error retrieving memory: {e}")
            return f"Error: {str(e)}"


class ListRemindersTool(Tool):
    """Tool to list active reminders."""

    name = "list_reminders"
    description = "List all active reminders and their scheduled times"
    parameters = {
        "type": "object",
        "properties": {}
    }

    def __init__(self, cron_service=None):
        self.cron = cron_service
        self._session_key = ""

    def set_context(self, session_key: str) -> None:
        """Set session context for reminder listing."""
        self._session_key = session_key

    async def execute(self) -> str:
        """List all reminders."""
        try:
            if not self.cron:
                return "No active reminders"

            jobs = self.cron.list_jobs(include_disabled=False)

            if not jobs:
                return "No active reminders"

            grouped: dict[str, dict[str, Any]] = {}
            for job in jobs:
                group_id = job.payload.group_id or f"single:{job.id}"
                if group_id not in grouped:
                    grouped[group_id] = {
                        "title": job.payload.group_title or job.name,
                        "items": [],
                    }
                schedule_str = self._format_schedule(job.schedule)
                grouped[group_id]["items"].append(
                    f"  - {job.name} (id: {job.id}): {schedule_str}"
                )

            results = []
            for group_id, data in grouped.items():
                results.append(f"* {data['title']} [group_id: {group_id}]")
                results.extend(data["items"])

            return "[LIST] Active reminders:\n\n" + "\n".join(results)

        except Exception as e:
            logger.error(f"Error listing reminders: {e}")
            return f"Error: {str(e)}"

    def _format_schedule(self, schedule) -> str:
        """Format schedule for display."""
        if schedule.kind == "at":
            dt = datetime.fromtimestamp(schedule.at_ms / 1000)
            return dt.strftime("%Y-%m-%d %H:%M")
        elif schedule.kind == "every":
            minutes = schedule.every_ms / (1000 * 60)
            if schedule.start_at_ms:
                anchor = datetime.fromtimestamp(schedule.start_at_ms / 1000).strftime("%Y-%m-%d %H:%M")
                return f"every {int(minutes)} minutes (start: {anchor})"
            return f"every {int(minutes)} minutes"
        elif schedule.kind == "cron":
            return f"cron: {schedule.expr}"
        return "unknown"
