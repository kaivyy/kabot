"""Transcript guard helpers for tool-call/tool-result persistence."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from kabot.utils.text_safety import ensure_utf8_text

MAX_PERSISTED_TOOL_RESULT_CHARS = 20_000
MAX_PERSISTED_TOOL_RESULT_PREVIEW_CHARS = 4_000
TRUNCATION_SUFFIX = (
    "\n\n[tool result truncated during persistence; ask for a smaller section or use "
    "offset/limit when available]"
)


def _normalize_text(value: Any) -> str:
    return ensure_utf8_text(value).strip()


def _truncate_tool_result_text(value: Any, *, limit: int = MAX_PERSISTED_TOOL_RESULT_CHARS) -> str:
    text = ensure_utf8_text(value)
    if len(text) <= limit:
        return text
    keep = max(0, limit - len(TRUNCATION_SUFFIX))
    return text[:keep].rstrip() + TRUNCATION_SUFFIX


def normalize_assistant_tool_calls(tool_calls: list | None) -> list[dict[str, Any]] | None:
    """Drop malformed tool calls and keep only the fields required for replay."""
    if not isinstance(tool_calls, list):
        return None

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in tool_calls:
        if not isinstance(item, dict):
            continue
        raw_id = _normalize_text(item.get("id"))
        raw_name = _normalize_text(item.get("name"))
        raw_arguments = item.get("arguments")
        if not raw_id or not raw_name:
            continue
        if raw_id in seen_ids:
            continue
        seen_ids.add(raw_id)
        normalized.append(
            {
                "id": raw_id,
                "name": raw_name,
                "arguments": raw_arguments if isinstance(raw_arguments, dict) else {},
            }
        )
    return normalized or None


def normalize_tool_results_payload(tool_results: list | None) -> list[dict[str, Any]] | None:
    """Normalize persisted tool-result metadata for history replay."""
    if not isinstance(tool_results, list):
        return None

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in tool_results:
        if not isinstance(item, dict):
            continue
        raw_id = _normalize_text(item.get("tool_call_id"))
        raw_name = _normalize_text(item.get("name"))
        raw_result = _truncate_tool_result_text(
            item.get("result"),
            limit=MAX_PERSISTED_TOOL_RESULT_PREVIEW_CHARS,
        )
        if not raw_id:
            continue
        if raw_id in seen_ids:
            continue
        seen_ids.add(raw_id)
        normalized.append(
            {
                "tool_call_id": raw_id,
                "name": raw_name or "unknown",
                "result": raw_result,
            }
        )
    return normalized or None


def normalize_persisted_message(
    *,
    role: str,
    content: str,
    tool_calls: list | None = None,
    tool_results: list | None = None,
) -> tuple[str, list[dict[str, Any]] | None, list[dict[str, Any]] | None]:
    """Normalize persisted message content and tool metadata."""
    normalized_role = str(role or "").strip().lower()
    normalized_content = ensure_utf8_text(content)
    normalized_tool_calls = normalize_assistant_tool_calls(tool_calls)
    normalized_tool_results = normalize_tool_results_payload(tool_results)

    if normalized_role == "tool":
        normalized_content = _truncate_tool_result_text(normalized_content)
    return normalized_content, normalized_tool_calls, normalized_tool_results


def make_missing_tool_result(tool_call_id: str, tool_name: str) -> dict[str, Any]:
    """Create a synthetic tool-result transcript entry for orphaned tool calls."""
    missing_text = (
        "WARNING: Tool result was missing from persisted history for this earlier tool call. "
        "Treat the original tool action as incomplete and re-run or verify it before relying on it."
    )
    return {
        "message_id": f"synthetic-tool-result:{tool_call_id}",
        "session_id": "",
        "parent_id": None,
        "role": "tool",
        "content": missing_text,
        "message_type": "tool_result_repair",
        "tool_calls": None,
        "tool_results": [
            {
                "tool_call_id": tool_call_id,
                "name": tool_name or "unknown",
                "result": missing_text,
            }
        ],
        "metadata": {
            "synthetic_tool_result": True,
            "tool_name": tool_name or "unknown",
        },
    }


def repair_tool_result_pairs(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure chronological history never leaves assistant tool calls orphaned."""
    if not isinstance(messages, list) or not messages:
        return messages

    repaired: list[dict[str, Any]] = []
    pending: "OrderedDict[str, str]" = OrderedDict()

    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "").strip().lower()
        normalized_message = dict(message)

        if role != "tool" and pending:
            for tool_call_id, tool_name in pending.items():
                repaired.append(make_missing_tool_result(tool_call_id, tool_name))
            pending.clear()

        if role == "assistant":
            normalized_calls = normalize_assistant_tool_calls(message.get("tool_calls"))
            if normalized_calls:
                normalized_message["tool_calls"] = normalized_calls
                for item in normalized_calls:
                    pending[str(item.get("id"))] = str(item.get("name") or "unknown")

        if role == "tool":
            normalized_results = normalize_tool_results_payload(message.get("tool_results"))
            if normalized_results:
                normalized_message["tool_results"] = normalized_results
                for item in normalized_results:
                    pending.pop(str(item.get("tool_call_id") or ""), None)

        repaired.append(normalized_message)

    if not pending:
        return repaired

    for tool_call_id, tool_name in pending.items():
        repaired.append(make_missing_tool_result(tool_call_id, tool_name))
    return repaired
