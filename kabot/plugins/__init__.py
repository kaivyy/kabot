"""Chat plugins module with hooks and dynamic loading."""

from kabot.plugins.registry import PluginRegistry, Plugin
from kabot.plugins.hooks import HookManager, HookEvent
from kabot.plugins.loader import load_plugins, load_dynamic_plugins

__all__ = [
    "PluginRegistry", "Plugin",
    "HookManager", "HookEvent",
    "load_plugins", "load_dynamic_plugins",
]
