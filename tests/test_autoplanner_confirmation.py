"""Tests for AutoPlanner user confirmation functionality.

This module tests the user confirmation flow for destructive actions in AutoPlanner.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from kabot.agent.tools.autoplanner import (
    AutoPlanner, Plan, Step, ExecutionResult,
    DESTRUCTIVE_TOOLS
)
from kabot.agent.tools.registry import ToolRegistry
from kabot.bus.queue import MessageBus
from kabot.bus.events import InboundMessage, OutboundMessage


class MockTool:
    """Mock tool for testing."""

    def __init__(self, name, return_value=None, should_fail=False):
        self.name = name
        self.return_value = return_value or f"Result from {name}"
        self.should_fail = should_fail
        self.execute = AsyncMock()

        if should_fail:
            self.execute.side_effect = Exception(f"Error in {name}")
        else:
            self.execute.return_value = self.return_value


class MockToolRegistry:
    """Mock tool registry for testing."""

    def __init__(self):
        self._tools = {}

    def register(self, tool):
        """Register a mock tool."""
        self._tools[tool.name] = tool

    def get(self, name):
        """Get a tool by name."""
        return self._tools.get(name)

    def has(self, name):
        """Check if tool exists."""
        return name in self._tools


class MockMessageBus:
    """Mock message bus for testing confirmation flows."""

    def __init__(self):
        self.messages = []
        self.inbound_queue = asyncio.Queue()
        self.outbound = Mock()
        self.outbound.put = AsyncMock()

    async def publish_outbound(self, msg):
        """Capture published messages."""
        self.messages.append(msg)

    async def consume_inbound(self):
        """Consume inbound messages."""
        return await self.inbound_queue.get()

    async def add_inbound_response(self, content, sender_id="user123", chat_id="chat123"):
        """Add an inbound message to the queue."""
        msg = InboundMessage(
            channel="telegram",
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            timestamp=datetime.now()
        )
        await self.inbound_queue.put(msg)


# ============================================================================
# Destructive Tools Set Tests
# ============================================================================

def test_destructive_tools_set():
    """Test that DESTRUCTIVE_TOOLS contains expected tools."""
    assert "write_file" in DESTRUCTIVE_TOOLS
    assert "edit_file" in DESTRUCTIVE_TOOLS
    assert "delete_file" in DESTRUCTIVE_TOOLS
    assert "exec" in DESTRUCTIVE_TOOLS
    assert "cron" in DESTRUCTIVE_TOOLS
    assert "read_file" not in DESTRUCTIVE_TOOLS
    assert "echo" not in DESTRUCTIVE_TOOLS


# ============================================================================
# Confirmation Requirement Tests
# ============================================================================

def test_should_confirm_destructive_tools():
    """Test that destructive tools require confirmation."""
    planner = AutoPlanner(confirm_destructive=True)

    for tool_name in DESTRUCTIVE_TOOLS:
        step = Step(tool=tool_name, params={})
        assert planner._should_confirm(step) is True, f"{tool_name} should require confirmation"


def test_should_not_confirm_non_destructive_tools():
    """Test that non-destructive tools don't require confirmation."""
    planner = AutoPlanner(confirm_destructive=True)

    non_destructive = ["read_file", "echo", "count_lines", "shell"]
    for tool_name in non_destructive:
        step = Step(tool=tool_name, params={})
        assert planner._should_confirm(step) is False, f"{tool_name} should not require confirmation"


def test_should_confirm_respects_configuration():
    """Test that confirmation can be disabled via configuration."""
    planner = AutoPlanner(confirm_destructive=False)

    for tool_name in DESTRUCTIVE_TOOLS:
        step = Step(tool=tool_name, params={})
        assert planner._should_confirm(step) is False, f"{tool_name} should not require confirmation when disabled"


# ============================================================================
# Confirmation Message Formatting Tests
# ============================================================================

