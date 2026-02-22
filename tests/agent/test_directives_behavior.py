"""Tests for directives behavior consumption."""

from unittest.mock import Mock

import pytest

from kabot.agent.loop import AgentLoop


@pytest.fixture
def mock_session():
    """Create a mock session with directives metadata."""
    session = Mock()
    session.metadata = {}
    return session


def test_think_mode_injects_reasoning_prompt(mock_session):
    """Think mode should inject reasoning prompt into messages."""
    # Arrange
    mock_session.metadata['directives'] = {'think': True, 'verbose': False, 'elevated': False}
    messages = [
        {"role": "user", "content": "Hello"}
    ]

    # Create a minimal AgentLoop instance (we only need the method)

    loop = AgentLoop.__new__(AgentLoop)

    # Act
    result = loop._apply_think_mode(messages.copy(), mock_session)

    # Assert
    assert len(result) == 2  # Original + reasoning prompt
    assert result[0]["role"] == "system"
    assert "Think step-by-step" in result[0]["content"]
    assert "reasoning process" in result[0]["content"]
    assert result[1] == messages[0]  # Original message preserved


def test_think_mode_disabled_by_default(mock_session):
    """Think mode disabled should not modify messages."""
    # Arrange
    mock_session.metadata['directives'] = {'think': False, 'verbose': False, 'elevated': False}
    messages = [
        {"role": "user", "content": "Hello"}
    ]

    loop = AgentLoop.__new__(AgentLoop)

    # Act
    result = loop._apply_think_mode(messages.copy(), mock_session)

    # Assert
    assert result == messages  # Unchanged


def test_think_mode_handles_corrupted_directives(mock_session):
    """Think mode should handle corrupted directives gracefully."""
    # Arrange
    mock_session.metadata['directives'] = "not a dict"  # Corrupted
    messages = [
        {"role": "user", "content": "Hello"}
    ]

    loop = AgentLoop.__new__(AgentLoop)

    # Act
    result = loop._apply_think_mode(messages.copy(), mock_session)

    # Assert
    assert result == messages  # Unchanged, no error


def test_verbose_mode_enabled(mock_session):
    """Verbose mode enabled should return True."""
    # Arrange
    mock_session.metadata['directives'] = {'think': False, 'verbose': True, 'elevated': False}

    loop = AgentLoop.__new__(AgentLoop)

    # Act
    result = loop._should_log_verbose(mock_session)

    # Assert
    assert result is True


def test_verbose_mode_disabled(mock_session):
    """Verbose mode disabled should return False."""
    # Arrange
    mock_session.metadata['directives'] = {'think': False, 'verbose': False, 'elevated': False}

    loop = AgentLoop.__new__(AgentLoop)

    # Act
    result = loop._should_log_verbose(mock_session)

    # Assert
    assert result is False


def test_format_verbose_output(mock_session):
    """Verbose mode should format output with DEBUG prefix."""
    # Arrange
    loop = AgentLoop.__new__(AgentLoop)

    # Act
    result = loop._format_verbose_output("test_tool", "result data", 150)

    # Assert
    assert "[DEBUG] Tool: test_tool" in result
    assert "[DEBUG] Tokens: 150" in result
    assert "[DEBUG] Result:\nresult data" in result


def test_elevated_mode_enabled(mock_session):
    """Elevated mode should enable auto-approve and high-risk operations."""
    # Arrange
    mock_session.metadata['directives'] = {'think': False, 'verbose': False, 'elevated': True}

    loop = AgentLoop.__new__(AgentLoop)

    # Act
    result = loop._get_tool_permissions(mock_session)

    # Assert
    assert result["auto_approve"] is True
    assert result["restrict_to_workspace"] is False
    assert result["allow_high_risk"] is True


def test_elevated_mode_disabled(mock_session):
    """Elevated mode disabled should keep restrictions."""
    # Arrange
    mock_session.metadata['directives'] = {'think': False, 'verbose': False, 'elevated': False}

    loop = AgentLoop.__new__(AgentLoop)

    # Act
    result = loop._get_tool_permissions(mock_session)

    # Assert
    assert result["auto_approve"] is False
    assert result["restrict_to_workspace"] is True
    assert result["allow_high_risk"] is False


def test_directives_error_handling(mock_session):
    """Directives methods should handle errors gracefully."""
    # Arrange
    mock_session.metadata = None  # Will cause AttributeError

    loop = AgentLoop.__new__(AgentLoop)

    # Act & Assert - should not raise exceptions
    think_result = loop._apply_think_mode([{"role": "user", "content": "test"}], mock_session)
    verbose_result = loop._should_log_verbose(mock_session)
    permissions_result = loop._get_tool_permissions(mock_session)

    # All should return safe defaults
    assert len(think_result) == 1
    assert verbose_result is False
    assert permissions_result["auto_approve"] is False
    assert permissions_result["restrict_to_workspace"] is True
    assert permissions_result["allow_high_risk"] is False
