"""Memory tools for personal diary, reminders, and fact storage."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from kabot.agent.tools.base import Tool
from kabot.memory.chroma_memory import ChromaMemoryManager


class SaveMemoryTool(Tool):
    """Tool untuk menyimpan memori pribadi, diary, atau fakta."""

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
                return f"[OK] {category.title()} tersimpan: {content[:100]}..."
            else:
                return f"[ERROR] Gagal menyimpan {category}"

        except Exception as e:
            logger.error(f"Error saving memory: {e}")
            return f"Error: {str(e)}"


class GetMemoryTool(Tool):
    """Tool untuk mengambil memori pribadi."""

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
                hint = f"Tidak ada memori ditemukan untuk: '{query}'.\n"
                
                # Try to list available categories to help the AI refine
                try:
                    facts = self.memory.metadata.get_facts(limit=10)
                    if facts:
                        categories = sorted(list(set(f.get('category', 'fact') for f in facts)))
                        hint += f"HINT: Coba cari dengan kategori berikut: {', '.join(categories)}\n"
                    
                    recent = self.memory.metadata.get_message_chain(limit=5)
                    if recent:
                        hint += "HINT: Periksa kembali kata kunci Anda atau gunakan 'list_reminders' jika mencari jadwal."
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
    """Tool untuk melihat daftar pengingat."""

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
            if not self.cron or not self.cron._store:
                return "Tidak ada pengingat aktif"

            jobs = [j for j in self.cron._store.jobs if j.enabled]

            if not jobs:
                return "Tidak ada pengingat aktif"

            results = []
            for job in jobs:
                schedule_str = self._format_schedule(job.schedule)
                results.append(f"• {job.name}: {schedule_str}")

            return "[LIST] Pengingat aktif:\n\n" + "\n".join(results)

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
            return f"setiap {int(minutes)} menit"
        elif schedule.kind == "cron":
            return f"cron: {schedule.expr}"
        return "unknown"
