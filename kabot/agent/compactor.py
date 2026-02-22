"""Message compactor for context window management."""

from typing import Any

from loguru import logger


class Compactor:
    """Compacts conversation history by summarizing old messages."""

    async def compact(
        self,
        messages: list[dict[str, Any]],
        provider: Any,
        model: str,
        keep_recent: int = 10
    ) -> list[dict[str, Any]]:
        """
        Compact messages by summarizing older ones.

        Args:
            messages: Full conversation history
            provider: LLM provider for summarization
            model: Model to use for summarization
            keep_recent: Number of recent messages to preserve

        Returns:
            Compacted message list with summary + recent messages
        """
        if len(messages) <= keep_recent:
            logger.debug("No compaction needed, message count within limit")
            return messages

        # Split into old (to summarize) and recent (to keep)
        old_messages = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]

        logger.info(f"Compacting {len(old_messages)} old messages, keeping {keep_recent} recent")

        # Build summarization prompt
        conversation_text = self._format_for_summary(old_messages)
        summary_prompt = f"""Summarize this conversation history concisely (max 200 words):

{conversation_text}

Focus on key topics, decisions, and context needed to continue the conversation."""

        try:
            response = await provider.chat(
                messages=[{"role": "user", "content": summary_prompt}],
                model=model,
                max_tokens=500,
                temperature=0.3
            )

            summary = response.content or "Previous conversation summary unavailable."

            # Create summary message
            summary_msg = {
                "role": "system",
                "content": f"[Conversation History Summary]\n{summary}"
            }

            # Return summary + recent messages
            return [summary_msg] + recent_messages

        except Exception as e:
            logger.error(f"Compaction failed: {e}, keeping recent messages only")
            return recent_messages

    def _format_for_summary(self, messages: list[dict[str, Any]]) -> str:
        """Format messages for summarization."""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                lines.append(f"{role.upper()}: {content[:500]}")
        return "\n\n".join(lines)