def test_format_confirmation_message_write_file():
    """Test confirmation message for write_file."""
    planner = AutoPlanner()
    step = Step(tool="write_file", params={"path": "test.txt"})
    message = planner._format_confirmation_message(step)

    assert "AutoPlanner ingin" in message
    assert "menulis file" in message
    assert "test.txt" in message
    assert "Setuju?" in message


def test_format_confirmation_message_delete_file():
    """Test confirmation message for delete_file."""
    planner = AutoPlanner()
    step = Step(tool="delete_file", params={"path": "important.doc"})
    message = planner._format_confirmation_message(step)

    assert "menghapus file" in message
    assert "important.doc" in message


def test_format_confirmation_message_exec():
    """Test confirmation message for exec."""
    planner = AutoPlanner()
    step = Step(tool="exec", params={"command": "rm -rf /"})
    message = planner._format_confirmation_message(step)

    assert "menjalankan perintah shell" in message
    assert "rm -rf /" in message


def test_format_confirmation_message_cron():
    """Test confirmation message for cron."""
    planner = AutoPlanner()
    step = Step(tool="cron", params={"schedule": "0 0 * * *", "command": "backup.sh"})
    message = planner._format_confirmation_message(step)

    assert "mengatur jadwal cron" in message
    assert "0 0 * * *" in message


def test_format_confirmation_message_edit_file():
    """Test confirmation message for edit_file."""
    planner = AutoPlanner()
    step = Step(tool="edit_file", params={"path": "config.ini"})
    message = planner._format_confirmation_message(step)

    assert "mengedit file" in message
    assert "config.ini" in message


def test_format_confirmation_message_unknown_tool():
    """Test confirmation message for unknown destructive tool."""
    planner = AutoPlanner()
    step = Step(tool="dangerous_tool", params={})
    message = planner._format_confirmation_message(step)

    assert "melakukan dangerous_tool" in message


# ============================================================================
# Confirmation Flow Tests
# ============================================================================

@pytest.mark.asyncio
async def test_autoplanner_asks_confirmation_for_destructive():
    """Test that AutoPlanner asks for confirmation before destructive actions."""
    mock_bus = MockMessageBus()
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("delete_file", return_value="File deleted")
    mock_registry.register(mock_tool)

    planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus, confirm_destructive=True)
    plan = Plan(steps=[Step(tool="delete_file", params={"path": "test.txt"})])

    # Schedule a "ya" response
    asyncio.create_task(mock_bus.add_inbound_response("ya"))

    result = await planner.execute_plan(plan)

    # Verify confirmation was requested
    confirmation_messages = [msg for msg in mock_bus.messages if "Konfirmasi" in msg.content or "ingin" in msg.content]
    assert len(confirmation_messages) >= 1
    assert result.success is True


@pytest.mark.asyncio
async def test_autoplanner_respects_rejection():
    """Test that AutoPlanner respects user rejection."""
    mock_bus = MockMessageBus()
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("delete_file", return_value="File deleted")
    mock_registry.register(mock_tool)

    planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus, confirm_destructive=True)
    plan = Plan(steps=[Step(tool="delete_file", params={"path": "test.txt"})])

    # Schedule a "tidak" response
    asyncio.create_task(mock_bus.add_inbound_response("tidak"))

    result = await planner.execute_plan(plan)

    assert result.success is False
    assert "Dibatalkan oleh user" in result.error


@pytest.mark.asyncio
async def test_autoplanner_handles_timeout():
    """Test that AutoPlanner handles confirmation timeout."""
    mock_bus = MockMessageBus()
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("delete_file", return_value="File deleted")
    mock_registry.register(mock_tool)

    planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus, confirm_destructive=True)
    planner._confirmation_timeout = 0.1  # Short timeout for testing
    plan = Plan(steps=[Step(tool="delete_file", params={"path": "test.txt"})])

    result = await planner.execute_plan(plan)

    assert result.success is False
    assert "Timeout" in result.error


