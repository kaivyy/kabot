"""Integration tests for Phase 12: Critical Features."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from kabot.agent.loop import AgentLoop
from kabot.agent.truncator import ToolResultTruncator


@pytest.fixture
def mock_agent_loop():
    """Create a minimal AgentLoop instance for testing."""
    from kabot.bus.queue import MessageBus
    from kabot.providers.base import LLMProvider

    # Create mocks
    bus = Mock(spec=MessageBus)
    provider = Mock(spec=LLMProvider)
    provider.get_default_model.return_value = "gpt-4"
    workspace = Path("C:/temp/test_workspace")

    # Create AgentLoop instance
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        model="gpt-4"
    )

    return loop


def test_truncator_initialized(mock_agent_loop):
    """Verify that ToolResultTruncator is initialized in AgentLoop."""
    # Assert
    assert hasattr(mock_agent_loop, 'truncator')
    assert isinstance(mock_agent_loop.truncator, ToolResultTruncator)
    assert mock_agent_loop.truncator.max_tokens == 128000
    assert mock_agent_loop.truncator.max_share == 0.3
    assert mock_agent_loop.truncator.threshold == 38400  # 128000 * 0.3


def test_directives_methods_exist(mock_agent_loop):
    """Verify that all directives behavior methods exist."""
    # Assert
    assert hasattr(mock_agent_loop, '_apply_think_mode')
    assert callable(mock_agent_loop._apply_think_mode)

    assert hasattr(mock_agent_loop, '_should_log_verbose')
    assert callable(mock_agent_loop._should_log_verbose)

    assert hasattr(mock_agent_loop, '_format_verbose_output')
    assert callable(mock_agent_loop._format_verbose_output)

    assert hasattr(mock_agent_loop, '_get_tool_permissions')
    assert callable(mock_agent_loop._get_tool_permissions)


@pytest.mark.asyncio
async def test_verbose_mode_integration(mock_agent_loop):
    """Verify that verbose mode actually appends debug output during tool execution."""
    from kabot.bus.events import InboundMessage

    # Create a mock session with verbose mode enabled
    mock_session = Mock()
    mock_session.metadata = {
        'directives': {
            'verbose': True,
            'think': False,
            'elevated': False
        }
    }

    # Create a mock response with tool calls
    mock_tool_call = Mock()
    mock_tool_call.id = "call_123"
    mock_tool_call.name = "read_file"
    mock_tool_call.arguments = {"path": "/test/file.txt"}

    mock_response = Mock()
    mock_response.tool_calls = [mock_tool_call]
    mock_response.content = None
    mock_response.reasoning_content = None
    mock_response.has_tool_calls = True

    # Mock tool execution
    mock_agent_loop.tools.execute = AsyncMock(return_value="File content here")

    # Mock context methods
    mock_agent_loop.context.add_assistant_message = Mock(return_value=[])
    mock_agent_loop.context.add_tool_result = Mock(return_value=[])

    # Mock memory
    mock_agent_loop.memory.add_message = AsyncMock()

    # Mock bus
    mock_agent_loop.bus.publish_outbound = AsyncMock()

    # Create a mock message
    msg = InboundMessage(
        channel="cli",
        sender_id="user",
        chat_id="test",
        content="test message",
        _session_key="cli:test"
    )

    # Execute tool calls
    messages = []
    result_messages = await mock_agent_loop._process_tool_calls(msg, messages, mock_response, mock_session)

    # Verify that add_tool_result was called
    assert mock_agent_loop.context.add_tool_result.called

    # Get the result that was passed to add_tool_result
    call_args = mock_agent_loop.context.add_tool_result.call_args
    result_for_llm = call_args[0][3]  # Fourth argument is the result

    # Verify verbose output is present
    assert "[DEBUG] Tool: read_file" in result_for_llm
    assert "[DEBUG] Tokens:" in result_for_llm
    assert "[DEBUG] Result:" in result_for_llm


@pytest.mark.asyncio
async def test_elevated_mode_integration(mock_agent_loop):
    """Verify that elevated mode permissions are retrieved during tool execution."""
    from kabot.bus.events import InboundMessage

    # Create a mock session with elevated mode enabled
    mock_session = Mock()
    mock_session.metadata = {
        'directives': {
            'verbose': False,
            'think': False,
            'elevated': True
        }
    }

    # Create a mock response with tool calls
    mock_tool_call = Mock()
    mock_tool_call.id = "call_456"
    mock_tool_call.name = "exec"
    mock_tool_call.arguments = {"command": "ls -la"}

    mock_response = Mock()
    mock_response.tool_calls = [mock_tool_call]
    mock_response.content = None
    mock_response.reasoning_content = None
    mock_response.has_tool_calls = True

    # Mock tool execution
    mock_agent_loop.tools.execute = AsyncMock(return_value="Command output")

    # Mock context methods
    mock_agent_loop.context.add_assistant_message = Mock(return_value=[])
    mock_agent_loop.context.add_tool_result = Mock(return_value=[])

    # Mock memory
    mock_agent_loop.memory.add_message = AsyncMock()

    # Mock bus
    mock_agent_loop.bus.publish_outbound = AsyncMock()

    # Create a mock message
    msg = InboundMessage(
        channel="cli",
        sender_id="user",
        chat_id="test",
        content="test message",
        _session_key="cli:test"
    )

    # Execute tool calls
    messages = []
    result_messages = await mock_agent_loop._process_tool_calls(msg, messages, mock_response, mock_session)

    # Verify that permissions were retrieved
    permissions = mock_agent_loop._get_tool_permissions(mock_session)
    assert permissions['auto_approve'] is True
    assert permissions['restrict_to_workspace'] is False
    assert permissions['allow_high_risk'] is True


def test_verbose_mode_disabled_by_default(mock_agent_loop):
    """Verify that verbose mode is disabled when not specified."""
    mock_session = Mock()
    mock_session.metadata = {'directives': {}}

    assert mock_agent_loop._should_log_verbose(mock_session) is False


def test_elevated_mode_disabled_by_default(mock_agent_loop):
    """Verify that elevated mode returns safe defaults when not specified."""
    mock_session = Mock()
    mock_session.metadata = {'directives': {}}

    permissions = mock_agent_loop._get_tool_permissions(mock_session)
    assert permissions['auto_approve'] is False
    assert permissions['restrict_to_workspace'] is True
    assert permissions['allow_high_risk'] is False
