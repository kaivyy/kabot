from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger
from kabot.agent.semantic_llm import call_semantic_llm_with_fallback

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
_ACTION_INTENTS = {
    "message",
    "list_dir",
    "read_file",
    "write_file",
    "find_files",
    "cleanup_system",
    "get_system_info",
    "get_process_memory",
    "server_monitor",
    "check_update",
    "system_update",
    "speedtest",
    "none",
}


def _normalize_action_intent(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _ACTION_INTENTS:
        return normalized
    return "none"


def _parse_action_intent_response(raw_response: Any) -> str:
    raw = _JSON_FENCE_RE.sub("", str(raw_response or "").strip()).strip()
    if not raw:
        return "none"
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        return _normalize_action_intent(
            parsed.get("action_intent") or parsed.get("tool") or parsed.get("intent")
        )
    match = re.search(
        r"\b(message|list_dir|read_file|write_file|find_files|cleanup_system|get_system_info|get_process_memory|server_monitor|check_update|system_update|speedtest|none)\b",
        raw,
        re.IGNORECASE,
    )
    return _normalize_action_intent(match.group(1) if match else "")


async def classify_stateful_action_intent(
    loop: Any,
    text: str,
    *,
    route_profile: str,
    turn_category: str,
    working_directory: str = "",
    pending_followup_tool: str = "",
    pending_followup_source: str = "",
    last_tool_context: dict[str, Any] | None = None,
    recent_history_file_path: str = "",
    explicit_file_path: str = "",
    resolved_delivery_path: str = "",
    resolved_list_dir_path: str = "",
) -> str:
    raw = str(text or "").strip()
    if not raw or raw.startswith("/"):
        return "none"

    provider = getattr(loop, "provider", None)
    chat = getattr(provider, "chat", None)
    if not callable(chat):
        return "none"

    model = (
        str(getattr(getattr(loop, "router", None), "model", "") or "").strip()
        or str(getattr(loop, "model", "") or "").strip()
    )
    if not model and hasattr(provider, "get_default_model"):
        try:
            model = str(provider.get_default_model() or "").strip()
        except Exception:
            model = ""

    last_tool_name = str((last_tool_context or {}).get("tool") or "").strip()
    last_tool_path = str((last_tool_context or {}).get("path") or "").strip()

    prompt = f"""Classify the user's primary filesystem or delivery action intent.

Return ONLY one JSON object:
{{"action_intent":"message|list_dir|read_file|write_file|find_files|cleanup_system|get_system_info|get_process_memory|server_monitor|check_update|system_update|speedtest|none"}}

Use semantics, not keyword spotting.

Choose:
- message: the user is asking to send/share/attach the active file or a file resolved from current directory context.
- list_dir: the user is continuing folder navigation or asking about directory contents relative to the active directory context.
- read_file: the user wants inspection/reading of a specific current file/artifact.
- write_file: the user wants to create or update a file artifact.
- find_files: the user wants to search for a file or folder before the next step.
- cleanup_system: the user wants cleanup/free-space/cache/temp optimization work done now.
- get_system_info: the user wants hardware, storage, disk-space, or system information.
- get_process_memory: the user wants process/RAM/memory usage inspection.
- server_monitor: the user wants runtime/server/uptime/resource health inspection.
- check_update: the user wants to check whether the app/bot has updates.
- system_update: the user wants to actually apply or install updates.
- speedtest: the user wants a network speed test.
- none: no grounded filesystem/delivery action is clear.

Route profile: {str(route_profile or '').strip().upper() or 'GENERAL'}
Turn category: {str(turn_category or '').strip().lower() or 'chat'}
Working directory: {str(working_directory or '').strip() or 'none'}
Pending follow-up tool: {str(pending_followup_tool or '').strip().lower() or 'none'}
Pending follow-up source:
\"\"\"{str(pending_followup_source or '')[:800]}\"\"\"
Last tool name: {last_tool_name or 'none'}
Last tool path: {last_tool_path or 'none'}
Recent history file path: {str(recent_history_file_path or '').strip() or 'none'}
Explicit file path candidate: {str(explicit_file_path or '').strip() or 'none'}
Resolved delivery path candidate: {str(resolved_delivery_path or '').strip() or 'none'}
Resolved directory path candidate: {str(resolved_list_dir_path or '').strip() or 'none'}
Available tools: {", ".join(sorted(str(name) for name in getattr(getattr(loop, "tools", None), "tool_names", []) or [])) or 'unknown'}
User message:
\"\"\"{raw[:1200]}\"\"\""""

    response = await call_semantic_llm_with_fallback(
        loop=loop,
        provider=provider,
        messages=[{"role": "user", "content": prompt}],
        primary_model=model,
        max_tokens=100,
        temperature=0.0,
    )
    if response is None:
        logger.debug("Stateful action semantic classification failed across fallback chain")
        return "none"

    return _parse_action_intent_response(getattr(response, "content", ""))


__all__ = ["classify_stateful_action_intent"]
