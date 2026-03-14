"""Tool-enforcement and deterministic fallback logic for AgentLoop."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kabot.agent.cron_fallback_nlp import (
    CRON_MANAGEMENT_OPS,
    CRON_MANAGEMENT_TERMS,
    extract_cycle_schedule,
    extract_explicit_schedule_title,
    extract_new_schedule_title,
    extract_recurring_schedule,
    extract_reminder_message,
    extract_weather_location,
)
from kabot.agent.cron_fallback_nlp import build_cycle_title as nlp_build_cycle_title
from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.loop_core.tool_enforcement_parts.action_requests import (
    _extract_find_files_query,
    _extract_message_delivery_path,
    _extract_write_file_content,
    _looks_like_find_files_request,
    _looks_like_media_action_request,
    _looks_like_message_send_file_request,
    _looks_like_write_file_request,
    _tool_name_available,
    infer_action_required_tool_for_loop,
)
from kabot.agent.loop_core.tool_enforcement_parts.common import (
    _is_low_information_followup,
    _looks_like_verbose_non_query_text,
    _normalize_text,
)
from kabot.agent.loop_core.tool_enforcement_parts.fallback_support import (
    _compact_web_search_query,
    _extract_explicit_mcp_tool_arguments,
    _extract_stock_analysis_days,
    _format_update_tool_output,
    _looks_like_stock_idr_conversion_query,
    _looks_like_stock_tracking_query,
    _parse_mcp_argument_value,
)
from kabot.agent.loop_core.tool_enforcement_parts.filesystem_paths import (
    _FILELIKE_QUERY_RE,
    _FILESYSTEM_TARGET_MARKERS,
    _PATHLIKE_QUERY_RE,
    _RELATIVE_DIRECTORY_QUERY_RE,
    _RELATIVE_DIRECTORY_SUFFIX_RE,
    _SPECIAL_DIR_SUBFOLDER_PATTERNS,
    _extract_list_dir_limit,
    _extract_list_dir_path,
    _extract_read_file_path,
    _extract_explicit_path_candidate,
    _extract_relative_directory_candidate,
    _filesystem_home_dir,
    _resolve_delivery_path,
    _resolve_find_files_root,
    _resolve_special_directory_path,
)
from kabot.agent.loop_core.tool_enforcement_parts.history_routing import (
    build_group_id_for_loop,
    existing_schedule_titles,
    infer_required_tool_from_history_for_loop,
    make_unique_schedule_title_for_loop,
    required_tool_for_query_for_loop,
)
from kabot.agent.loop_core.message_runtime_parts.user_profile import (
    infer_user_profile_updates,
)
from kabot.agent.tools.stock import (
    extract_crypto_ids,
    extract_stock_name_candidates,
    extract_stock_symbols,
)
from kabot.agent.tools.weather import infer_weather_request_profile
from kabot.bus.events import InboundMessage


_NON_MARKET_DOTTED_SUFFIXES = {
    "MD",
    "TXT",
    "JSON",
    "YAML",
    "YML",
    "TOML",
    "CSV",
    "LOG",
    "PDF",
    "DOC",
    "DOCX",
    "XLS",
    "XLSX",
    "PY",
    "JS",
    "TS",
    "TSX",
    "JSX",
    "HTML",
    "CSS",
    "XML",
    "INI",
    "CFG",
    "CONF",
    "ENV",
}


def _extract_structural_stock_symbols(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []

    result: list[str] = []
    seen: set[str] = set()
    tokens = [token for token in re.split(r"[\s,]+", text) if token]
    for token_raw in tokens:
        token = token_raw.strip().strip("()[]{}\"'`")
        token = token.strip(".,;:!?")
        if not token:
            continue
        upper = token.upper()
        if upper.endswith("=X") and re.fullmatch(r"[A-Z]{3,10}=X", upper):
            if upper not in seen:
                seen.add(upper)
                result.append(upper)
            continue
        if upper.startswith("^") and re.fullmatch(r"\^[A-Z]{2,8}", upper):
            if upper not in seen:
                seen.add(upper)
                result.append(upper)
            continue
        if "." in upper and re.fullmatch(r"[A-Z0-9]{1,10}\.[A-Z]{1,5}", upper):
            _left, right = upper.split(".", 1)
            if right in _NON_MARKET_DOTTED_SUFFIXES:
                continue
            if upper not in seen:
                seen.add(upper)
                result.append(upper)
            continue
        if token == token.upper() and re.fullmatch(r"[A-Z]{2,8}", upper):
            if upper not in seen:
                seen.add(upper)
                result.append(upper)
    return result


def _has_explicit_stock_symbol_payload(raw: str) -> bool:
    text = str(raw or "").strip()
    if not text:
        return False

    explicit_tokens: set[str] = set()
    for token_raw in re.split(r"[\s,]+", text):
        token = token_raw.strip().strip("()[]{}\"'`")
        token = token.strip(".,;:!?")
        if not token:
            continue
        explicit_tokens.add(token.upper())

    for symbol in extract_stock_symbols(text):
        normalized = str(symbol or "").strip().upper()
        if not normalized:
            continue
        if normalized in explicit_tokens:
            return True
        root = normalized.split(".", 1)[0]
        if root.endswith("=X"):
            root = root[:-2]
        if root and root in explicit_tokens:
            return True
    return False


def _query_has_tool_payload(tool_name: str, text: str) -> bool:
    """Check whether raw user text carries explicit payload for a required tool."""
    raw = str(text or "").strip()
    if not raw:
        return False
    tool = str(tool_name or "").strip().lower()
    if tool in {"stock", "stock_analysis"}:
        return bool(_extract_structural_stock_symbols(raw)) or _has_explicit_stock_symbol_payload(raw)
    if tool == "crypto":
        return bool(extract_crypto_ids(raw))
    if tool == "weather":
        return bool(extract_weather_location(raw))
    if tool == "read_file":
        return bool(_extract_read_file_path(raw))
    if tool == "write_file":
        return bool(_extract_read_file_path(raw) and _looks_like_write_file_request(raw))
    if tool == "list_dir":
        return bool(_extract_list_dir_path(raw) or _extract_relative_directory_candidate(raw))
    if tool == "image_gen":
        return bool(_looks_like_media_action_request(raw, kind="image"))
    if tool == "message":
        explicit = _extract_read_file_path(raw)
        if explicit and _looks_like_message_send_file_request(raw, explicit_path=explicit):
            return True
        return False
    return False


def _get_session_metadata(loop: Any, msg: InboundMessage) -> dict[str, Any] | None:
    try:
        session = loop.sessions.get_or_create(msg.session_key)
    except Exception:
        return None
    session_meta = getattr(session, "metadata", None)
    if not isinstance(session_meta, dict):
        return None
    return session_meta


def _normalize_working_directory_path(path_value: str) -> str | None:
    raw = str(path_value or "").strip()
    if not raw:
        return None
    try:
        resolved = Path(raw).expanduser().resolve()
    except Exception:
        return None
    if not resolved.exists():
        return None
    if resolved.is_file():
        resolved = resolved.parent
    if not resolved.is_dir():
        return None
    return str(resolved)


def _set_working_directory(
    loop: Any,
    msg: InboundMessage,
    metadata: dict[str, Any],
    path_value: str,
) -> str | None:
    normalized = _normalize_working_directory_path(path_value)
    if not normalized:
        return None
    metadata["working_directory"] = normalized
    session_meta = _get_session_metadata(loop, msg)
    if isinstance(session_meta, dict):
        session_meta["working_directory"] = normalized
    return normalized


def _get_working_directory(loop: Any, msg: InboundMessage, metadata: dict[str, Any]) -> str:
    session_meta = _get_session_metadata(loop, msg)
    if isinstance(session_meta, dict):
        session_working_directory = str(session_meta.get("working_directory") or "").strip()
        if session_working_directory:
            return session_working_directory
    direct = str(metadata.get("working_directory") or "").strip()
    if direct:
        return direct
    return ""


def _set_last_navigated_path(loop: Any, msg: InboundMessage, metadata: dict[str, Any], path_value: str) -> str | None:
    raw = str(path_value or "").strip()
    if not raw:
        return None
    try:
        resolved = Path(raw).expanduser().resolve()
    except Exception:
        return None
    if not resolved.exists() or not resolved.is_dir():
        return None
    normalized = str(resolved)
    metadata.pop("last_navigated_path", None)
    session_meta = _get_session_metadata(loop, msg)
    if isinstance(session_meta, dict):
        session_meta.pop("last_navigated_path", None)
    _set_working_directory(loop, msg, metadata, normalized)
    return normalized


def _get_last_navigated_path(loop: Any, msg: InboundMessage, metadata: dict[str, Any]) -> str:
    working_directory = _get_working_directory(loop, msg, metadata)
    if working_directory:
        return working_directory
    session_meta = _get_session_metadata(loop, msg)
    if isinstance(session_meta, dict):
        session_working_directory = str(session_meta.get("working_directory") or "").strip()
        if session_working_directory:
            return session_working_directory
        session_last_nav = str(session_meta.get("last_navigated_path") or "").strip()
        if session_last_nav:
            return session_last_nav
    direct = str(metadata.get("last_navigated_path") or "").strip()
    if direct:
        return direct
    return ""


def _looks_like_internal_temp_path(candidate: Path) -> bool:
    try:
        parts = {str(part).lower() for part in candidate.parts}
    except Exception:
        return False
    internal_markers = {
        ".basetemp",
        ".tmp",
        ".tmp-tests-json-storage",
        ".pytest_cache",
        "__pycache__",
    }
    return bool(parts.intersection(internal_markers))


def _get_last_delivery_path(loop: Any, msg: InboundMessage, metadata: dict[str, Any]) -> str:
    session_meta = _get_session_metadata(loop, msg)
    if isinstance(session_meta, dict):
        session_delivery = str(session_meta.get("last_delivery_path") or "").strip()
        if session_delivery:
            return session_delivery
    direct = str(metadata.get("last_delivery_path") or "").strip()
    if direct:
        return direct
    return ""


def _set_last_delivery_path(loop: Any, msg: InboundMessage, metadata: dict[str, Any], path_value: str) -> str | None:
    raw = str(path_value or "").strip()
    if not raw:
        return None
    try:
        resolved = Path(raw).expanduser().resolve()
    except Exception:
        return None
    if not resolved.exists() or not resolved.is_file():
        return None
    normalized = str(resolved)
    metadata.pop("last_delivery_path", None)
    session_meta = _get_session_metadata(loop, msg)
    if isinstance(session_meta, dict):
        session_meta["last_delivery_path"] = normalized
    _set_working_directory(loop, msg, metadata, str(resolved.parent))
    return normalized


async def execute_required_tool_fallback(loop: Any, required_tool: str, msg: InboundMessage) -> str | None:
    """Deterministic fallback when model skips required tools repeatedly."""
    metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
    resolved_query = str(metadata.get("required_tool_query") or "").strip()
    raw_text = str(msg.content or "").strip()
    source_text = resolved_query or raw_text
    stale_metadata_dropped = False
    execute_tool = getattr(loop, "_execute_tool", None)

    async def _exec_tool(name: str, payload: dict[str, Any]) -> Any:
        if callable(execute_tool):
            return await execute_tool(name, payload, session_key=msg.session_key)
        return await loop.tools.execute(name, payload)

    def _seed_pending_send_file_followup(intent_text: str) -> None:
        normalized_intent = str(intent_text or "").strip()
        if not normalized_intent:
            return
        try:
            session = loop.sessions.get_or_create(msg.session_key)
        except Exception:
            return
        try:
            from kabot.agent.loop_core.message_runtime_parts.followup import (
                _set_pending_followup_intent,
            )
        except Exception:
            return
        _set_pending_followup_intent(
            session,
            normalized_intent,
            "GENERAL",
            time.time(),
            kind="assistant_committed_action",
            request_text=normalized_intent,
        )

    # Prefer fresh raw user intent when it clearly maps to the same required tool.
    # This protects against stale carried metadata when users switch tasks quickly.
    if resolved_query and raw_text:
        try:
            raw_required_tool = required_tool_for_query_for_loop(loop, raw_text)
        except Exception:
            raw_required_tool = None
        if raw_required_tool == required_tool:
            raw_has_payload = _query_has_tool_payload(required_tool, raw_text)
            resolved_has_payload = _query_has_tool_payload(required_tool, source_text)
            if raw_has_payload or not resolved_has_payload:
                source_text = raw_text

    # Generic stale-metadata guard for short follow-up turns.
    # Example: user sends "iya/ok/gas", but metadata accidentally carries a long
    # assistant paragraph from the previous turn.
    if (
        resolved_query
        and raw_text
        and _is_low_information_followup(raw_text)
        and _looks_like_verbose_non_query_text(resolved_query)
    ):
        source_text = raw_text
        stale_metadata_dropped = True

    # If user sends a short follow-up that contains a concrete tool payload
    # (e.g., "adaro mana", "ethereum berapa", "cuaca di 東京"), prefer it over
    # stale carried query metadata.
    if resolved_query and raw_text and _query_has_tool_payload(required_tool, raw_text):
        source_text = raw_text

    if required_tool == "web_search":
        query = _compact_web_search_query(source_text)
        if not query:
            return i18n_t("web_search.need_query", source_text)
        if stale_metadata_dropped:
            return i18n_t("web_search.need_topic", source_text)
        result = await _exec_tool(
            "web_search",
            {"query": query, "count": 5, "context_text": source_text},
        )
        return str(result)

    if required_tool == "list_dir":
        last_tool_context = metadata.get("last_tool_context") if isinstance(metadata.get("last_tool_context"), dict) else {}
        path = _extract_list_dir_path(source_text, last_tool_context=last_tool_context)
        if not path:
            return i18n_t("filesystem.need_path", source_text)
        payload: dict[str, Any] = {"path": path}
        limit = _extract_list_dir_limit(source_text)
        if limit is not None:
            payload["limit"] = limit

        resolved_list_dir = _resolve_delivery_path(loop, path)
        if resolved_list_dir.exists() and resolved_list_dir.is_dir() and isinstance(metadata, dict):
            _set_last_navigated_path(loop, msg, metadata, str(resolved_list_dir))

        result = await _exec_tool("list_dir", payload)
        return str(result)

    if required_tool == "find_files":
        query = _extract_find_files_query(source_text)
        if not query:
            return i18n_t("filesystem.need_query", source_text)
        payload: dict[str, Any] = {
            "query": query,
            "context_text": source_text,
        }
        root_path = _resolve_find_files_root(loop, source_text, metadata=metadata)
        if root_path:
            payload["path"] = root_path
        result = await _exec_tool("find_files", payload)
        return str(result)

    if required_tool == "read_file":
        path = _extract_read_file_path(source_text)
        if not path:
            path = str(metadata.get("file_analysis_path") or "").strip()
        if not path:
            last_tool_context = (
                metadata.get("last_tool_context")
                if isinstance(metadata.get("last_tool_context"), dict)
                else {}
            )
            path = str(last_tool_context.get("path") or "").strip()
        if not path:
            return i18n_t("filesystem.need_path", source_text)

        resolved_path = _resolve_delivery_path(loop, path)
        if resolved_path.exists() and resolved_path.is_dir() and _tool_name_available(loop, "list_dir"):
            payload: dict[str, Any] = {"path": str(resolved_path)}
            limit = _extract_list_dir_limit(source_text)
            if limit is not None:
                payload["limit"] = limit
            if isinstance(metadata, dict):
                _set_last_navigated_path(loop, msg, metadata, str(resolved_path))
            result = await _exec_tool("list_dir", payload)
            return str(result)

        result = await _exec_tool("read_file", {"path": path})
        return str(result)

    if required_tool == "write_file":
        path = _extract_read_file_path(source_text)
        if not path:
            return i18n_t("filesystem.need_path", source_text)
        content = _extract_write_file_content(source_text)
        if not content:
            return None
        result = await _exec_tool("write_file", {"path": path, "content": content})
        return str(result)

    if required_tool == "save_memory":
        inferred_profile = infer_user_profile_updates(source_text)
        address = str(inferred_profile.get("address") or "").strip()
        self_identity_answer = str(inferred_profile.get("self_identity_answer") or "").strip()
        if self_identity_answer:
            content = f'If the user asks "who am I?", answer: {self_identity_answer}.'
            category = "preference"
        elif address:
            content = f"User prefers to be called {address}."
            category = "preference"
        else:
            content = source_text
            category = "fact"
        result = await _exec_tool(
            "save_memory",
            {"content": content, "category": category},
        )
        return str(result)

    if required_tool == "archive_path":
        path = _extract_read_file_path(source_text)
        if not path:
            last_tool_context = (
                metadata.get("last_tool_context")
                if isinstance(metadata.get("last_tool_context"), dict)
                else {}
            )
            path = str(last_tool_context.get("path") or "").strip()
        if not path:
            return i18n_t("filesystem.need_path", source_text)
        result = await _exec_tool("archive_path", {"path": path})
        return str(result)

    if required_tool == "message":
        last_tool_context = (
            metadata.get("last_tool_context")
            if isinstance(metadata.get("last_tool_context"), dict)
            else {}
        )
        requested_file = _extract_read_file_path(source_text)
        path = _extract_message_delivery_path(
            source_text,
            last_tool_context=last_tool_context,
        )

        normalized_source = _normalize_text(source_text)
        has_send_verb = bool(re.search(r"(?i)\b(kirim|send|share|attach|lampirkan|upload)\b", source_text))
        has_explicit_target = bool(_FILELIKE_QUERY_RE.search(source_text) or _PATHLIKE_QUERY_RE.search(source_text))
        send_without_target = bool(has_send_verb and not has_explicit_target)

        last_delivery_path = _get_last_delivery_path(loop, msg, metadata)
        if send_without_target and last_delivery_path:
            path = last_delivery_path

        if not path:
            if _looks_like_message_send_file_request(
                source_text,
                explicit_path=requested_file,
            ):
                _seed_pending_send_file_followup(source_text)
            return i18n_t("filesystem.need_path", source_text)
        if not requested_file and send_without_target and last_delivery_path:
            requested_file = Path(last_delivery_path).name

        resolved_path = _resolve_delivery_path(loop, path)
        if requested_file:
            try:
                resolved_candidate = resolved_path.expanduser().resolve()
            except Exception:
                resolved_candidate = resolved_path
            if (
                (
                    (resolved_candidate.exists() and resolved_candidate.is_dir())
                    or not resolved_candidate.suffix
                )
                and not re.match(r"(?i)^(?:[a-z]:[\\/]|\\\\|/|~[\\/])", requested_file)
                and "/" not in requested_file
                and "\\" not in requested_file
            ):
                candidate = (resolved_candidate / str(requested_file)).resolve()
                if candidate.exists() and candidate.is_file():
                    resolved_path = candidate
                    path = str(candidate)

        is_bare_file_request = bool(
            requested_file
            and not re.match(r"(?i)^(?:[a-z]:[\\/]|\\\\|/|~[\\/])", requested_file)
            and "/" not in requested_file
            and "\\" not in requested_file
        )
        working_directory = _get_working_directory(loop, msg, metadata)
        navigation_hint = working_directory or _get_last_navigated_path(loop, msg, metadata)
        nav_base: Path | None = None
        if navigation_hint and is_bare_file_request:
            try:
                nav_base = Path(navigation_hint).expanduser().resolve()
            except Exception:
                nav_base = None
            if nav_base is not None and not (nav_base.exists() and nav_base.is_dir()):
                nav_base = None

        # Prioritize active navigated folder for bare-filename sends, even when
        # stale fallback paths still exist (e.g. internal temp folders).
        if nav_base is not None and is_bare_file_request:
            candidate = (nav_base / str(requested_file)).resolve()
            if candidate.exists() and candidate.is_file():
                resolved_path = candidate
                path = str(candidate)
                _set_last_navigated_path(loop, msg, metadata, str(nav_base))

        # If we still point to an internal temp artifact outside the active
        # navigated folder, prefer a not-found response over sending stale files.
        if (
            nav_base is not None
            and is_bare_file_request
            and resolved_path.exists()
            and resolved_path.is_file()
            and _looks_like_internal_temp_path(resolved_path)
        ):
            try:
                outside_nav = not resolved_path.resolve().is_relative_to(nav_base)
            except Exception:
                outside_nav = True
            if outside_nav:
                resolved_path = Path("__missing__")
                path = str((nav_base / str(requested_file)).resolve())

        if not resolved_path.exists():
            if nav_base is not None and is_bare_file_request:
                candidate = (nav_base / str(requested_file)).resolve()
                if candidate.exists():
                    resolved_path = candidate
                    path = str(candidate)

        if not resolved_path.exists():
            return i18n_t("filesystem.file_not_found", path, path=path)
        if resolved_path.is_dir():
            if not _tool_name_available(loop, "archive_path"):
                return i18n_t("filesystem.not_file", path, path=path)
            archive_result = await _exec_tool("archive_path", {"path": str(resolved_path)})
            archive_result_text = str(archive_result or "").strip()
            archived_path = _extract_explicit_path_candidate(archive_result_text)
            if not archived_path:
                return archive_result_text or i18n_t("filesystem.not_file", path, path=path)
            resolved_path = _resolve_delivery_path(loop, archived_path)
            if not resolved_path.exists() or not resolved_path.is_file():
                return i18n_t("filesystem.file_not_found", archived_path, path=archived_path)
        elif not resolved_path.is_file():
            return i18n_t("filesystem.not_file", path, path=path)

        _set_last_navigated_path(loop, msg, metadata, str(resolved_path.parent))
        _set_last_delivery_path(loop, msg, metadata, str(resolved_path))

        result = await _exec_tool(
            "message",
            {
                "content": "Here is the requested file.",
                "files": [str(resolved_path)],
            },
        )
        return str(result)

    if required_tool == "image_gen":
        prompt = raw_text or source_text
        prompt = re.sub(r"(?i)^(?:tolong|please|mohon|bisa|could you)\s+", "", prompt).strip()
        prompt = re.sub(r"(?i)^(?:buat(?:kan)?|generate|create|render)\s+", "", prompt).strip()
        prompt = re.sub(
            r"(?i)\s+(?:dan|lalu|kemudian|then)\s+(?:simpan|save|kirim|send|attach|lampirkan|upload|export)\b.*$",
            "",
            prompt,
        ).strip(" .,:;")
        provider = None
        normalized_prompt = _normalize_text(source_text)
        if "imagen" in normalized_prompt or "gemini" in normalized_prompt:
            provider = "gemini"
        elif any(marker in normalized_prompt for marker in ("dall-e", "dalle", "openai")):
            provider = "openai"
        payload: dict[str, Any] = {"prompt": prompt or source_text}
        if provider:
            payload["provider"] = provider
        result = await _exec_tool("image_gen", payload)
        return str(result)

    if required_tool == "check_update":
        result = await _exec_tool("check_update", {})
        return _format_update_tool_output(required_tool, result, source_text)

    if required_tool == "system_update":
        result = await _exec_tool(
            "system_update",
            {"confirm_restart": False},
        )
        return _format_update_tool_output(required_tool, result, source_text)

    if required_tool == "weather":
        last_tool_context = metadata.get("last_tool_context") if isinstance(metadata.get("last_tool_context"), dict) else {}
        fallback_location = str(last_tool_context.get("location") or "").strip()
        explicit_location = extract_weather_location(source_text) if source_text else None
        short_weather_followup = bool(
            raw_text
            and len(str(raw_text).strip()) <= 24
            and re.search(r"(?i)(wind|angin|weather|cuaca)", str(raw_text))
        )
        if (
            raw_text
            and (_is_low_information_followup(raw_text) or short_weather_followup)
            and fallback_location
            and not explicit_location
        ):
            location = fallback_location
        else:
            location = explicit_location
            if not location and fallback_location:
                location = fallback_location
        if not location:
            return i18n_t("weather.need_location", source_text)
        resolved_mode, resolved_hours_start, resolved_hours_end = infer_weather_request_profile(
            source_text,
        )
        payload: dict[str, Any] = {"location": location, "context_text": source_text}
        if resolved_mode != "current":
            payload["mode"] = resolved_mode
        if resolved_hours_start is not None:
            payload["hours_ahead_start"] = resolved_hours_start
        if resolved_hours_end is not None:
            payload["hours_ahead_end"] = resolved_hours_end
        result = await _exec_tool(
            "weather",
            payload,
        )
        return str(result)

    if required_tool == "get_system_info":
        result = await _exec_tool("get_system_info", {})
        return str(result)

    if required_tool == "server_monitor":
        result = await _exec_tool("server_monitor", {})
        return str(result)

    if required_tool == "get_process_memory":
        q_lower = source_text.lower()
        limit = 15
        match = re.search(r"\b(\d{1,3})\b", q_lower)
        if match:
            try:
                limit = int(match.group(1))
            except Exception:
                limit = 15
        if limit < 1:
            limit = 1
        if limit > 200:
            limit = 200
        result = await _exec_tool(
            "get_process_memory",
            {"limit": limit},
        )
        return str(result)

    if required_tool == "speedtest":
        result = await _exec_tool("speedtest", {})
        return str(result)

    if required_tool == "stock_analysis":
        symbols = extract_stock_symbols(source_text)
        days = _extract_stock_analysis_days(source_text, default_days=30)
        days_payload = str(days)
        if symbols:
            result = await _exec_tool(
                "stock_analysis",
                {"symbol": symbols[0], "days": days_payload},
            )
            return str(result)
        name_candidates = extract_stock_name_candidates(source_text)
        if not name_candidates:
            return i18n_t("stock.need_symbol", source_text)
        result = await _exec_tool(
            "stock_analysis",
            {"symbol": source_text, "days": days_payload},
        )
        return str(result)

    # Built-in market tools stay available as a fallback path.
    # Skill-first precedence is decided earlier in routing/history helpers so
    # installed external finance skills can take the lead when relevant.
    if required_tool == "stock":
        # Guard against stale assistant-style metadata being reused as ticker query
        # when user only sends a short confirmation like "iya/ok/gas".
        raw_text_norm = _normalize_text(raw_text)
        if (
            resolved_query
            and raw_text_norm
            and _is_low_information_followup(raw_text)
            and len(resolved_query) > 80
        ):
            source_text = raw_text

        tracking_signal = _looks_like_stock_tracking_query(raw_text) or _looks_like_stock_tracking_query(source_text)
        if tracking_signal and loop.tools.has("stock_analysis"):
            combined_text = " ".join(part for part in (source_text, raw_text) if part).strip()
            analysis_symbols = extract_stock_symbols(combined_text)
            analysis_days = _extract_stock_analysis_days(raw_text or source_text, default_days=30)
            analysis_days_payload = str(analysis_days)
            if analysis_symbols:
                result = await _exec_tool(
                    "stock_analysis",
                    {"symbol": analysis_symbols[0], "days": analysis_days_payload},
                )
                return str(result)
            analysis_name_candidates = extract_stock_name_candidates(combined_text)
            if analysis_name_candidates:
                result = await _exec_tool(
                    "stock_analysis",
                    {"symbol": combined_text, "days": analysis_days_payload},
                )
                return str(result)

        combined_parts: list[str] = []
        seen_parts: set[str] = set()
        for part in (source_text, raw_text):
            normalized_part = str(part or "").strip()
            if not normalized_part:
                continue
            dedupe_key = normalized_part.lower()
            if dedupe_key in seen_parts:
                continue
            seen_parts.add(dedupe_key)
            combined_parts.append(normalized_part)
        combined_text = " ".join(combined_parts).strip()
        if (
            combined_text
            and raw_text
            and _looks_like_stock_idr_conversion_query(raw_text)
            and combined_text != source_text
        ):
            result = await _exec_tool(
                "stock",
                {"symbol": combined_text},
            )
            return str(result)

        q_lower = source_text.lower()
        tickers = extract_stock_symbols(source_text)
        if tickers:
            result = await _exec_tool(
                "stock",
                {"symbol": ",".join(tickers)},
            )
            return str(result)

        if "crypto" in q_lower or "btc" in q_lower or "eth" in q_lower:
            required_tool = "crypto"
        else:
            # For ranking/list-style requests without explicit ticker, use web search directly.
            stock_research_markers = ("top", "best", "teratas", "unggulan", "rekomendasi", "list", "daftar")
            if loop.tools.has("web_search") and any(marker in q_lower for marker in stock_research_markers):
                result = await _exec_tool(
                    "web_search",
                    {"query": source_text.strip(), "count": 5, "context_text": source_text},
                )
                return str(result)
            name_candidates = extract_stock_name_candidates(source_text)
            if not name_candidates:
                return i18n_t("stock.need_symbol", source_text)
            stock_result = await _exec_tool(
                "stock",
                {"symbol": source_text},
            )
            stock_text = str(stock_result)
            if (
                stock_text == i18n_t("stock.need_symbol", source_text)
                or "No valid stock ticker found" in stock_text
            ):
                return i18n_t("stock.need_symbol", source_text)
            return stock_text

    # Same fallback rule for crypto: keep the tool, but do not force it when
    # a matching external skill already owns the request.
    if required_tool == "crypto":
        coins = extract_crypto_ids(source_text)
        coin_arg = ",".join(coins) if coins else "bitcoin"
        result = await _exec_tool("crypto", {"coin": coin_arg})
        return str(result)

    if required_tool.startswith("mcp__"):
        payload = _extract_explicit_mcp_tool_arguments(loop, required_tool, source_text)
        if not payload:
            return None
        result = await _exec_tool(required_tool, payload)
        return str(result)

    if required_tool == "cleanup_system":
        # Detect cleanup level from user message
        q_lower = source_text.lower()
        level = "standard"
        if any(k in q_lower for k in ("deep", "dalam", "mendalam", "full", "lengkap")):
            level = "deep"
        elif any(k in q_lower for k in ("quick", "cepat", "ringan", "light")):
            level = "quick"
        result = await _exec_tool(
            "cleanup_system",
            {"level": level},
        )
        return str(result)

    if required_tool != "cron":
        return None

    from kabot.cron.parse import parse_absolute_time_ms, parse_relative_time_ms

    async def _exec_cron(payload: dict[str, Any]) -> Any:
        enriched = dict(payload)
        enriched.setdefault("context_text", source_text)
        return await _exec_tool("cron", enriched)

    q_lower = source_text.lower()
    is_management = any(op in q_lower for op in CRON_MANAGEMENT_OPS) and any(
        term in q_lower for term in CRON_MANAGEMENT_TERMS
    )

    if is_management and any(k in q_lower for k in ("list", "lihat", "show")):
        result = await _exec_cron({"action": "list_groups"})
        return str(result)

    if is_management and any(k in q_lower for k in ("hapus", "delete", "remove")):
        group_id_match = re.search(r"\bgrp_[a-z0-9_-]+\b", q_lower)
        if group_id_match:
            result = await _exec_cron({"action": "remove_group", "group_id": group_id_match.group(0)})
            return str(result)

        title = extract_explicit_schedule_title(source_text)
        if title:
            result = await _exec_cron({"action": "remove_group", "title": title})
            return str(result)

        job_id_match = re.search(r"\b[a-f0-9]{8}\b", q_lower)
        if job_id_match:
            result = await _exec_cron({"action": "remove", "job_id": job_id_match.group(0)})
            return str(result)

        return i18n_t("cron.remove.need_selector", source_text)

    if is_management and any(k in q_lower for k in ("edit", "ubah", "update")):
        selector_payload: dict[str, Any] = {}
        group_id_match = re.search(r"\bgrp_[a-z0-9_-]+\b", q_lower)
        if group_id_match:
            selector_payload["group_id"] = group_id_match.group(0)
        else:
            title = extract_explicit_schedule_title(source_text)
            if title:
                selector_payload["title"] = title

        if not selector_payload:
            return i18n_t("cron.update.need_selector", source_text)

        update_payload: dict[str, Any] = {"action": "update_group", **selector_payload}
        recurring_update = extract_recurring_schedule(source_text)
        if recurring_update:
            update_payload.update(recurring_update)

        new_title = extract_new_schedule_title(source_text)
        if new_title:
            update_payload["new_title"] = make_unique_schedule_title_for_loop(loop, new_title)

        if len(update_payload) <= 2:
            return i18n_t("cron.update.incomplete", source_text)

        result = await _exec_cron(update_payload)
        return str(result)

    cycle_schedule = extract_cycle_schedule(source_text)
    if cycle_schedule:
        every_seconds = int(cycle_schedule["period_days"]) * 86400
        group_title = nlp_build_cycle_title(
            source_text,
            int(cycle_schedule["period_days"]),
            existing_schedule_titles(loop),
        )
        group_id = build_group_id_for_loop(loop, group_title)
        created_jobs = 0
        for event in cycle_schedule["events"]:
            payload = {
                "action": "add",
                "message": event["message"],
                "title": group_title,
                "group_id": group_id,
                "every_seconds": every_seconds,
                "start_at": event["start_at"],
                "one_shot": False,
            }
            await _exec_cron(payload)
            created_jobs += 1
        return i18n_t(
            "cron.cycle_created",
            source_text,
            title=group_title,
            group_id=group_id,
            job_count=created_jobs,
            period_days=int(cycle_schedule["period_days"]),
        )

    reminder_text = extract_reminder_message(source_text)
    recurring_schedule = extract_recurring_schedule(source_text)
    if recurring_schedule:
        default_title = f"Recurring: {reminder_text[:40]}".strip()
        group_title = make_unique_schedule_title_for_loop(loop, default_title)
        recurring_payload = {
            "action": "add",
            "message": reminder_text,
            "title": group_title,
            "group_id": build_group_id_for_loop(loop, group_title),
            **recurring_schedule,
        }
        result = await _exec_cron(recurring_payload)
        return str(result)

    target_ms: int | None = None
    relative_ms = parse_relative_time_ms(source_text)
    if relative_ms is not None:
        now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        target_ms = now_ms + relative_ms
    else:
        absolute_match = re.search(
            r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)",
            source_text or "",
        )
        if absolute_match:
            target_ms = parse_absolute_time_ms(absolute_match.group(1))

    if target_ms is None:
        return i18n_t("cron.time_unclear", source_text)

    at_time = datetime.fromtimestamp(target_ms / 1000, tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    result = await _exec_cron(
        {
            "action": "add",
            "message": reminder_text,
            "at_time": at_time,
            "one_shot": True,
        }
    )
    return str(result)
