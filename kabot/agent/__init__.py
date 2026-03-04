"""Agent core module.

Keep package import lightweight. Heavy modules are resolved lazily so
`import kabot.agent.loop` does not pull unrelated startup dependencies.
"""

from typing import TYPE_CHECKING, Any

__all__ = ["AgentLoop", "ContextBuilder", "MemoryStore", "SkillsLoader"]

if TYPE_CHECKING:
    from kabot.agent.context import ContextBuilder
    from kabot.agent.loop import AgentLoop
    from kabot.agent.memory import MemoryStore
    from kabot.agent.skills import SkillsLoader


def __getattr__(name: str) -> Any:
    if name == "AgentLoop":
        from kabot.agent.loop import AgentLoop

        return AgentLoop
    if name == "ContextBuilder":
        from kabot.agent.context import ContextBuilder

        return ContextBuilder
    if name == "MemoryStore":
        from kabot.agent.memory import MemoryStore

        return MemoryStore
    if name == "SkillsLoader":
        from kabot.agent.skills import SkillsLoader

        return SkillsLoader
    raise AttributeError(f"module 'kabot.agent' has no attribute '{name}'")