@pytest.mark.asyncio
async def test_autoplanner_accepts_various_confirmations():
    """Test that AutoPlanner accepts various confirmation responses."""
    confirmations = ["ya", "yes", "Y", "YES", "Setuju"]

    for confirmation in confirmations:
        mock_bus = MockMessageBus()
        mock_registry = MockToolRegistry()
        mock_tool = MockTool("delete_file", return_value="File deleted")
        mock_registry.register(mock_tool)

        planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus, confirm_destructive=True)
        plan = Plan(steps=[Step(tool="delete_file", params={"path": "test.txt"})])

        # Schedule confirmation response
        asyncio.create_task(mock_bus.add_inbound_response(confirmation))

        result = await planner.execute_plan(plan)

        assert result.success is True, f"Should accept '{confirmation}' as valid confirmation"


@pytest.mark.asyncio
async def test_autoplanner_rejects_various_rejections():
    """Test that AutoPlanner rejects various rejection responses."""
    rejections = ["tidak", "no", "N", "NO", "batal", "cancel"]

    for rejection in rejections:
        mock_bus = MockMessageBus()
        mock_registry = MockToolRegistry()
        mock_tool = MockTool("delete_file", return_value="File deleted")
        mock_registry.register(mock_tool)

        planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus, confirm_destructive=True)
        plan = Plan(steps=[Step(tool="delete_file", params={"path": "test.txt"})])

        # Schedule rejection response
        asyncio.create_task(mock_bus.add_inbound_response(rejection))

        result = await planner.execute_plan(plan)

        assert result.success is False, f"Should reject '{rejection}' as valid rejection"
        assert "Dibatalkan oleh user" in result.error


# ============================================================================
# Configuration Option Tests
# ============================================================================

@pytest.mark.asyncio
async def test_autoplanner_skips_confirmation_when_disabled():
    """Test that AutoPlanner skips confirmation when disabled."""
    mock_bus = MockMessageBus()
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("delete_file", return_value="File deleted")
    mock_registry.register(mock_tool)

    planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus, confirm_destructive=False)
    plan = Plan(steps=[Step(tool="delete_file", params={"path": "test.txt"})])

    result = await planner.execute_plan(plan)

    # Should succeed without asking for confirmation
    assert result.success is True
    # No confirmation messages should be sent
    confirmation_messages = [msg for msg in mock_bus.messages if "Konfirmasi" in msg.content or "ingin" in msg.content]
    assert len(confirmation_messages) == 0


@pytest.mark.asyncio
async def test_autoplanner_skips_confirmation_without_bus():
    """Test that AutoPlanner skips confirmation when no message bus is available."""
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("delete_file", return_value="File deleted")
    mock_registry.register(mock_tool)

    planner = AutoPlanner(tool_registry=mock_registry, message_bus=None, confirm_destructive=True)
    plan = Plan(steps=[Step(tool="delete_file", params={"path": "test.txt"})])

    result = await planner.execute_plan(plan)

    # Should succeed without confirmation when no bus available
    assert result.success is True


# ============================================================================
# Mixed Plan Tests
# ============================================================================

@pytest.mark.asyncio
async def test_autoplanner_confirms_only_destructive_in_plan():
    """Test that AutoPlanner only asks for confirmation on destructive steps."""
    mock_bus = MockMessageBus()
    mock_registry = MockToolRegistry()

    read_tool = MockTool("read_file", return_value="File content")
    delete_tool = MockTool("delete_file", return_value="File deleted")

    mock_registry.register(read_tool)
    mock_registry.register(delete_tool)

    planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus, confirm_destructive=True)
    plan = Plan(steps=[
        Step(tool="read_file", params={"path": "test.txt"}),
        Step(tool="delete_file", params={"path": "test.txt"})
    ])

    # Schedule a "ya" response for the destructive step
    asyncio.create_task(mock_bus.add_inbound_response("ya"))

    result = await planner.execute_plan(plan)

    assert result.success is True
    # Should only ask for confirmation once (for delete_file)
    confirmation_messages = [msg for msg in mock_bus.messages if "ingin" in msg.content]
    assert len(confirmation_messages) == 1


