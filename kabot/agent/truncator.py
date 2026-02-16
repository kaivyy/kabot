"""Tool result truncation to prevent context overflow."""

from loguru import logger


class ToolResultTruncator:
    """Truncates tool results to prevent context overflow."""

    def __init__(self, max_tokens: int = 128000, max_share: float = 0.3):
        self.max_tokens = max_tokens
        self.max_share = max_share
        self.threshold = int(max_tokens * max_share)

    def truncate(self, result: str, tool_name: str) -> str:
        try:
            token_count = self._count_tokens(result)
            if token_count <= self.threshold:
                return result

            keep_tokens = int(self.threshold * 0.8)
            truncated = self._truncate_to_tokens(result, keep_tokens)
            warning = (
                f"⚠️ [Output truncated: {token_count} tokens exceeds limit of {self.threshold}. "
                f"Showing first {keep_tokens} tokens...]"
            )
            return truncated + warning
        except Exception as e:
            logger.error(f"Truncation failed for {tool_name}: {e}")
            max_chars = self.threshold * 4
            if len(result) <= max_chars:
                return result
            truncated = result[:int(max_chars * 0.8)]
            warning = f"\n\n⚠️ [Output truncated: ~{len(result)} chars exceeds limit.]"
            return truncated + warning

    def _count_tokens(self, text: str) -> int:
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model("gpt-4")
            return len(encoding.encode(text))
        except ImportError:
            logger.warning("tiktoken not available, using character-based estimation")
            return len(text) // 4

    def _truncate_to_tokens(self, text: str, target_tokens: int) -> str:
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model("gpt-4")
            tokens = encoding.encode(text)
            truncated_tokens = tokens[:target_tokens]
            return encoding.decode(truncated_tokens)
        except ImportError:
            target_chars = target_tokens * 4
            return text[:target_chars]
