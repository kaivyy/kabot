"""Tests for system event bus functionality."""

import asyncio

import pytest

from kabot.bus.events import SystemEvent
from kabot.bus.queue import MessageBus


@pytest.fixture
def bus():
    """Provide a MessageBus instance."""
    return MessageBus()


class TestSystemEventCreation:
    """Test SystemEvent factory methods."""

    def test_lifecycle_event(self):
        """Test lifecycle event creation."""
        event = SystemEvent.lifecycle("run-123", 1, "start", component="agent_loop")

        assert event.run_id == "run-123"
        assert event.seq == 1
        assert event.stream == "lifecycle"
        assert event.data["action"] == "start"
        assert event.data["component"] == "agent_loop"
        assert isinstance(event.timestamp, float)

    def test_tool_event(self):
        """Test tool event creation."""
        event = SystemEvent.tool("run-123", 2, "exec", "start", params={"cmd": "ls"})

        assert event.run_id == "run-123"
        assert event.seq == 2
        assert event.stream == "tool"
        assert event.data["tool"] == "exec"
        assert event.data["status"] == "start"
        assert event.data["params"] == {"cmd": "ls"}

    def test_assistant_event(self):
        """Test assistant event creation."""
        event = SystemEvent.assistant("run-123", 3, "Hello world", tokens=10)

        assert event.run_id == "run-123"
        assert event.seq == 3
        assert event.stream == "assistant"
        assert event.data["content"] == "Hello world"
        assert event.data["tokens"] == 10

    def test_error_event(self):
        """Test error event creation."""
        event = SystemEvent.error("run-123", 4, "processing_error", "Something failed", details="stack trace")

        assert event.run_id == "run-123"
        assert event.seq == 4
        assert event.stream == "error"
        assert event.data["error_type"] == "processing_error"
        assert event.data["message"] == "Something failed"
        assert event.data["details"] == "stack trace"


class TestMessageBusSequencing:
    """Test monotonic sequence generation."""

    def test_get_next_seq_starts_at_one(self, bus):
        """Test that sequence starts at 1."""
        seq = bus.get_next_seq("run-123")
        assert seq == 1

    def test_get_next_seq_increments(self, bus):
        """Test that sequence increments monotonically."""
        seq1 = bus.get_next_seq("run-123")
        seq2 = bus.get_next_seq("run-123")
        seq3 = bus.get_next_seq("run-123")

        assert seq1 == 1
        assert seq2 == 2
        assert seq3 == 3

    def test_get_next_seq_per_run(self, bus):
        """Test that sequences are independent per run."""
        seq1_run1 = bus.get_next_seq("run-1")
        seq1_run2 = bus.get_next_seq("run-2")
        seq2_run1 = bus.get_next_seq("run-1")
        seq2_run2 = bus.get_next_seq("run-2")

        assert seq1_run1 == 1
        assert seq1_run2 == 1
        assert seq2_run1 == 2
        assert seq2_run2 == 2


@pytest.mark.asyncio
class TestSystemEventEmission:
    """Test system event emission."""

    async def test_emit_system_event(self, bus):
        """Test emitting a system event."""
        event = SystemEvent.lifecycle("run-123", 1, "start")

        await bus.emit_system_event(event)

        # Event should be in queue
        assert bus.system_events_size == 1

    async def test_emit_multiple_events(self, bus):
        """Test emitting multiple events."""
        event1 = SystemEvent.lifecycle("run-123", 1, "start")
        event2 = SystemEvent.tool("run-123", 2, "exec", "start")
        event3 = SystemEvent.lifecycle("run-123", 3, "stop")

        await bus.emit_system_event(event1)
        await bus.emit_system_event(event2)
        await bus.emit_system_event(event3)

        assert bus.system_events_size == 3


@pytest.mark.asyncio
class TestSystemEventSubscription:
    """Test system event subscription."""

    async def test_subscribe_system_events(self, bus):
        """Test subscribing to system events."""
        received_events = []

        async def callback(event):
            received_events.append(event)

        bus.subscribe_system_events(callback)

        event = SystemEvent.lifecycle("run-123", 1, "start")
        await bus.emit_system_event(event)

        # Give callback time to execute
        await asyncio.sleep(0.1)

        assert len(received_events) == 1
        assert received_events[0].run_id == "run-123"

    async def test_multiple_subscribers(self, bus):
        """Test multiple subscribers receive events."""
        received1 = []
        received2 = []

        async def callback1(event):
            received1.append(event)

        async def callback2(event):
            received2.append(event)

        bus.subscribe_system_events(callback1)
        bus.subscribe_system_events(callback2)

        event = SystemEvent.lifecycle("run-123", 1, "start")
        await bus.emit_system_event(event)

        await asyncio.sleep(0.1)

        assert len(received1) == 1
        assert len(received2) == 1

    async def test_subscriber_error_handling(self, bus):
        """Test that subscriber errors don't break event emission."""
        received = []

        async def failing_callback(event):
            raise ValueError("Simulated error")

        async def working_callback(event):
            received.append(event)

        bus.subscribe_system_events(failing_callback)
        bus.subscribe_system_events(working_callback)

        event = SystemEvent.lifecycle("run-123", 1, "start")
        await bus.emit_system_event(event)

        await asyncio.sleep(0.1)

        # Working callback should still receive event
        assert len(received) == 1


@pytest.mark.asyncio
class TestSystemEventDispatch:
    """Test system event dispatch background task."""

    async def test_dispatch_system_events(self, bus):
        """Test dispatching system events in background."""
        received_events = []

        async def callback(event):
            received_events.append(event)

        bus.subscribe_system_events(callback)

        # Start dispatcher
        dispatch_task = asyncio.create_task(bus.dispatch_system_events())

        # Emit events
        event1 = SystemEvent.lifecycle("run-123", 1, "start")
        event2 = SystemEvent.tool("run-123", 2, "exec", "start")

        await bus.emit_system_event(event1)
        await bus.emit_system_event(event2)

        # Wait for dispatch
        await asyncio.sleep(0.2)

        # Stop dispatcher
        bus.stop()
        await asyncio.wait_for(dispatch_task, timeout=2.0)

        # Both events should be received
        assert len(received_events) >= 2


class TestSystemEventIntegration:
    """Integration tests for system events."""

    def test_event_ordering(self, bus):
        """Test that events maintain sequence order."""
        events = []
        for i in range(10):
            seq = bus.get_next_seq("run-123")
            event = SystemEvent.lifecycle("run-123", seq, f"action-{i}")
            events.append(event)

        # Verify sequences are monotonic
        for i, event in enumerate(events):
            assert event.seq == i + 1

    def test_multiple_runs_independent(self, bus):
        """Test that multiple runs maintain independent sequences."""
        run1_events = []
        run2_events = []

        for i in range(5):
            seq1 = bus.get_next_seq("run-1")
            seq2 = bus.get_next_seq("run-2")

            run1_events.append(SystemEvent.lifecycle("run-1", seq1, f"action-{i}"))
            run2_events.append(SystemEvent.lifecycle("run-2", seq2, f"action-{i}"))

        # Both runs should have sequences 1-5
        assert [e.seq for e in run1_events] == [1, 2, 3, 4, 5]
        assert [e.seq for e in run2_events] == [1, 2, 3, 4, 5]
