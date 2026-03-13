"""Artifact-path and completion-evidence helpers for execution runtime."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from loguru import logger

from kabot.agent.loop_core.execution_runtime_parts.intent import (
    _is_low_information_turn,
    _looks_like_short_confirmation,
    _normalize_text,
)


def _stringify_tool_arg_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set)):
        parts: list[str] = []
        for item in value:
            text = _stringify_tool_arg_value(item)
            if text:
                parts.append(text)
        return ", ".join(parts).strip()
    if isinstance(value, dict):
        parts: list[str] = []
        for key in sorted(value.keys()):
            text = _stringify_tool_arg_value(value.get(key))
            if text:
                parts.append(f"{key}:{text}")
        return ", ".join(parts).strip()
    return str(value).strip()


_DEFAULT_TOOL_SOURCE_KEYS = (
    "query",
    "q",
    "symbol",
    "ticker",
    "location",
    "city",
    "path",
    "url",
    "coin",
    "id",
    "name",
    "title",
    "topic",
    "prompt",
)
_TOOL_SOURCE_KEYS_BY_NAME: dict[str, tuple[str, ...]] = {
    "weather": ("location", "city", "place", "query", "q"),
    "stock": ("symbol", "ticker", "query", "q", "name"),
    "stock_analysis": ("symbol", "ticker", "query", "q", "name"),
    "crypto": ("coin", "symbol", "ticker", "query", "q"),
    "find_files": ("query", "name", "path"),
    "message": ("files", "path", "content"),
    "read_file": ("path", "file_path", "filepath"),
    "list_dir": ("path", "directory", "dir"),
    "web_search": ("query", "q", "keyword", "keywords"),
}


def _looks_like_short_context_value(text: str) -> bool:
    return _looks_like_short_confirmation(text) or _is_low_information_turn(
        text,
        max_tokens=6,
        max_chars=64,
    )


def _pick_primary_tool_argument(tool_name: str, tool_args: dict[str, Any] | None) -> str:
    if not isinstance(tool_args, dict):
        return ""
    normalized_tool = str(tool_name or "").strip().lower()
    preferred = _TOOL_SOURCE_KEYS_BY_NAME.get(normalized_tool, _DEFAULT_TOOL_SOURCE_KEYS)
    for key in preferred:
        if key not in tool_args:
            continue
        value = _stringify_tool_arg_value(tool_args.get(key))
        if value:
            return value
    for key, value in tool_args.items():
        key_name = str(key or "").strip()
        if not key_name or key_name.startswith("_"):
            continue
        text = _stringify_tool_arg_value(value)
        if text:
            return text
    return ""


def _sanitize_tool_args_snapshot(tool_args: dict[str, Any] | None, *, max_items: int = 8) -> dict[str, Any]:
    if not isinstance(tool_args, dict):
        return {}
    snapshot: dict[str, Any] = {}
    for key in list(tool_args.keys())[:max_items]:
        key_name = str(key or "").strip()
        if not key_name or key_name.startswith("_"):
            continue
        value = _stringify_tool_arg_value(tool_args.get(key))
        if not value:
            continue
        if len(value) > 160:
            value = value[:157].rstrip() + "..."
        snapshot[key_name] = value
    return snapshot


_RESULT_PATH_SUFFIX_PATTERN = (
    r"png|jpe?g|gif|webp|bmp|svg|mp4|mov|wav|mp3|ogg|m4a|pdf|docx?|xlsx?|csv|txt|json|yaml|yml|zip"
)
_RESULT_RELATIVE_PATH_RE = re.compile(
    rf"(?<![\w.:/\\-])((?:\.{{1,2}}[\\/]|[A-Za-z0-9_.-]+[\\/])(?:[^\s\"'`]+[\\/])*[^\s\"'`]+\.(?:{_RESULT_PATH_SUFFIX_PATTERN}))",
    re.IGNORECASE,
)
_RESULT_ABSOLUTE_PATH_RE = re.compile(
    rf"(?<![\w.:/\\-])((?:[A-Za-z]:[\\/]|/)[^\r\n\"']+\.(?:{_RESULT_PATH_SUFFIX_PATTERN}))",
    re.IGNORECASE,
)
_RESULT_BARE_FILENAME_RE = re.compile(
    rf"(?<![:/\w.-])([A-Za-z0-9_.-]+\.(?:{_RESULT_PATH_SUFFIX_PATTERN}))(?![\w.-])",
    re.IGNORECASE,
)
_RESULT_PATH_KEY_TOKENS = (
    "path",
    "file",
    "files",
    "artifact",
    "artifacts",
    "output",
    "outputs",
    "result",
    "results",
    "attachment",
    "attachments",
    "image",
    "images",
    "video",
    "videos",
    "audio",
    "media",
    "uri",
)
_RESULT_PATH_SKIP_KEYS = {
    "mime",
    "mime_type",
    "content_type",
    "media_type",
    "type",
    "status",
    "message",
    "prompt",
}


def _normalize_result_path_candidate(candidate: str) -> str:
    normalized = str(candidate or "").strip().strip("\"'`")
    if not normalized:
        return ""
    return normalized.rstrip(".,;:!?)]}")


def _extract_file_uri_path(candidate: str) -> str:
    raw = str(candidate or "").strip()
    if not raw.lower().startswith("file://"):
        return ""
    try:
        parsed = urlparse(raw)
    except Exception:
        return ""
    if str(parsed.scheme or "").lower() != "file":
        return ""
    path = unquote(str(parsed.path or "").strip())
    if parsed.netloc and re.fullmatch(r"(?i)[A-Z]:", str(parsed.netloc or "").strip()):
        path = f"{parsed.netloc}{path}"
    normalized = _normalize_result_path_candidate(path)
    if re.search(rf"\.(?:{_RESULT_PATH_SUFFIX_PATTERN})$", normalized, re.IGNORECASE):
        return normalized
    return ""


def _looks_like_local_result_path(candidate: str) -> bool:
    normalized = _normalize_result_path_candidate(candidate)
    if not normalized:
        return False
    lowered = normalized.lower()
    if lowered.startswith(("http://", "https://")):
        return False
    if not re.search(rf"\.(?:{_RESULT_PATH_SUFFIX_PATTERN})$", normalized, re.IGNORECASE):
        return False
    if (
        normalized.startswith(("/", "./", "../"))
        or re.match(r"(?i)^[A-Z]:[\\/]", normalized)
        or "\\" in normalized
        or "/" in normalized
        or re.fullmatch(rf"[A-Za-z0-9_.-]+\.(?:{_RESULT_PATH_SUFFIX_PATTERN})", normalized, re.IGNORECASE)
    ):
        return True
    return False


def _is_result_path_key(key_hint: str) -> bool:
    normalized = str(key_hint or "").strip().lower()
    return bool(normalized) and any(token in normalized for token in _RESULT_PATH_KEY_TOKENS)


def _extract_path_candidates_from_string(value: str, *, key_hint: str = "") -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []

    normalized_key = str(key_hint or "").strip().lower()
    if normalized_key in _RESULT_PATH_SKIP_KEYS:
        return []

    candidates: list[str] = []
    file_uri_path = _extract_file_uri_path(raw)
    if file_uri_path:
        candidates.append(file_uri_path)

    if raw[:1] in {"{", "["}:
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
        if parsed is not None:
            candidates.extend(_extract_path_candidates_from_value(parsed))

    for pattern in (_RESULT_RELATIVE_PATH_RE, _RESULT_ABSOLUTE_PATH_RE, _RESULT_BARE_FILENAME_RE):
        for match in pattern.finditer(raw):
            candidate = _normalize_result_path_candidate(match.group(1))
            if _looks_like_local_result_path(candidate):
                candidates.append(candidate)

    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def _extract_path_candidates_from_value(value: Any, *, key_hint: str = "", _depth: int = 0) -> list[str]:
    if _depth > 6:
        return []

    if value is None:
        return []
    if isinstance(value, str):
        return _extract_path_candidates_from_string(value, key_hint=key_hint)
    if isinstance(value, dict):
        prioritized: list[tuple[str, Any]] = []
        deferred: list[tuple[str, Any]] = []
        for key, item in value.items():
            key_name = str(key or "")
            if _is_result_path_key(key_name):
                prioritized.append((key_name, item))
            else:
                deferred.append((key_name, item))
        candidates: list[str] = []
        for child_key, child_value in prioritized + deferred:
            candidates.extend(
                _extract_path_candidates_from_value(
                    child_value,
                    key_hint=child_key,
                    _depth=_depth + 1,
                )
            )
        return list(dict.fromkeys(candidate for candidate in candidates if candidate))
    if isinstance(value, (list, tuple, set)):
        candidates: list[str] = []
        for item in value:
            candidates.extend(
                _extract_path_candidates_from_value(
                    item,
                    key_hint=key_hint,
                    _depth=_depth + 1,
                )
            )
        return list(dict.fromkeys(candidate for candidate in candidates if candidate))
    if hasattr(value, "__fspath__"):
        candidate = _normalize_result_path_candidate(str(value))
        if _looks_like_local_result_path(candidate):
            return [candidate]
        return []
    return _extract_path_candidates_from_string(str(value), key_hint=key_hint)


def _extract_single_result_path(tool_name: str, tool_args: dict[str, Any] | None, tool_result: Any) -> str:
    normalized_tool = str(tool_name or "").strip().lower()
    if normalized_tool == "message":
        if isinstance(tool_args, dict):
            files_arg = tool_args.get("files")
            if isinstance(files_arg, list):
                for item in files_arg:
                    candidate = str(item or "").strip()
                    if candidate:
                        return candidate
            path_arg = str(tool_args.get("path") or "").strip()
            if path_arg:
                return path_arg
    if normalized_tool in {"write_file", "read_file"} and isinstance(tool_args, dict):
        path_arg = str(tool_args.get("path") or "").strip()
        if path_arg:
            return path_arg
    if normalized_tool == "list_dir" and isinstance(tool_args, dict):
        for key in ("path", "directory", "dir"):
            path_arg = str(tool_args.get(key) or "").strip()
            if path_arg:
                return path_arg
    if normalized_tool == "exec" and isinstance(tool_args, dict):
        command_text = str(
            tool_args.get("command")
            or tool_args.get("cmd")
            or tool_args.get("shell")
            or ""
        ).strip()
        if command_text:
            named_path_match = re.search(
                r"""(?ix)
                \b(?:path|output|outfile|out)\s*
                (?:=|:)\s*
                ['"]([^'"]+\.(?:png|jpe?g|gif|webp|bmp|svg|pdf|mp4|mov|wav|mp3|txt|html|json|csv|xlsx?))['"]
                """,
                command_text,
            )
            if named_path_match:
                return str(named_path_match.group(1) or "").strip()
            command_candidates = _extract_path_candidates_from_string(command_text)
            if command_candidates:
                return command_candidates[0]
    if normalized_tool == "find_files":
        raw_result = str(tool_result or "").strip()
        if not raw_result:
            return ""
        matched_paths: list[str] = []
        for line in raw_result.splitlines():
            stripped = str(line or "").strip()
            if stripped.startswith("FILE ") or stripped.startswith("DIR "):
                candidate = stripped.split(" ", 1)[1].strip()
                if candidate:
                    matched_paths.append(candidate)
        unique_paths = list(dict.fromkeys(matched_paths))
        if unique_paths:
            return unique_paths[0]
    if normalized_tool == "archive_path":
        raw_result = str(tool_result or "").strip()
        if raw_result:
            archive_match = re.search(
                r"(?i)(?:created\s+archive|archive(?:d)?(?:\s+path)?[:=]?)\s+(.+?\.(?:zip|tar|tgz|gz|7z|rar))(?:\s+from\b|$)",
                raw_result,
            )
            if archive_match:
                return _normalize_result_path_candidate(archive_match.group(1))
    if normalized_tool == "image_gen":
        raw_result = str(tool_result or "").strip()
        if not raw_result:
            return ""
        path_match = re.search(
            r"((?:[A-Za-z]:[\\/]|/|\.{1,2}[\\/])[^\r\n\"']+\.(?:png|jpe?g|gif|webp|bmp|svg|mp4|mov|wav|mp3))",
            raw_result,
            re.IGNORECASE,
        )
        if path_match:
            return str(path_match.group(1) or "").strip()
    structured_candidates = _extract_path_candidates_from_value(tool_result)
    if structured_candidates:
        return structured_candidates[0]
    raw_result = str(tool_result or "").strip()
    if raw_result:
        string_candidates = _extract_path_candidates_from_string(raw_result)
        if string_candidates:
            return string_candidates[0]
    return ""


def _resolve_completion_artifact_path(loop: Any, candidate: str) -> str:
    raw = str(candidate or "").strip()
    if not raw:
        return ""
    try:
        path = Path(raw).expanduser()
    except Exception:
        return raw
    if path.is_absolute():
        try:
            return str(path.resolve())
        except Exception:
            return str(path)

    resolved_candidates: list[Path] = []
    workspace = getattr(loop, "workspace", None)
    if isinstance(workspace, Path):
        try:
            resolved_candidates.append((workspace / path).resolve())
        except Exception:
            pass
    elif isinstance(workspace, str) and str(workspace).strip():
        try:
            resolved_candidates.append((Path(workspace).expanduser() / path).resolve())
        except Exception:
            pass
    try:
        resolved_candidates.append((Path.cwd().expanduser() / path).resolve())
    except Exception:
        pass
    for resolved in resolved_candidates:
        if resolved.exists():
            return str(resolved)
    if resolved_candidates:
        return str(resolved_candidates[0])
    try:
        return str(path.resolve())
    except Exception:
        return str(path)


def _verify_completion_artifact_path(loop: Any, candidate: str) -> tuple[str, bool]:
    resolved = _resolve_completion_artifact_path(loop, candidate)
    if not resolved:
        return "", False
    try:
        resolved_path = Path(resolved).expanduser()
        return str(resolved_path), resolved_path.exists()
    except Exception:
        return resolved, False


def _unique_preserve_order(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _update_completion_evidence(
    metadata: dict[str, Any] | None,
    session: Any,
    *,
    artifact_paths: list[str] | None = None,
    artifact_verified: bool | None = None,
    delivery_paths: list[str] | None = None,
    delivery_verified: bool | None = None,
) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}

    existing = metadata.get("completion_evidence")
    evidence = dict(existing) if isinstance(existing, dict) else {}
    executed_tools = metadata.get("executed_tools")
    if isinstance(executed_tools, list):
        evidence["executed_tools"] = _unique_preserve_order([str(item) for item in executed_tools])
    else:
        evidence.setdefault("executed_tools", [])

    current_artifact_paths = evidence.get("artifact_paths")
    merged_artifact_paths = list(current_artifact_paths) if isinstance(current_artifact_paths, list) else []
    if artifact_paths:
        merged_artifact_paths.extend(str(item) for item in artifact_paths if str(item or "").strip())
    evidence["artifact_paths"] = _unique_preserve_order(merged_artifact_paths)

    current_delivery_paths = evidence.get("delivery_paths")
    merged_delivery_paths = list(current_delivery_paths) if isinstance(current_delivery_paths, list) else []
    if delivery_paths:
        merged_delivery_paths.extend(str(item) for item in delivery_paths if str(item or "").strip())
    evidence["delivery_paths"] = _unique_preserve_order(merged_delivery_paths)

    if artifact_verified is not None:
        evidence["artifact_verified"] = bool(artifact_verified)
    else:
        evidence.setdefault("artifact_verified", False)
    if delivery_verified is not None:
        evidence["delivery_verified"] = bool(delivery_verified)
    else:
        evidence.setdefault("delivery_verified", False)

    evidence["requires_delivery"] = bool(metadata.get("requires_message_delivery", False))
    evidence["updated_at"] = time.time()
    metadata["completion_evidence"] = evidence
    executed_summary = ",".join(evidence.get("executed_tools", []))
    logger.info(
        "completion_evidence "
        f"artifact_verified={str(bool(evidence.get('artifact_verified', False))).lower()} "
        f"delivery_verified={str(bool(evidence.get('delivery_verified', False))).lower()} "
        f"executed_tools={executed_summary}"
    )

    session_metadata = getattr(session, "metadata", None)
    if isinstance(session_metadata, dict):
        session_metadata["last_completion_evidence"] = dict(evidence)
    return evidence


def _resolve_followup_source_from_execution(
    *,
    tool_name: str,
    tool_args: dict[str, Any] | None,
    fallback_source: str,
) -> str:
    arg_value = _pick_primary_tool_argument(tool_name, tool_args)
    fallback = str(fallback_source or "").strip()
    if not fallback:
        return arg_value
    if not arg_value:
        return fallback
    if _looks_like_short_context_value(fallback):
        return arg_value
    fallback_norm = _normalize_text(fallback)
    arg_norm = _normalize_text(arg_value)
    if arg_norm and arg_norm in fallback_norm:
        return fallback
    if len(fallback_norm.split()) <= 2:
        return arg_value
    combined = f"{arg_value} {fallback}".strip()
    return combined[:220]


def _update_followup_context_from_tool_execution(
    session: Any,
    *,
    tool_name: str,
    tool_args: dict[str, Any] | None,
    fallback_source: str,
    tool_result: Any = None,
    now_ts: float | None = None,
) -> None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return

    normalized_tool = str(tool_name or "").strip()
    if not normalized_tool:
        return

    source_text = _resolve_followup_source_from_execution(
        tool_name=normalized_tool,
        tool_args=tool_args,
        fallback_source=fallback_source,
    )
    if not source_text:
        source_text = str(fallback_source or normalized_tool).strip()
    if not source_text:
        return

    ts = float(now_ts) if isinstance(now_ts, (int, float)) else time.time()
    try:
        from kabot.agent.loop_core.message_runtime_parts.followup import (
            _set_last_tool_context,
            _set_pending_followup_tool,
        )

        _set_last_tool_context(session, normalized_tool, ts, source_text)
        _set_pending_followup_tool(session, normalized_tool, ts, source_text)
    except Exception as exc:
        logger.debug(f"Failed updating follow-up tool context for {normalized_tool}: {exc}")
        return

    preview = str(tool_result or "").strip()
    if len(preview) > 280:
        preview = preview[:277].rstrip() + "..."
    metadata["last_tool_execution"] = {
        "tool": normalized_tool,
        "source": _normalize_text(source_text)[:220],
        "args": _sanitize_tool_args_snapshot(tool_args),
        "result_preview": preview,
        "updated_at": ts,
    }
    extracted_path = _extract_single_result_path(normalized_tool, tool_args, tool_result)
    if extracted_path:
        last_tool_context = metadata.get("last_tool_context")
        if isinstance(last_tool_context, dict):
            last_tool_context["path"] = extracted_path
        else:
            metadata["last_tool_context"] = {
                "tool": normalized_tool,
                "source": source_text,
                "path": extracted_path,
                "updated_at": ts,
            }

        if normalized_tool in {"list_dir", "read_file"}:
            try:
                candidate_path = Path(str(extracted_path)).expanduser().resolve()
            except Exception:
                candidate_path = None
            if candidate_path is not None and candidate_path.exists() and candidate_path.is_dir():
                metadata["last_navigated_path"] = str(candidate_path)
