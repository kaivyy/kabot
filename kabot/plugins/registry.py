"""Plugin registry for managing loaded plugins."""

from dataclasses import dataclass


@dataclass
class Plugin:
    """Represents a loaded plugin."""
    name: str
    description: str
    path: str
    enabled: bool = True


class PluginRegistry:
    """Registry for managing plugins."""

    def __init__(self):
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin):
        """Register a plugin."""
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> Plugin | None:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def list_all(self) -> list[Plugin]:
        """List all registered plugins."""
        return list(self._plugins.values())

    def unregister(self, name: str) -> bool:
        """Unregister a plugin by name. Returns True if plugin was found."""
        if name in self._plugins:
            del self._plugins[name]
            return True
        return False
