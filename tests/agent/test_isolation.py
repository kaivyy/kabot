"""Tests for session isolation."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kabot.agent.loop import AgentLoop
from kabot.agent.router import RouteDecision


@pytest.mark.asyncio
async def test_background_session_not_saved():
    """Test that background sessions are not saved to disk."""
    # Mock dependencies
    mock_bus = MagicMock()
    mock_bus.consume_inbound = AsyncMock()

    mock_provider = MagicMock()
    mock_provider.get_default_model.return_value = "test-model"
    mock_provider.chat = AsyncMock()
    mock_provider.chat.return_value.has_tool_calls = False
    mock_provider.chat.return_value.content = "Response"

    mock_sessions = MagicMock()
    mock_sessions.get_or_create.return_value = MagicMock()

    # Patch internal components that are instantiated in __init__
    with patch('kabot.agent.loop.ContextBuilder') as mock_context_cls, \
         patch('kabot.agent.loop.ChromaMemoryManager') as mock_memory_cls, \
         patch('kabot.agent.loop.IntentRouter') as mock_router_cls, \
         patch('kabot.agent.loop.SubagentManager'):

        mock_context = mock_context_cls.return_value
        mock_context.build_messages.return_value = []

        mock_memory = mock_memory_cls.return_value
        mock_memory.add_message = AsyncMock()
        mock_memory.get_conversation_context = MagicMock(return_value=[])

        mock_router = mock_router_cls.return_value
        mock_router.classify = AsyncMock(return_value="GENERAL")
        mock_router.route = AsyncMock(return_value=RouteDecision(profile="GENERAL", is_complex=False))

        # Initialize agent
        agent = AgentLoop(
            bus=mock_bus,
            provider=mock_provider,
            workspace=MagicMock(),
            session_manager=mock_sessions,
            enable_hybrid_memory=False
        )

        # Process a background message
        await agent.process_direct(
            "test",
            session_key="background:test",
            channel="cli",
            chat_id="direct"
        )

        # Verify save NOT called
        mock_sessions.save.assert_not_called()

@pytest.mark.asyncio
async def test_normal_session_saved():
    """Test that normal sessions ARE saved to disk."""
    # Mock dependencies
    mock_bus = MagicMock()

    mock_provider = MagicMock()
    mock_provider.get_default_model.return_value = "test-model"
    mock_provider.chat = AsyncMock()
    mock_provider.chat.return_value.has_tool_calls = False
    mock_provider.chat.return_value.content = "Response"

    mock_sessions = MagicMock()
    mock_sessions.get_or_create.return_value = MagicMock()

    with patch('kabot.agent.loop.ContextBuilder') as mock_context_cls, \
         patch('kabot.agent.loop.ChromaMemoryManager') as mock_memory_cls, \
         patch('kabot.agent.loop.IntentRouter') as mock_router_cls, \
         patch('kabot.agent.loop.SubagentManager'):

        mock_context = mock_context_cls.return_value
        mock_context.build_messages.return_value = []

        mock_memory = mock_memory_cls.return_value
        mock_memory.add_message = AsyncMock()
        mock_memory.get_conversation_context = MagicMock(return_value=[])

        mock_router = mock_router_cls.return_value
        mock_router.classify = AsyncMock(return_value="GENERAL")
        mock_router.route = AsyncMock(return_value=RouteDecision(profile="GENERAL", is_complex=False))

        # Initialize agent
        agent = AgentLoop(
            bus=mock_bus,
            provider=mock_provider,
            workspace=MagicMock(),
            session_manager=mock_sessions,
            enable_hybrid_memory=False
        )

        await agent.process_direct(
            "test",
            session_key="normal:test",
            channel="cli",
            chat_id="direct"
        )

        # Verify save called
        mock_sessions.save.assert_called_once()
