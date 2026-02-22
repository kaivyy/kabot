# kabot/memory/memory_pruner.py
"""Memory Pruner: scheduled cleanup of stale memories."""

from __future__ import annotations

from loguru import logger

from kabot.memory.sqlite_store import SQLiteMetadataStore


class MemoryPruner:
    """Prune old facts and messages to keep memory lean.

    Designed to run as a periodic background job (via CronService).
    """

    def __init__(self, max_age_days: int = 30):
        self.max_age_days = max_age_days

    def prune_old_facts(self, store: SQLiteMetadataStore) -> int:
        """Delete facts older than max_age_days.

        Returns:
            Number of deleted facts.
        """
        try:
            with store._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM facts WHERE created_at < datetime('now', ?)",
                    (f"-{self.max_age_days} days",),
                )
                deleted = cursor.rowcount
                conn.commit()
                if deleted > 0:
                    logger.info(f"Pruned {deleted} stale facts (>{self.max_age_days} days)")
                return deleted
        except Exception as e:
            logger.error(f"Error pruning facts: {e}")
            return 0

    def prune_old_messages(self, store: SQLiteMetadataStore) -> int:
        """Delete messages older than max_age_days.

        Returns:
            Number of deleted messages.
        """
        try:
            with store._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM messages WHERE created_at < datetime('now', ?)",
                    (f"-{self.max_age_days} days",),
                )
                deleted = cursor.rowcount
                conn.commit()
                if deleted > 0:
                    logger.info(f"Pruned {deleted} stale messages (>{self.max_age_days} days)")
                return deleted
        except Exception as e:
            logger.error(f"Error pruning messages: {e}")
            return 0

    def prune_all(self, store: SQLiteMetadataStore) -> dict[str, int]:
        """Run all pruning tasks.

        Returns:
            Dict with counts of deleted items per category.
        """
        return {
            "facts": self.prune_old_facts(store),
            "messages": self.prune_old_messages(store),
            "logs": store.cleanup_logs(retention_days=self.max_age_days),
        }