@pytest.mark.asyncio
async def test_autoplanner_handles_multiple_destructive_steps():
    """Test that AutoPlanner handles multiple destructive steps in sequence."""
    mock_bus = MockMessageBus()
    mock_registry = MockToolRegistry()

    write_tool = MockTool("write_file", return_value="File written")
    delete_tool = MockTool("delete_file", return_value="File deleted")

    mock_registry.register(write_tool)
    mock_registry.register(delete_tool)

    planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus, confirm_destructive=True)
    plan = Plan(steps=[
        Step(tool="write_file", params={"path": "test1.txt", "content": "Hello"}),
        Step(tool="delete_file", params={"path": "test2.txt"})
    ])

    # Schedule confirmation responses
    asyncio.create_task(mock_bus.add_inbound_response("ya"))
    asyncio.create_task(mock_bus.add_inbound_response("ya"))

    result = await planner.execute_plan(plan)

    assert result.success is True
    # Should ask for confirmation twice (once for each destructive step)
    confirmation_messages = [msg for msg in mock_bus.messages if "ingin" in msg.content]
    assert len(confirmation_messages) == 2


@pytest.mark.asyncio
async def test_autoplanner_stops_on_rejection_in_multi_step_plan():
    """Test that AutoPlanner stops execution when user rejects a step."""
    mock_bus = MockMessageBus()
    mock_registry = MockToolRegistry()

    write_tool = MockTool("write_file", return_value="File written")
    delete_tool = MockTool("delete_file", return_value="File deleted")

    mock_registry.register(write_tool)
    mock_registry.register(delete_tool)

    planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus, confirm_destructive=True)
    plan = Plan(steps=[
        Step(tool="write_file", params={"path": "test1.txt", "content": "Hello"}),
        Step(tool="delete_file", params={"path": "test2.txt"})
    ])

    # Confirm first step, reject second
    asyncio.create_task(mock_bus.add_inbound_response("ya"))
    asyncio.create_task(mock_bus.add_inbound_response("tidak"))

    result = await planner.execute_plan(plan)

    assert result.success is False
    assert "Dibatalkan oleh user" in result.error
    # First step should be executed
    write_tool.execute.assert_called_once()
    # Second step should not be executed
    delete_tool.execute.assert_not_called()


# ============================================================================
# Edge Case Tests
# ============================================================================

@pytest.mark.asyncio
async def test_autoplanner_handles_invalid_responses():
    """Test that AutoPlanner continues waiting on invalid responses."""
    mock_bus = MockMessageBus()
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("delete_file", return_value="File deleted")
    mock_registry.register(mock_tool)

    planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus, confirm_destructive=True)
    planner._confirmation_timeout = 1.0  # 1 second timeout for testing
    plan = Plan(steps=[Step(tool="delete_file", params={"path": "test.txt"})])

    # Schedule invalid responses followed by valid confirmation
    async def send_responses():
        await mock_bus.add_inbound_response("maybe")
        await mock_bus.add_inbound_response("what?")
        await mock_bus.add_inbound_response("ya")

    asyncio.create_task(send_responses())

    result = await planner.execute_plan(plan)

    assert result.success is True


@pytest.mark.asyncio
async def test_autoplanner_empty_plan():
    """Test that AutoPlanner handles empty plans."""
    mock_bus = MockMessageBus()
    planner = AutoPlanner(tool_registry=MockToolRegistry(), message_bus=mock_bus, confirm_destructive=True)
    plan = Plan(steps=[])

    result = await planner.execute_plan(plan)

    assert result.success is True
    assert "No steps to execute" in result.output


