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

    def _count_content_tokens(self, content: Any, encoding) -> int:
        """
        Recursively count tokens in content of any type.

        Args:
            content: Content to count (str, list, dict, or other)
            encoding: Tiktoken encoding

        Returns:
            Token count
        """
        if content is None:
            return 0
        elif isinstance(content, str):
            return len(encoding.encode(content))
        elif isinstance(content, list):
            return sum(self._count_content_tokens(item, encoding) for item in content)
        elif isinstance(content, dict):
            return sum(self._count_content_tokens(v, encoding) for v in content.values())
        else:
            # Convert to string for other types
            return len(encoding.encode(str(content)))

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
                # Count content (handles str, list, dict, etc.)
                content = msg.get("content")
                if content:
                    total_tokens += self._count_content_tokens(content, encoding)

                # Count tool calls if present
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    for tc in tool_calls:
                        # Count tool name
                        if isinstance(tc, dict):
                            func = tc.get("function", {})
                            if isinstance(func, dict):
                                name = func.get("name", "")
                                args = func.get("arguments", "")
                                total_tokens += len(encoding.encode(str(name)))
                                total_tokens += len(encoding.encode(str(args)))

                # Add overhead for role, formatting, and message structure
                total_tokens += 4

            logger.debug(f"Context tokens: {total_tokens}/{self.max_tokens}")

            return total_tokens > self.threshold

        except ImportError:
            logger.warning("tiktoken not available, using character-based estimation")
            # Fallback: rough estimate (4 chars ≈ 1 token)
            total_chars = sum(len(str(msg.get("content", ""))) for msg in messages)
            estimated_tokens = total_chars // 4
            return estimated_tokens > self.threshold
