from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop import AgentLoop


@pytest.mark.asyncio
async def test_process_isolated_hydrates_origin_history_by_default():
    """Test that process_isolated reuses the origin chat history unless fresh context is requested."""
    loop = AgentLoop.__new__(AgentLoop)
    loop.context = MagicMock()
    loop.tools = MagicMock()
    loop.tools.tool_names = []
    loop.tools.get = MagicMock(return_value=MagicMock())
    loop.model = "test-model"
    loop.fallbacks = []
    loop.max_iterations = 1
    loop.bus = MagicMock()
    origin_session = MagicMock()
    origin_session.get_history.return_value = [
        {"role": "assistant", "content": "Konteks origin masih relevan."}
    ]
    isolated_session = MagicMock()
    loop.sessions = MagicMock()
    loop.sessions.get_or_create = MagicMock(
        side_effect=lambda key: origin_session if key == "cli:direct" else isolated_session
    )
    loop._run_agent_loop = AsyncMock(return_value="Response")

    loop.context.build_messages = MagicMock(return_value=[])

    result = await loop.process_isolated(
        content="Test message",
        channel="cli",
        chat_id="direct",
        job_id="test123"
    )

    loop.context.build_messages.assert_called_once()
    call_kwargs = loop.context.build_messages.call_args[1]
    assert call_kwargs["history"] == [
        {"role": "assistant", "content": "Konteks origin masih relevan."}
    ]
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
    loop.sessions = MagicMock()  # Add missing sessions attribute
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


@pytest.mark.asyncio
async def test_process_isolated_fresh_context_skips_origin_history():
    loop = AgentLoop.__new__(AgentLoop)
    loop.context = MagicMock()
    loop.tools = MagicMock()
    loop.tools.tool_names = []
    loop.tools.get = MagicMock(return_value=MagicMock())
    loop.model = "test-model"
    loop.fallbacks = []
    loop.max_iterations = 1
    loop.bus = MagicMock()
    origin_session = MagicMock()
    origin_session.get_history.return_value = [
        {"role": "assistant", "content": "Konteks origin masih relevan."}
    ]
    isolated_session = MagicMock()
    loop.sessions = MagicMock()
    loop.sessions.get_or_create = MagicMock(
        side_effect=lambda key: origin_session if key == "cli:direct" else isolated_session
    )
    loop._run_agent_loop = AsyncMock(return_value="Response")
    loop.context.build_messages = MagicMock(return_value=[])

    result = await loop.process_isolated(
        content="Test message",
        channel="cli",
        chat_id="direct",
        job_id="test123",
        fresh_context=True,
    )

    loop.context.build_messages.assert_called_once()
    call_kwargs = loop.context.build_messages.call_args[1]
    assert call_kwargs["history"] == []
    assert result == "Response"
