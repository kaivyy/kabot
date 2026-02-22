"""Tests for ToolResultTruncator."""

from kabot.agent.truncator import ToolResultTruncator


def test_truncator_allows_small_results():
    """Small results should pass through unchanged."""
    truncator = ToolResultTruncator()
    small_result = "This is a small result" * 10

    result = truncator.truncate(small_result, "test_tool")

    assert result == small_result


def test_truncator_truncates_large_results():
    """Large results should be truncated with warning."""
    truncator = ToolResultTruncator(max_tokens=1000, max_share=0.3)
    # Create a result that exceeds threshold (300 tokens)
    large_result = "word " * 500  # ~500 tokens

    result = truncator.truncate(large_result, "test_tool")

    assert result != large_result
    assert "⚠️ [Output truncated:" in result
    assert "tokens exceeds limit" in result


def test_truncator_preserves_beginning():
    """Truncation should preserve beginning and remove end."""
    truncator = ToolResultTruncator(max_tokens=1000, max_share=0.3)
    large_result = "START " + ("middle " * 500) + " END"

    result = truncator.truncate(large_result, "test_tool")

    assert "START" in result
    assert "END" not in result


def test_truncator_handles_empty_result():
    """Empty results should be handled gracefully."""
    truncator = ToolResultTruncator()
    empty_result = ""

    result = truncator.truncate(empty_result, "test_tool")

    assert result == ""


def test_truncator_custom_threshold():
    """Custom threshold should be calculated correctly."""
    truncator = ToolResultTruncator(max_tokens=10000, max_share=0.5)

    assert truncator.threshold == 5000
    assert truncator.max_tokens == 10000
    assert truncator.max_share == 0.5


def test_truncator_fallback_without_tiktoken():
    """Falls back to character-based counting when tiktoken unavailable."""
    from unittest.mock import patch

    with patch('builtins.__import__', side_effect=ImportError("tiktoken not found")):
        truncator = ToolResultTruncator(max_tokens=128000, max_share=0.3)
        large_result = "x" * 200000

        result = truncator.truncate(large_result, "test_tool")

        assert len(result) < len(large_result)
        assert "⚠️" in result

