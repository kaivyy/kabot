"""Public execution runtime facade with compatibility exports."""

from __future__ import annotations

from typing import Any

from loguru import logger

from kabot.agent.fallback_i18n import t
from kabot.agent.loop_core.execution_runtime_parts import agent_loop as _agent_loop
from kabot.agent.loop_core.execution_runtime_parts import helpers as _helpers
from kabot.agent.loop_core.execution_runtime_parts import progress as _progress
from kabot.agent.loop_core.execution_runtime_parts import tool_processing as _tool_processing
from kabot.agent.loop_core.execution_runtime_parts.llm import (
    call_llm_with_fallback,
    format_tool_result,
    run_simple_response,
)
from kabot.bus.events import InboundMessage

for _name in dir(_helpers):
    if _name.startswith("_"):
        globals()[_name] = getattr(_helpers, _name)

__all__ = [
    "format_tool_result",
    "call_llm_with_fallback",
    "run_agent_loop",
    "run_simple_response",
    "_apply_response_quota_usage",
    "_resolve_expected_tool_for_query",
    "_sanitize_error",
]


def _sync_agent_loop_globals() -> None:
    _agent_loop.t = t
    _agent_loop.logger = logger
    _progress.t = t
    _progress.logger = logger
    _tool_processing.t = t
    _tool_processing.logger = logger


async def run_agent_loop(loop: Any, msg: InboundMessage, messages: list, session: Any) -> str | None:
    _sync_agent_loop_globals()
    return await _agent_loop.run_agent_loop(loop, msg, messages, session)


async def process_tool_calls(loop: Any, msg: InboundMessage, messages: list, response: Any, session: Any) -> list:
    _sync_agent_loop_globals()
    return await _agent_loop.process_tool_calls(loop, msg, messages, response, session)