@pytest.mark.asyncio
async def test_autoplanner_preserves_step_result_on_confirmation():
    """Test that step results are preserved after confirmation."""
    mock_bus = MockMessageBus()
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("write_file", return_value="Success: File written")
    mock_registry.register(mock_tool)

    planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus, confirm_destructive=True)
    plan = Plan(steps=[Step(tool="write_file", params={"path": "test.txt", "content": "Hello"})])

    # Schedule confirmation
    asyncio.create_task(mock_bus.add_inbound_response("ya"))

    result = await planner.execute_plan(plan)

    assert result.success is True
    mock_tool.execute.assert_called_once_with(path="test.txt", content="Hello")


# ============================================================================
# Message Format Tests
# ============================================================================

def test_confirmation_message_metadata():
    """Test that confirmation messages have correct metadata."""
    planner = AutoPlanner()
    step = Step(tool="delete_file", params={"path": "test.txt"})
    message = planner._format_confirmation_message(step)

    assert "test.txt" in message
    assert "menghapus" in message


@pytest.mark.asyncio
async def test_autoplanner_sends_correct_metadata():
    """Test that confirmation messages include correct metadata."""
    mock_bus = MockMessageBus()
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("delete_file", return_value="File deleted")
    mock_registry.register(mock_tool)

    planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus, confirm_destructive=True)
    plan = Plan(steps=[Step(tool="delete_file", params={"path": "test.txt"})])

    # Schedule timeout to avoid waiting
    planner._confirmation_timeout = 0.1

    await planner.execute_plan(plan)

    # Find confirmation message
    confirmation_msgs = [msg for msg in mock_bus.messages if msg.metadata.get("type") == "confirmation_request"]
    assert len(confirmation_msgs) == 1
    assert confirmation_msgs[0].metadata["tool"] == "delete_file"
    assert "path" in confirmation_msgs[0].metadata["params"]


# ============================================================================
# Integration with Tool Registry Tests
# ============================================================================

@pytest.mark.asyncio
async def test_autoplanner_confirmation_with_real_registry():
    """Test confirmation flow with real tool registry."""
    mock_bus = MockMessageBus()
    registry = ToolRegistry()

    # Create and register a mock destructive tool
    mock_tool = MockTool("delete_file", return_value="File deleted")
    registry.register(mock_tool)

    planner = AutoPlanner(tool_registry=registry, message_bus=mock_bus, confirm_destructive=True)
    plan = Plan(steps=[Step(tool="delete_file", params={"path": "test.txt"})])

    # Schedule confirmation
    asyncio.create_task(mock_bus.add_inbound_response("ya"))

    result = await planner.execute_plan(plan)

    assert result.success is True
    mock_tool.execute.assert_called_once()


# ============================================================================
# Timeout Message Tests
# ============================================================================

@pytest.mark.asyncio
async def test_timeout_message_sent():
    """Test that timeout message is sent when confirmation times out."""
    mock_bus = MockMessageBus()
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("delete_file", return_value="File deleted")
    mock_registry.register(mock_tool)

    planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus, confirm_destructive=True)
    planner._confirmation_timeout = 0.1  # Short timeout
    plan = Plan(steps=[Step(tool="delete_file", params={"path": "test.txt"})])

    await planner.execute_plan(plan)

    # Find timeout message
    timeout_msgs = [msg for msg in mock_bus.messages if msg.metadata.get("type") == "timeout"]
    assert len(timeout_msgs) == 1
    assert "Timeout" in timeout_msgs[0].content


@pytest.mark.asyncio
async def test_cancellation_message_sent():
    """Test that cancellation message is sent when user rejects."""
    mock_bus = MockMessageBus()
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("delete_file", return_value="File deleted")
    mock_registry.register(mock_tool)

    planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus, confirm_destructive=True)
    plan = Plan(steps=[Step(tool="delete_file", params={"path": "test.txt"})])

    # Schedule rejection
    asyncio.create_task(mock_bus.add_inbound_response("tidak"))

    await planner.execute_plan(plan)

    # Find cancellation message
    cancel_msgs = [msg for msg in mock_bus.messages if msg.metadata.get("type") == "cancelled"]
    assert len(cancel_msgs) == 1
    assert "Dibatalkan oleh user" in cancel_msgs[0].content
