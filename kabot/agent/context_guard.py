"""Context window guard to prevent token overflow."""

from typing import Any
from loguru import logger


class ContextGuard:
    """Guards against context window overflow."""

    def __init__(self, max_tokens: int = 128000, buffer_tokens: int = 4000):
        """
        Initialize context guard.

        Args:
            max_tokens: Maximum context window size
            buffer_tokens: Safety buffer before triggering compaction
        """
        self.max_tokens = max_tokens
        self.buffer_tokens = buffer_tokens
        self.threshold = max_tokens - buffer_tokens

    def check_overflow(self, messages: list[dict[str, Any]], model: str) -> bool:
        """
        Check if messages exceed context window threshold.

        Args:
            messages: Conversation messages
            model: Model name for token counting

        Returns:
            True if compaction needed, False otherwise
        """
        try:
            import tiktoken

            # Get encoding for model
            try:
                encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fallback to cl100k_base for unknown models
                encoding = tiktoken.get_encoding("cl100k_base")

            # Count tokens
            total_tokens = 0
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str):
                    total_tokens += len(encoding.encode(content))
                # Add overhead for role, formatting
                total_tokens += 4

            logger.debug(f"Context tokens: {total_tokens}/{self.max_tokens}")

            return total_tokens > self.threshold

        except ImportError:
            logger.warning("tiktoken not available, using character-based estimation")
            # Fallback: rough estimate (4 chars ≈ 1 token)
            total_chars = sum(len(str(msg.get("content", ""))) for msg in messages)
            estimated_tokens = total_chars // 4
            return estimated_tokens > self.threshold
