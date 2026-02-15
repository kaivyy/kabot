"""Tests for message compactor."""

import pytest
from kabot.agent.compactor import Compactor


@pytest.mark.asyncio
async def test_compactor_summarizes_old_messages():
    """Test that compactor summarizes older messages."""
    compactor = Compactor()

    messages = [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a programming language..."},
        {"role": "user", "content": "What about Java?"},
        {"role": "assistant", "content": "Java is also a programming language..."},
        {"role": "user", "content": "Compare them"},
    ]

    # Mock LLM provider
    class MockProvider:
        async def chat(self, messages, model, max_tokens=500, temperature=0.3):
            class Response:
                content = "Summary: User asked about Python and Java."
            return Response()

    provider = MockProvider()
    compacted = await compactor.compact(messages, provider, model="gpt-4", keep_recent=2)

    # Should keep last 2 messages + summary
    assert len(compacted) == 3
    assert "Summary:" in compacted[0]["content"]
    assert compacted[2]["content"] == "Compare them"


@pytest.mark.asyncio
async def test_compactor_preserves_recent_messages():
    """Test that compactor always preserves recent messages."""
    compactor = Compactor()

    messages = [
        {"role": "user", "content": "Recent message 1"},
        {"role": "assistant", "content": "Recent response 1"},
    ]

    class MockProvider:
        async def chat(self, messages, model, max_tokens=500, temperature=0.3):
            class Response:
                content = "Summary"
            return Response()

    provider = MockProvider()
    compacted = await compactor.compact(messages, provider, model="gpt-4", keep_recent=2)

    # Should not compact if all messages are recent
    assert len(compacted) == 2
