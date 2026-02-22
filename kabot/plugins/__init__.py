"""Chat plugins module with hooks and dynamic loading."""

from kabot.plugins.hooks import HookEvent, HookManager
from kabot.plugins.loader import load_dynamic_plugins, load_plugins
from kabot.plugins.manager import PluginManager
from kabot.plugins.registry import Plugin, PluginRegistry
from kabot.plugins.scaffold import scaffold_plugin

__all__ = [
    "PluginRegistry", "Plugin",
    "HookManager", "HookEvent",
    "load_plugins", "load_dynamic_plugins",
    "PluginManager",
    "scaffold_plugin",
]
