"""Compatibility helpers extracted from kabot.agent.loop."""

from typing import Any


def lazy_compat_getattr(name: str) -> Any:
    """Lazy compatibility exports for legacy module consumers."""
    if name == "ContextBuilder":
        from kabot.agent.context import ContextBuilder

        return ContextBuilder
    if name == "HybridMemoryManager":
        from kabot.memory import HybridMemoryManager

        return HybridMemoryManager
    if name == "IntentRouter":
        from kabot.agent.router import IntentRouter

        return IntentRouter
    if name == "SubagentManager":
        from kabot.agent.subagent import SubagentManager

        return SubagentManager
    raise AttributeError(f"module 'kabot.agent.loop' has no attribute '{name}'")

