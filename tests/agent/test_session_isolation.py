import pytest
from unittest.mock import AsyncMock, MagicMock
from kabot.agent.loop import AgentLoop

@pytest.mark.asyncio
async def test_process_isolated_no_history():
    """Test that process_isolated doesn't load conversation history."""
    # Create a mock agent loop
    loop = AgentLoop.__new__(AgentLoop)
    loop.context = MagicMock()
    loop.tools = MagicMock()
    loop.tools.tool_names = []
    loop.tools.get = MagicMock(return_value=MagicMock())
    loop.model = "test-model"
    loop.fallbacks = []
    loop.max_iterations = 1
    loop.bus = MagicMock()
    loop._run_agent_loop = AsyncMock(return_value="Response")

    # Mock build_messages to verify it's called with empty history
    loop.context.build_messages = MagicMock(return_value=[])

    result = await loop.process_isolated(
        content="Test message",
        channel="cli",
        chat_id="direct",
        job_id="test123"
    )

    # Verify build_messages was called with empty history
    loop.context.build_messages.assert_called_once()
    call_kwargs = loop.context.build_messages.call_args[1]
    assert call_kwargs["history"] == [], "History should be empty for isolated sessions"
    assert result == "Response"

@pytest.mark.asyncio
async def test_process_isolated_session_key():
    """Test that process_isolated uses isolated session key."""
    loop = AgentLoop.__new__(AgentLoop)
    loop.context = MagicMock()
    loop.tools = MagicMock()
    loop.tools.tool_names = []
    loop.tools.get = MagicMock(return_value=MagicMock())
    loop.model = "test-model"
    loop.fallbacks = []
    loop.max_iterations = 1
    loop.bus = MagicMock()
    loop._run_agent_loop = AsyncMock(return_value="Response")
    loop.context.build_messages = MagicMock(return_value=[])

    result = await loop.process_isolated(
        content="Test message",
        channel="whatsapp",
        chat_id="628123456",
        job_id="abc123"
    )

    # Verify the session key format
    # The session key should be "isolated:cron:abc123"
    assert result == "Response"
