"""
Hooks System for Kabot (Phase 10).

Provides a lifecycle event system that plugins can subscribe to.
Events are emitted at key points in the agent pipeline.
"""

import asyncio
import logging
from enum import StrEnum
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class HookEvent(StrEnum):
    """Lifecycle events that plugins can subscribe to."""
    
    # System lifecycle
    ON_STARTUP = "on_startup"              # Before agent loop starts
    ON_SHUTDOWN = "on_shutdown"            # Before agent loop stops
    
    # Message lifecycle  
    ON_MESSAGE_RECEIVED = "on_message_received"   # Raw message intercept
    ON_MESSAGE_PROCESSED = "on_message_processed" # After agent processes message
    
    # LLM lifecycle
    PRE_LLM_CALL = "pre_llm_call"          # Before sending to LLM (modify prompt)
    POST_LLM_CALL = "post_llm_call"        # After LLM response (modify response)
    
    # Tool lifecycle
    ON_TOOL_CALL = "on_tool_call"          # Before tool execution
    ON_TOOL_RESULT = "on_tool_result"      # After tool returns result
    
    # Session lifecycle
    ON_SESSION_START = "on_session_start"   # New conversation session created
    ON_SESSION_END = "on_session_end"       # Session terminated
    
    # Error handling
    ON_ERROR = "on_error"                   # Any error in the pipeline


# Type for hook handlers
HookHandler = Callable[..., Awaitable[Any]]


class HookManager:
    """
    Central event bus for plugin hooks.
    
    Plugins register handlers for events they care about.
    The core engine emits events at key pipeline points.
    
    Usage:
        hooks = HookManager()
        hooks.on(HookEvent.PRE_LLM_CALL, my_pre_llm_handler)
        await hooks.emit(HookEvent.PRE_LLM_CALL, messages=messages)
    """
    
    def __init__(self):
        self._listeners: dict[str, list[HookHandler]] = {
            event.value: [] for event in HookEvent
        }
        self._stats: dict[str, int] = {}
    
    def on(self, event: HookEvent | str, handler: HookHandler) -> None:
        """
        Register a handler for an event.
        
        Args:
            event: The event type to listen for.
            handler: Async function to call when event fires.
        """
        event_name = event.value if isinstance(event, HookEvent) else event
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(handler)
        logger.debug(f"Hook registered: {event_name} → {handler.__name__}")
    
    def off(self, event: HookEvent | str, handler: HookHandler) -> bool:
        """
        Unregister a handler for an event.
        
        Returns:
            True if the handler was found and removed.
        """
        event_name = event.value if isinstance(event, HookEvent) else event
        listeners = self._listeners.get(event_name, [])
        if handler in listeners:
            listeners.remove(handler)
            return True
        return False
    
    async def emit(self, event: HookEvent | str, **kwargs: Any) -> list[Any]:
        """
        Emit an event, calling all registered handlers.
        
        Handlers are called in registration order.
        All handlers receive the same kwargs.
        
        Args:
            event: The event to emit.
            **kwargs: Data to pass to handlers.
        
        Returns:
            List of results from all handlers.
        """
        event_name = event.value if isinstance(event, HookEvent) else event
        listeners = self._listeners.get(event_name, [])
        
        if not listeners:
            return []
        
        # Track stats
        self._stats[event_name] = self._stats.get(event_name, 0) + 1
        
        results = []
        for handler in listeners:
            try:
                result = await handler(**kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Hook handler '{handler.__name__}' for '{event_name}' failed: {e}")
                results.append(None)
        
        return results
    
    async def emit_chain(self, event: HookEvent | str, data: Any) -> Any:
        """
        Emit an event where each handler can modify the data.
        
        Each handler receives the output of the previous handler.
        Useful for PRE_LLM_CALL where handlers can modify the prompt.
        
        Args:
            event: The event to emit.
            data: Initial data to pass through the chain.
        
        Returns:
            Final data after all handlers have processed it.
        """
        event_name = event.value if isinstance(event, HookEvent) else event
        listeners = self._listeners.get(event_name, [])
        
        current_data = data
        for handler in listeners:
            try:
                result = await handler(data=current_data)
                if result is not None:
                    current_data = result
            except Exception as e:
                logger.error(f"Chain handler '{handler.__name__}' for '{event_name}' failed: {e}")
        
        return current_data
    
    def handler_count(self, event: HookEvent | str | None = None) -> int:
        """Get number of registered handlers."""
        if event:
            event_name = event.value if isinstance(event, HookEvent) else event
            return len(self._listeners.get(event_name, []))
        return sum(len(h) for h in self._listeners.values())
    
    def get_stats(self) -> str:
        """Get human-readable hook stats."""
        total_handlers = self.handler_count()
        total_events = sum(self._stats.values())
        
        lines = [
            f"🔗 *Hooks Status*",
            f"  Handlers: {total_handlers}",
            f"  Events Emitted: {total_events}",
        ]
        
        if self._stats:
            lines.append(f"  Most Active:")
            sorted_stats = sorted(self._stats.items(), key=lambda x: x[1], reverse=True)
            for event_name, count in sorted_stats[:5]:
                lines.append(f"    {event_name}: {count}×")
        
        return "\n".join(lines)
