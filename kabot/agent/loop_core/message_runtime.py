"""Public message runtime facade with compatibility exports."""

from __future__ import annotations

import time
from typing import Any

from loguru import logger

from kabot.agent.cron_fallback_nlp import extract_weather_location
from kabot.agent.fallback_i18n import t
from kabot.agent.loop_core import message_runtime_parts as _message_runtime_parts_pkg
from kabot.agent.loop_core.message_runtime_parts import continuity_runtime as _continuity_runtime
from kabot.agent.loop_core.message_runtime_parts import helpers as _helpers
from kabot.agent.loop_core.message_runtime_parts import process_flow as _process_flow
from kabot.agent.loop_core.message_runtime_parts import response_runtime as _response_runtime
from kabot.agent.loop_core.message_runtime_parts.tail import (
    process_isolated,
    process_pending_exec_approval,
    process_system_message,
)
from kabot.agent.loop_core.message_runtime_parts.temporal import build_temporal_fast_reply
from kabot.agent.loop_core.tool_enforcement import (
    _extract_list_dir_path,
    _extract_read_file_path,
    _query_has_tool_payload,
    infer_action_required_tool_for_loop,
)
from kabot.bus.events import InboundMessage, OutboundMessage

# Preserve helper-style module access used by tests and runtime proxy helpers.
for _name in dir(_helpers):
    if _name.startswith("_"):
        globals()[_name] = getattr(_helpers, _name)

_looks_like_brief_answer_request = _process_flow._looks_like_brief_answer_request
_select_answer_reference_target = _process_flow._select_answer_reference_target
_looks_like_meaning_followup = _process_flow._looks_like_meaning_followup
_format_grounded_target_reply = _process_flow._format_grounded_target_reply
_build_answer_reference_fast_reply = _process_flow._build_answer_reference_fast_reply
_resolve_turn_category = _process_flow._resolve_turn_category
_infer_required_tool_from_recent_user_intent = _process_flow._infer_required_tool_from_recent_user_intent
_extract_reusable_last_tool_execution = _process_flow._extract_reusable_last_tool_execution

__all__ = [
    "_extract_assistant_followup_offer_text",
    "_extract_option_selection_reference",
    "_infer_recent_assistant_answer_from_history",
    "_infer_recent_assistant_option_prompt_from_history",
    "_extract_user_supplied_option_prompt_text",
    "_is_low_information_turn",
    "_looks_like_answer_reference_followup",
    "_normalize_text",
    "_resolve_runtime_locale",
    "build_temporal_fast_reply",
    "extract_weather_location",
    "process_isolated",
    "process_message",
    "process_pending_exec_approval",
    "process_system_message",
]


def _sync_process_flow_globals() -> None:
    _process_flow.t = t
    _process_flow.time = time
    _process_flow.logger = logger
    _process_flow.extract_weather_location = extract_weather_location
    _process_flow.build_temporal_fast_reply = build_temporal_fast_reply
    _process_flow._KEEPALIVE_INITIAL_DELAY_SECONDS = _KEEPALIVE_INITIAL_DELAY_SECONDS
    _process_flow._KEEPALIVE_INTERVAL_SECONDS = _KEEPALIVE_INTERVAL_SECONDS
    _response_runtime.t = t
    _response_runtime.time = time
    _response_runtime.logger = logger
    _response_runtime.build_temporal_fast_reply = build_temporal_fast_reply
    _response_runtime._KEEPALIVE_INITIAL_DELAY_SECONDS = _KEEPALIVE_INITIAL_DELAY_SECONDS
    _response_runtime._KEEPALIVE_INTERVAL_SECONDS = _KEEPALIVE_INTERVAL_SECONDS
    _continuity_runtime.logger = logger


async def process_message(loop: Any, msg: InboundMessage) -> OutboundMessage | None:
    _sync_process_flow_globals()
    return await _process_flow.process_message(loop, msg)
