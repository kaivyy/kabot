"""Tool result truncation to prevent context overflow."""

from loguru import logger


class ToolResultTruncator:
    """Truncates tool results to prevent context overflow."""

    # Constants for truncation behavior
    TRUNCATION_RATIO = 0.8  # Keep 80% of threshold when truncating
    CHARS_PER_TOKEN = 4     # Approximate character-to-token ratio

    def __init__(self, max_tokens: int = 128000, max_share: float = 0.3):
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if not 0 < max_share <= 1.0:
            raise ValueError("max_share must be between 0 and 1.0")

        self.max_tokens = max_tokens
        self.max_share = max_share
        self.threshold = int(max_tokens * max_share)

        # Cache tiktoken encoding
        try:
            import tiktoken
            self.encoding = tiktoken.encoding_for_model("gpt-4")
            self.has_tiktoken = True
        except ImportError:
            self.encoding = None
            self.has_tiktoken = False
            logger.warning("tiktoken not available, using character-based estimation")

    def truncate(self, result: str, tool_name: str) -> str:
        """Truncate tool result if it exceeds the token threshold.

        Args:
            result: The tool result string to potentially truncate
            tool_name: Name of the tool for logging purposes

        Returns:
            Original result if under threshold, otherwise truncated result with warning
        """
        try:
            token_count = self._count_tokens(result)
            if token_count <= self.threshold:
                return result

            keep_tokens = int(self.threshold * self.TRUNCATION_RATIO)
            truncated = self._truncate_to_tokens(result, keep_tokens)
            warning = (
                f"⚠️ [Output truncated: {token_count} tokens exceeds limit of {self.threshold}. "
                f"Showing first {keep_tokens} tokens...]"
            )
            return truncated + warning
        except Exception as e:
            logger.error(f"Truncation failed for {tool_name}: {e}")
            max_chars = self.threshold * self.CHARS_PER_TOKEN
            if len(result) <= max_chars:
                return result
            truncated = result[:int(max_chars * self.TRUNCATION_RATIO)]
            warning = f"\n\n⚠️ [Output truncated: ~{len(result)} chars exceeds limit.]"
            return truncated + warning

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken or character-based estimation.

        Args:
            text: The text to count tokens for

        Returns:
            Number of tokens (or estimated tokens if tiktoken unavailable)
        """
        if self.has_tiktoken:
            return len(self.encoding.encode(text))
        else:
            return len(text) // self.CHARS_PER_TOKEN

    def _truncate_to_tokens(self, text: str, target_tokens: int) -> str:
        """Truncate text to target token count.

        Args:
            text: The text to truncate
            target_tokens: Maximum number of tokens to keep

        Returns:
            Truncated text
        """
        if self.has_tiktoken:
            tokens = self.encoding.encode(text)
            truncated_tokens = tokens[:target_tokens]
            return self.encoding.decode(truncated_tokens)
        else:
            target_chars = target_tokens * self.CHARS_PER_TOKEN
            return text[:target_chars]
