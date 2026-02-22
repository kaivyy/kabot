"""Tests for HookManager (Phase 10)."""

import pytest

from kabot.plugins.hooks import HookManager


@pytest.mark.asyncio
async def test_hook_registration():
    """Test registering hooks."""
    hooks = HookManager()

    async def handler():
        return "handled"

    hooks.on("TEST_EVENT", handler)

    # Check handler count
    assert hooks.handler_count("TEST_EVENT") == 1


@pytest.mark.asyncio
async def test_hook_emission_sync():
    """Test emitting events with async handlers."""
    hooks = HookManager()
    results = []

    async def handler(value):
        results.append(value)
        return f"processed: {value}"

    hooks.on("TEST_EVENT", handler)

    emitted = await hooks.emit("TEST_EVENT", value="test_value")

    assert len(emitted) == 1
    assert emitted[0] == "processed: test_value"
    assert results == ["test_value"]


@pytest.mark.asyncio
async def test_hook_emission_async():
    """Test emitting events with async handlers."""
    hooks = HookManager()
    results = []

    async def handler(value):
        results.append(value)
        return f"async processed: {value}"

    hooks.on("TEST_EVENT", handler)

    emitted = await hooks.emit("TEST_EVENT", value="test_value")

    assert len(emitted) == 1
    assert emitted[0] == "async processed: test_value"
    assert results == ["test_value"]


@pytest.mark.asyncio
async def test_multiple_handlers():
    """Test multiple handlers for same event."""
    hooks = HookManager()
    results = []

    async def handler1(value):
        results.append(f"h1:{value}")

    async def handler2(value):
        results.append(f"h2:{value}")

    hooks.on("TEST_EVENT", handler1)
    hooks.on("TEST_EVENT", handler2)

    await hooks.emit("TEST_EVENT", value="test")

    assert len(results) == 2
    assert "h1:test" in results
    assert "h2:test" in results


@pytest.mark.asyncio
async def test_hook_with_kwargs():
    """Test hooks with keyword arguments."""
    hooks = HookManager()

    async def handler(name, value=None):
        return f"{name}={value}"

    hooks.on("TEST_EVENT", handler)

    results = await hooks.emit("TEST_EVENT", name="key", value="val")

    assert len(results) == 1
    assert results[0] == "key=val"


@pytest.mark.asyncio
async def test_hook_error_handling():
    """Test that hook errors don't crash the system."""
    hooks = HookManager()

    async def failing_handler():
        raise ValueError("Handler failed")

    async def working_handler():
        return "success"

    hooks.on("TEST_EVENT", failing_handler)
    hooks.on("TEST_EVENT", working_handler)

    # Should not raise, should continue to working_handler
    results = await hooks.emit("TEST_EVENT")

    # Failing handler returns None, working handler returns "success"
    assert len(results) == 2
    assert results[0] is None
    assert results[1] == "success"


@pytest.mark.asyncio
async def test_emit_nonexistent_event():
    """Test emitting event with no handlers."""
    hooks = HookManager()

    results = await hooks.emit("NONEXISTENT_EVENT")

    assert results == []


@pytest.mark.asyncio
async def test_handler_count():
    """Test counting handlers for events."""
    hooks = HookManager()

    async def handler1():
        pass

    async def handler2():
        pass

    hooks.on("EVENT1", handler1)
    hooks.on("EVENT1", handler2)
    hooks.on("EVENT2", handler1)

    assert hooks.handler_count("EVENT1") == 2
    assert hooks.handler_count("EVENT2") == 1
    assert hooks.handler_count() == 3


@pytest.mark.asyncio
async def test_off_handler():
    """Test removing specific handler."""
    hooks = HookManager()

    async def handler1():
        pass

    async def handler2():
        pass

    hooks.on("EVENT1", handler1)
    hooks.on("EVENT1", handler2)

    # Remove handler1
    removed = hooks.off("EVENT1", handler1)
    assert removed is True
    assert hooks.handler_count("EVENT1") == 1

    # Try to remove again
    removed = hooks.off("EVENT1", handler1)
    assert removed is False


@pytest.mark.asyncio
async def test_hook_lifecycle_events():
    """Test typical lifecycle event flow."""
    hooks = HookManager()
    events_fired = []

    async def on_startup():
        events_fired.append("startup")

    async def on_message(msg):
        events_fired.append(f"message:{msg}")

    async def on_shutdown():
        events_fired.append("shutdown")

    hooks.on("ON_STARTUP", on_startup)
    hooks.on("ON_MESSAGE_RECEIVED", on_message)
    hooks.on("ON_SHUTDOWN", on_shutdown)

    # Simulate lifecycle
    await hooks.emit("ON_STARTUP")
    await hooks.emit("ON_MESSAGE_RECEIVED", msg="hello")
    await hooks.emit("ON_MESSAGE_RECEIVED", msg="world")
    await hooks.emit("ON_SHUTDOWN")

    assert events_fired == [
        "startup",
        "message:hello",
        "message:world",
        "shutdown"
    ]
