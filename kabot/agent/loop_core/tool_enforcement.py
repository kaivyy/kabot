"""Public tool-enforcement facade with compatibility exports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kabot.agent.loop_core.tool_enforcement_parts import action_requests as _action_requests
from kabot.agent.loop_core.tool_enforcement_parts import core as _tool_enforcement_core
from kabot.agent.loop_core.tool_enforcement_parts import filesystem_paths as _filesystem_paths
from kabot.agent.loop_core.tool_enforcement_parts.common import (
    _is_low_information_followup,
    _looks_like_verbose_non_query_text,
    _normalize_text,
)
from kabot.agent.loop_core.tool_enforcement_parts.core import (
    _FILESYSTEM_TARGET_MARKERS as _CORE_FILESYSTEM_TARGET_MARKERS,
    _RELATIVE_DIRECTORY_QUERY_RE as _CORE_RELATIVE_DIRECTORY_QUERY_RE,
    _RELATIVE_DIRECTORY_SUFFIX_RE as _CORE_RELATIVE_DIRECTORY_SUFFIX_RE,
    _SPECIAL_DIR_SUBFOLDER_PATTERNS as _CORE_SPECIAL_DIR_SUBFOLDER_PATTERNS,
    _compact_web_search_query,
    _extract_explicit_mcp_tool_arguments,
    _extract_stock_analysis_days,
    _format_update_tool_output,
    _looks_like_stock_idr_conversion_query,
    _looks_like_stock_tracking_query,
    _parse_mcp_argument_value,
    build_group_id_for_loop,
    existing_schedule_titles,
    infer_required_tool_from_history_for_loop,
    make_unique_schedule_title_for_loop,
    required_tool_for_query_for_loop,
)
from kabot.bus.events import InboundMessage

_ACTION_EXTRACT_MESSAGE_DELIVERY_PATH = _action_requests._extract_message_delivery_path
_ACTION_INFER_ACTION_REQUIRED_TOOL_FOR_LOOP = _action_requests.infer_action_required_tool_for_loop
_ACTION_LOOKS_LIKE_WRITE_FILE_REQUEST = _action_requests._looks_like_write_file_request
_ACTION_RESOLVE_FIND_FILES_ROOT = _action_requests._resolve_find_files_root
_CORE_QUERY_HAS_TOOL_PAYLOAD = _tool_enforcement_core._query_has_tool_payload

__all__ = [
    "_extract_list_dir_limit",
    "_extract_list_dir_path",
    "_extract_message_delivery_path",
    "_extract_read_file_path",
    "_query_has_tool_payload",
    "execute_required_tool_fallback",
    "infer_action_required_tool_for_loop",
    "required_tool_for_query_for_loop",
    "infer_required_tool_from_history_for_loop",
    "existing_schedule_titles",
    "make_unique_schedule_title_for_loop",
    "build_group_id_for_loop",
]

# Keep the canonical multilingual regexes/markers visible from the facade.
_FILESYSTEM_TARGET_MARKERS = _CORE_FILESYSTEM_TARGET_MARKERS
_RELATIVE_DIRECTORY_QUERY_RE = _CORE_RELATIVE_DIRECTORY_QUERY_RE
_RELATIVE_DIRECTORY_SUFFIX_RE = _CORE_RELATIVE_DIRECTORY_SUFFIX_RE
_SPECIAL_DIR_SUBFOLDER_PATTERNS = _CORE_SPECIAL_DIR_SUBFOLDER_PATTERNS

# Re-export stable pure helpers directly from extracted parts.
_extract_list_dir_limit = _filesystem_paths._extract_list_dir_limit


def _filesystem_home_dir() -> Path:
    return Path.home()


def _sync_filesystem_globals() -> None:
    _filesystem_paths._filesystem_home_dir = _filesystem_home_dir
    _filesystem_paths.Path = Path


def _sync_action_globals() -> None:
    _sync_filesystem_globals()
    _action_requests._extract_list_dir_path = _extract_list_dir_path
    _action_requests._extract_read_file_path = _extract_read_file_path
    _action_requests._resolve_special_directory_path = _resolve_special_directory_path
    _action_requests._resolve_find_files_root = _resolve_find_files_root
    _action_requests._resolve_delivery_path = _resolve_delivery_path


def _sync_core_globals() -> None:
    _sync_action_globals()
    _tool_enforcement_core.Path = Path
    _tool_enforcement_core._filesystem_home_dir = _filesystem_home_dir
    _tool_enforcement_core._extract_list_dir_path = _extract_list_dir_path
    _tool_enforcement_core._extract_read_file_path = _extract_read_file_path
    _tool_enforcement_core._resolve_special_directory_path = _resolve_special_directory_path
    _tool_enforcement_core._resolve_find_files_root = _resolve_find_files_root
    _tool_enforcement_core._resolve_delivery_path = _resolve_delivery_path
    _tool_enforcement_core._extract_message_delivery_path = _extract_message_delivery_path
    _tool_enforcement_core._looks_like_write_file_request = _looks_like_write_file_request
    _tool_enforcement_core.infer_action_required_tool_for_loop = infer_action_required_tool_for_loop
    _tool_enforcement_core.required_tool_for_query_for_loop = required_tool_for_query_for_loop
    _tool_enforcement_core.existing_schedule_titles = existing_schedule_titles
    _tool_enforcement_core.make_unique_schedule_title_for_loop = make_unique_schedule_title_for_loop
    _tool_enforcement_core.build_group_id_for_loop = build_group_id_for_loop
    _tool_enforcement_core._normalize_text = _normalize_text
    _tool_enforcement_core._is_low_information_followup = _is_low_information_followup
    _tool_enforcement_core._looks_like_verbose_non_query_text = _looks_like_verbose_non_query_text
    _tool_enforcement_core._query_has_tool_payload = _query_has_tool_payload



def _resolve_special_directory_path(text: str) -> str | None:
    _sync_filesystem_globals()
    return _filesystem_paths._resolve_special_directory_path(text)



def _extract_read_file_path(text: str) -> str | None:
    _sync_filesystem_globals()
    return _filesystem_paths._extract_read_file_path(text)



def _extract_list_dir_path(text: str, *, last_tool_context: dict[str, Any] | None = None) -> str | None:
    _sync_filesystem_globals()
    return _filesystem_paths._extract_list_dir_path(text, last_tool_context=last_tool_context)



def _resolve_find_files_root(
    loop: Any,
    text: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    _sync_action_globals()
    return _ACTION_RESOLVE_FIND_FILES_ROOT(loop, text, metadata=metadata)



def _resolve_delivery_path(loop: Any, path: str) -> Path:
    _sync_filesystem_globals()
    return _filesystem_paths._resolve_delivery_path(loop, path)



def _extract_message_delivery_path(
    text: str,
    *,
    last_tool_context: dict[str, Any] | None = None,
) -> str | None:
    _sync_action_globals()
    return _ACTION_EXTRACT_MESSAGE_DELIVERY_PATH(text, last_tool_context=last_tool_context)



def _looks_like_write_file_request(text: str, *, explicit_path: str | None = None) -> bool:
    _sync_action_globals()
    return _ACTION_LOOKS_LIKE_WRITE_FILE_REQUEST(text, explicit_path=explicit_path)



def infer_action_required_tool_for_loop(
    loop: Any,
    text: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    _sync_action_globals()
    return _ACTION_INFER_ACTION_REQUIRED_TOOL_FOR_LOOP(loop, text, metadata=metadata)



def _query_has_tool_payload(tool_name: str, text: str) -> bool:
    _sync_core_globals()
    return _CORE_QUERY_HAS_TOOL_PAYLOAD(tool_name, text)


async def execute_required_tool_fallback(loop: Any, required_tool: str, msg: InboundMessage) -> str | None:
    _sync_core_globals()
    return await _tool_enforcement_core.execute_required_tool_fallback(loop, required_tool, msg)
