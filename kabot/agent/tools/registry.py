"""Tool registry for dynamic tool management."""

from typing import Any, Optional

from kabot.agent.tools.base import Tool


class ToolRegistry:
    """
    Registry for agent tools.

    Allows dynamic registration and execution of tools.
    Phase 14: Added system event emission for tool execution monitoring.
    """

    def __init__(self, bus: Optional[Any] = None, run_id: Optional[str] = None):
        self._tools: dict[str, Tool] = {}
        self._bus = bus  # MessageBus for emitting system events
        self._run_id = run_id  # Run ID for event sequencing

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def get_definitions(self, policy_profile: Optional[str] = None) -> list[dict[str, Any]]:
        """
        Get all tool definitions in OpenAI format.

        Args:
            policy_profile: Optional tool policy profile to filter tools.
                          Options: "minimal", "coding", "messaging", "analysis", "full"
                          If None, returns all tools (default behavior).

        Returns:
            List of tool definitions filtered by policy if specified.
        """
        if policy_profile:
            from kabot.agent.tools.tool_policy import apply_tool_policy, resolve_profile_policy

            policy = resolve_profile_policy(policy_profile)
            tool_names = list(self._tools.keys())
            filtered_names = apply_tool_policy(tool_names, policy)
            return [self._tools[name].to_schema() for name in filtered_names if name in self._tools]

        return [tool.to_schema() for tool in self._tools.values()]

    async def execute(self, name: str, params: dict[str, Any]) -> str:
        """
        Execute a tool by name with given parameters.

        Args:
            name: Tool name.
            params: Tool parameters.

        Returns:
            Tool execution result as string.

        Raises:
            KeyError: If tool not found.
        """
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found"

        # Phase 14: Emit tool start event
        if self._bus and self._run_id:
            from kabot.bus.events import SystemEvent
            seq = self._bus.get_next_seq(self._run_id)
            await self._bus.emit_system_event(
                SystemEvent.tool(self._run_id, seq, name, "start", params=params)
            )

        try:
            errors = tool.validate_params(params)
            if errors:
                error_msg = f"Error: Invalid parameters for tool '{name}': " + "; ".join(errors)

                # Phase 14: Emit tool error event
                if self._bus and self._run_id:
                    from kabot.bus.events import SystemEvent
                    seq = self._bus.get_next_seq(self._run_id)
                    await self._bus.emit_system_event(
                        SystemEvent.tool(self._run_id, seq, name, "error", error=error_msg)
                    )

                return error_msg

            result = await tool.execute(**params)

            # Phase 14: Emit tool complete event
            if self._bus and self._run_id:
                from kabot.bus.events import SystemEvent
                seq = self._bus.get_next_seq(self._run_id)
                await self._bus.emit_system_event(
                    SystemEvent.tool(self._run_id, seq, name, "complete", result_length=len(result))
                )

            return result

        except Exception as e:
            error_msg = f"Error executing {name}: {str(e)}"

            # Phase 14: Emit tool error event
            if self._bus and self._run_id:
                from kabot.bus.events import SystemEvent
                seq = self._bus.get_next_seq(self._run_id)
                await self._bus.emit_system_event(
                    SystemEvent.tool(self._run_id, seq, name, "error", error=str(e))
                )

            return error_msg

    @property
    def tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
