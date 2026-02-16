"""Integration tests for Phase 12: Critical Features."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock
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
