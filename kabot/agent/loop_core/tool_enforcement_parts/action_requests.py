"""Action-request inference helpers for tool enforcement."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kabot.agent.loop_core.tool_enforcement_parts.common import _normalize_text
from kabot.agent.loop_core.tool_enforcement_parts.filesystem_paths import (
    _FILELIKE_QUERY_RE,
    _extract_explicit_path_candidate,
    _extract_list_dir_path,
    _extract_relative_directory_candidate,
    _extract_read_file_path,
    _looks_like_explicit_filesystem_path,
    _looks_like_textual_write_target,
    _resolve_special_directory_path,
)

_WRITE_FILE_ACTION_RE = re.compile(
    r"(?i)\b(?:generate|create|write|save)\s+file\b"
)
_WRITE_FILE_CONTENT_RE = re.compile(
    r"(?i)\b(?:content(?:s)?|containing|with\s+content)\b"
)
_WRITE_FILE_EMPTY_RE = re.compile(r"(?i)\b(?:blank|empty)\b")
_FIND_FILE_ACTION_RE = re.compile(
    r"(?i)\b(?:find|search(?:\s+for)?|locate|look\s+for)\b"
)
_FIND_FILE_DIR_SUBJECT_RE = re.compile(r"(?i)\b(?:folder|directory|dir)\b")
_FIND_FILE_FILE_SUBJECT_RE = re.compile(
    r"(?i)\b(?:file|document|config|pdf|csv|xlsx|docx)\b"
)
_SEND_FILE_ACTION_RE = re.compile(
    r"(?i)\b(?:send|share|attach|upload)\b"
)
_SEND_FILE_DELIVERY_RE = re.compile(
    r"(?i)(?:\b(?:chat|channel)\s+(?:here|this)\b|"
    r"\bto\s+this\s+chat\b|"
    r"\bsend\s+it\s+here\b|"
    r"\bhere\b)"
)
_LIST_DIR_ACTION_RE = re.compile(
    r"(?i)(?:\b(?:open|enter|show|display|list)\b|\buse\s+path\b)"
)
_LIST_DIR_WEAK_ACTION_RE = re.compile(r"(?i)\b(?:check)\b")
_LIST_DIR_SUBJECT_RE = re.compile(
    r"(?i)\b(?:folder|directory|dir|content(?:s)?|listing|file/?folder)\b|"
    r"文件(?:夹|夾)|資料夾|目?录|フォルダ|ディレクトリ|โฟลเดอร์|ไดเรกทอรี"
)
_IMAGE_ACTION_RE = re.compile(
    r"(?i)\b(?:image|poster|banner|logo|thumbnail|cover\s+art|illustration|render)\b"
)
_VIDEO_ACTION_RE = re.compile(
    r"(?i)\b(?:video|mp4|gif|clip|reel|animation)\b"
)
_AUDIO_ACTION_RE = re.compile(
    r"(?i)\b(?:audio|voice|speech|music|sound|mp3|wav)\b"
)
_ACTION_PROVIDER_RE = re.compile(
    r"(?i)\b(?:imagen|nanobanana|dall-?e|gemini|midjourney|stable\s+diffusion|sora|veo|runway|pika)\b"
)
_WRITE_FILE_CONTENT_INLINE_RE = re.compile(
    r"(?i)\b(?:content(?:s)?|containing|with content)\b\s*(?:[:=-]\s*)?(?:(?P<double>\"[^\"]+\")|(?P<single>'[^']+')|(?P<backtick>`[^`]+`)|(?P<plain>.+))"
)
_ACTION_TOOL_EXCLUDE_NAMES = {
    "read_file",
    "list_dir",
    "web_search",
    "weather",
    "stock",
    "stock_analysis",
    "crypto",
    "cron",
    "session_status",
    "message",
}


def _trim_find_files_query_candidate(value: str) -> str:
    candidate = str(value or "").strip().strip("\"'`")
    if not candidate:
        return ""
    candidate = re.sub(
        r"(?i)\s+(?:in|inside|within|under)\s+"
        r"(?:workspace|current working directory|working directory|current dir|cwd)\b.*$",
        "",
        candidate,
    ).strip()
    return candidate.rstrip(".,;:!?")

def _tool_name_available(loop: Any, tool_name: str) -> bool:
    tools = getattr(loop, "tools", None)
    has = getattr(tools, "has", None)
    if callable(has):
        try:
            return bool(has(tool_name))
        except Exception:
            return False
    tool_names = getattr(tools, "tool_names", None)
    if isinstance(tool_names, list):
        return tool_name in tool_names
    return False


def _iter_tool_names(loop: Any) -> list[str]:
    tools = getattr(loop, "tools", None)
    tool_names = getattr(tools, "tool_names", None)
    if isinstance(tool_names, list):
        return [str(name) for name in tool_names if str(name or "").strip()]
    return []


def _has_explicit_delivery_intent(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    return bool(
        _SEND_FILE_ACTION_RE.search(normalized)
        and (
            _SEND_FILE_DELIVERY_RE.search(normalized)
            or "chat" in normalized
            or "channel" in normalized
            or "telegram" in normalized
            or "whatsapp" in normalized
        )
    )


def _looks_like_write_file_request(text: str, *, explicit_path: str | None = None) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if not explicit_path:
        explicit_path = _extract_read_file_path(raw)
    if not explicit_path:
        return False
    if not _WRITE_FILE_ACTION_RE.search(normalized):
        return False
    has_inline_content = bool(_extract_write_file_content(raw))
    if _looks_like_textual_write_target(explicit_path):
        return has_inline_content or bool(_WRITE_FILE_EMPTY_RE.search(normalized))
    return has_inline_content or bool(_WRITE_FILE_CONTENT_RE.search(normalized))


def _looks_like_find_files_request(text: str, *, explicit_path: str | None = None) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    query = _extract_find_files_query(raw)
    if not query:
        return False
    if explicit_path and _looks_like_explicit_filesystem_path(explicit_path):
        return False
    dir_kind = _extract_find_files_kind(raw) == "dir"
    has_delivery_intent = _has_explicit_delivery_intent(raw)
    has_search_verb = bool(_FIND_FILE_ACTION_RE.search(normalized))
    has_explicit_filesystem_subject = bool(
        dir_kind
        or _FILELIKE_QUERY_RE.search(raw)
        or _FIND_FILE_FILE_SUBJECT_RE.search(normalized)
        or (explicit_path and _looks_like_explicit_filesystem_path(explicit_path))
    )
    if dir_kind and not has_delivery_intent:
        return False
    if has_search_verb:
        return bool(has_delivery_intent or has_explicit_filesystem_subject)
    if _LIST_DIR_ACTION_RE.search(normalized):
        return False
    if _LIST_DIR_WEAK_ACTION_RE.search(normalized):
        return False
    return False


def _looks_like_list_dir_request(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    list_path = _extract_list_dir_path(raw)
    if not list_path:
        return False
    if _has_explicit_delivery_intent(raw):
        return False
    if _LIST_DIR_ACTION_RE.search(normalized):
        return True
    if _LIST_DIR_WEAK_ACTION_RE.search(normalized):
        return bool(_extract_explicit_path_candidate(raw)) or bool(
            _LIST_DIR_SUBJECT_RE.search(normalized)
        ) or bool(
            _extract_read_file_path(raw) or _FILELIKE_QUERY_RE.search(raw)
        )
    if _extract_find_files_kind(raw) == "dir":
        query = _extract_find_files_query(raw) or _extract_relative_directory_candidate(raw)
        tokens = [token for token in _normalize_text(str(query or "")).split() if token]
        return 0 < len(tokens) <= 3
    return False


def _looks_like_message_send_file_request(text: str, *, explicit_path: str | None = None) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized or not explicit_path:
        return False
    if not _SEND_FILE_ACTION_RE.search(normalized):
        return False

    # Avoid hijacking explanatory/help-style turns.
    if re.match(r"(?i)^\s*(?:how\s+to)\b", raw):
        return False

    has_find_intent = bool(_FIND_FILE_ACTION_RE.search(normalized))
    explicit_is_pathlike = _looks_like_explicit_filesystem_path(explicit_path)

    # Keep search-first phrasing on the find_files lane when the user asks to
    # search first (e.g. "find file report.pdf then send").
    if has_find_intent and not explicit_is_pathlike:
        return False

    if not explicit_is_pathlike:
        # Bare filenames (e.g. "send file TELEGRAM_DEMO.md here") are valid
        # send intents; resolution will use recent folder context when available.
        if not _FILELIKE_QUERY_RE.search(str(explicit_path)):
            return False

    delivery_marker = bool(
        _SEND_FILE_DELIVERY_RE.search(normalized)
        or "chat" in normalized
        or "channel" in normalized
    )
    imperative_send = bool(re.match(r"(?i)^\s*(?:send|share|attach|upload)\b", raw))
    return delivery_marker or imperative_send


def _extract_find_files_query(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    explicit_path = _extract_read_file_path(raw)
    if explicit_path:
        if _looks_like_explicit_filesystem_path(explicit_path):
            return Path(explicit_path).name or explicit_path
        return explicit_path

    quoted = re.findall(r"[\"'`]+([^\"'`]+)[\"'`]+", raw)
    for candidate in quoted:
        cleaned = _trim_find_files_query_candidate(candidate)
        if cleaned:
            return cleaned

    relative_dir = _extract_relative_directory_candidate(raw)
    if relative_dir and _extract_find_files_kind(raw) == "dir":
        cleaned_relative_dir = _trim_find_files_query_candidate(relative_dir)
        if cleaned_relative_dir:
            return cleaned_relative_dir

    patterns = (
        re.compile(
            r"(?i)\b(?:file|document|folder|directory|dir|config|pdf|csv|xlsx|docx)\b\s+([A-Za-z0-9_.*\-]+)"
        ),
        re.compile(
            r"(?i)\b(?:find|search|locate|look for)\b\s+([A-Za-z0-9_.*\-]+)"
        ),
    )
    for pattern in patterns:
        match = pattern.search(raw)
        if not match:
            continue
        candidate = _trim_find_files_query_candidate(match.group(1))
        if candidate:
            return candidate
    return None


def _extract_find_files_kind(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    normalized = _normalize_text(raw)
    if _FIND_FILE_DIR_SUBJECT_RE.search(normalized):
        return "dir"
    if bool(_FILELIKE_QUERY_RE.search(raw)) or _FIND_FILE_FILE_SUBJECT_RE.search(normalized):
        return "file"
    return None


def _resolve_find_files_root(
    loop: Any,
    text: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    normalized = _normalize_text(text)
    if "workspace" in normalized:
        workspace = getattr(loop, "workspace", None)
        if isinstance(workspace, Path):
            return str(workspace.resolve())
        if isinstance(workspace, str) and str(workspace).strip():
            return str(Path(workspace).expanduser().resolve())

    special_dir = _resolve_special_directory_path(text)
    if special_dir:
        return special_dir

    last_tool_context = metadata.get("last_tool_context") if isinstance(metadata, dict) else {}
    list_path = _extract_list_dir_path(text, last_tool_context=last_tool_context if isinstance(last_tool_context, dict) else None)
    if list_path:
        return list_path

    if isinstance(metadata, dict):
        working_directory = str(metadata.get("working_directory") or "").strip()
        if working_directory:
            try:
                resolved_working_directory = Path(working_directory).expanduser().resolve()
                if resolved_working_directory.exists() and resolved_working_directory.is_dir():
                    return str(resolved_working_directory)
            except Exception:
                return working_directory
        if isinstance(last_tool_context, dict):
            last_path = str(last_tool_context.get("path") or "").strip()
            if last_path:
                try:
                    resolved = Path(last_path).expanduser().resolve()
                    if resolved.exists() and resolved.is_dir():
                        return str(resolved)
                except Exception:
                    return last_path
        last_nav = str(metadata.get("last_navigated_path") or "").strip()
        if last_nav:
            try:
                resolved_nav = Path(last_nav).expanduser().resolve()
                if resolved_nav.exists() and resolved_nav.is_dir():
                    return str(resolved_nav)
            except Exception:
                return last_nav
    if isinstance(last_tool_context, dict):
        last_path = str(last_tool_context.get("path") or "").strip()
        if last_path:
            try:
                resolved = Path(last_path).expanduser().resolve()
                if resolved.exists() and resolved.is_dir():
                    return str(resolved)
            except Exception:
                return last_path
    return None


def _resolve_delivery_path(loop: Any, path: str) -> Path:
    candidate = Path(str(path or "").strip()).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()

    resolved_candidates: list[Path] = []
    try:
        resolved_candidates.append((Path.cwd().expanduser() / candidate).resolve())
    except Exception:
        pass

    workspace = getattr(loop, "workspace", None)
    if isinstance(workspace, Path):
        try:
            resolved_candidates.append((workspace / candidate).resolve())
        except Exception:
            pass
    elif isinstance(workspace, str) and str(workspace).strip():
        try:
            resolved_candidates.append((Path(workspace).expanduser() / candidate).resolve())
        except Exception:
            pass

    for resolved in resolved_candidates:
        if resolved.exists():
            return resolved
    if resolved_candidates:
        return resolved_candidates[0]
    return candidate.resolve()


def _extract_message_delivery_path(
    text: str,
    *,
    last_tool_context: dict[str, Any] | None = None,
) -> str | None:
    file_path = _extract_read_file_path(text)
    dir_path = _extract_list_dir_path(text, last_tool_context=last_tool_context)
    last_found_path = (
        str(last_tool_context.get("path") or "").strip()
        if isinstance(last_tool_context, dict)
        else ""
    )

    if file_path:
        normalized_file = str(file_path).strip()
        if _looks_like_explicit_filesystem_path(normalized_file):
            return normalized_file

        if dir_path:
            dir_obj = Path(str(dir_path).strip())
            if dir_obj.suffix:
                if dir_obj.name.lower() == normalized_file.lower():
                    return str(dir_obj)
                return str(dir_obj.parent / normalized_file)
            return str(dir_obj / normalized_file)

        if last_found_path:
            last_path_obj = Path(last_found_path)
            if last_path_obj.suffix:
                if last_path_obj.name.lower() == normalized_file.lower():
                    return str(last_path_obj)
                return str(last_path_obj.parent / normalized_file)
            return str(last_path_obj / normalized_file)

        return normalized_file

    path = str(dir_path or last_found_path or "").strip()
    return path or None


def _trim_write_content_candidate(value: str) -> str:
    candidate = str(value or "").strip().strip("\"'`")
    if not candidate:
        return ""
    candidate = re.split(
        r"(?i)\s+(?:then|afterwards?)\s+(?:send|attach|upload|export|save)\b",
        candidate,
        maxsplit=1,
    )[0].strip()
    candidate = re.split(r"(?i)\s+(?:then|afterwards?)\b", candidate, maxsplit=1)[0].strip()
    return candidate.rstrip(" .,:;")


def _extract_write_file_content(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    match = _WRITE_FILE_CONTENT_INLINE_RE.search(raw)
    if not match:
        return None
    candidate = next((group for group in match.groups() if group), "")
    cleaned = _trim_write_content_candidate(candidate)
    return cleaned or None


def _looks_like_media_action_request(text: str, *, kind: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    pattern = _IMAGE_ACTION_RE
    if kind == "video":
        pattern = _VIDEO_ACTION_RE
    elif kind == "audio":
        pattern = _AUDIO_ACTION_RE
    return bool(pattern.search(normalized))


def _select_best_action_tool(loop: Any, text: str, *, kind: str) -> str | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None
    tool_names = _iter_tool_names(loop)
    if not tool_names:
        return None
    if kind == "image" and _tool_name_available(loop, "image_gen"):
        return "image_gen"

    media_pattern = _IMAGE_ACTION_RE
    if kind == "video":
        media_pattern = _VIDEO_ACTION_RE
    elif kind == "audio":
        media_pattern = _AUDIO_ACTION_RE

    provider_hits = {
        str(hit).lower()
        for hit in _ACTION_PROVIDER_RE.findall(normalized)
        if str(hit or "").strip()
    }
    best_name = None
    best_score = 0
    for name in tool_names:
        tool_name = str(name or "").strip()
        if not tool_name or tool_name in _ACTION_TOOL_EXCLUDE_NAMES:
            continue
        tool_norm = re.sub(r"[_\-.]+", " ", tool_name.lower())
        score = 0
        if tool_name.startswith("mcp__"):
            score += 1
        if media_pattern.search(tool_norm):
            score += 5
        if any(marker in tool_norm for marker in provider_hits):
            score += 6
        if any(marker in tool_norm for marker in ("generate", "generator", "gen", "create", "render")):
            score += 3
        if kind == "image" and "image" in tool_norm:
            score += 2
        if kind == "video" and "video" in tool_norm:
            score += 2
        if kind == "audio" and any(marker in tool_norm for marker in ("audio", "voice", "speech", "music")):
            score += 2
        if score > best_score:
            best_score = score
            best_name = tool_name
    return best_name if best_score >= 6 else None


def infer_action_required_tool_for_loop(loop: Any, text: str) -> tuple[str | None, str | None]:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not raw or not normalized:
        return None, None

    explicit_path = _extract_read_file_path(raw)
    if _tool_name_available(loop, "write_file") and _looks_like_write_file_request(
        raw,
        explicit_path=explicit_path,
    ):
        return "write_file", raw

    if _tool_name_available(loop, "message") and _looks_like_message_send_file_request(
        raw,
        explicit_path=explicit_path,
    ):
        return "message", raw

    if _tool_name_available(loop, "list_dir") and _looks_like_list_dir_request(raw):
        return "list_dir", raw

    if _tool_name_available(loop, "find_files") and _looks_like_find_files_request(
        raw,
        explicit_path=explicit_path,
    ):
        return "find_files", raw

    if _looks_like_media_action_request(raw, kind="image"):
        image_tool = _select_best_action_tool(loop, raw, kind="image")
        if image_tool:
            return image_tool, raw

    if _looks_like_media_action_request(raw, kind="video"):
        video_tool = _select_best_action_tool(loop, raw, kind="video")
        if video_tool:
            return video_tool, raw

    if _looks_like_media_action_request(raw, kind="audio"):
        audio_tool = _select_best_action_tool(loop, raw, kind="audio")
        if audio_tool:
            return audio_tool, raw

    if _ACTION_PROVIDER_RE.search(normalized):
        for kind in ("image", "video", "audio"):
            provider_tool = _select_best_action_tool(loop, raw, kind=kind)
            if provider_tool:
                return provider_tool, raw

    return None, None
