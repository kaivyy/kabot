"""Filesystem/path extraction helpers for tool enforcement."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kabot.agent.loop_core.tool_enforcement_parts.common import (
    _is_low_information_followup,
    _normalize_text,
)

_FILELIKE_QUERY_RE = re.compile(
    r"\b[\w\-]+\.(json|ya?ml|toml|ini|cfg|conf|env|md|txt|csv|log|pdf|docx?|xlsx?|py|js|ts|tsx|jsx|html|css|xml|zip|png|jpe?g|gif|mp4|mov|wav|mp3|ogg|m4a)\b",
    re.IGNORECASE,
)
_PATHLIKE_QUERY_RE = re.compile(
    r"([a-zA-Z]:[\\/][^\n\r\"']+|\\\\[^\n\r\"']+|(?<![\w])/(?=[^\"'\s]*[\w.])[^\"'\s]+|(?<![\w])~[\\/][^\s\"']+|[\w.\-]+\\[\w .\\/-]+)"
)
_RELATIVE_FILE_PATH_RE = re.compile(
    r"(?<![\w])((?:\.{1,2}[\\/]|[A-Za-z0-9_.-]+[\\/])(?:[^\s\"'`]+[\\/])*[^\s\"'`]+\.(?:json|ya?ml|toml|ini|cfg|conf|env|md|txt|csv|log|pdf|docx?|xlsx?|py|js|ts|tsx|jsx|html|css|xml|png|jpe?g|gif|mp4|mov|wav|mp3|ogg|m4a|zip|pptx?))",
    re.IGNORECASE,
)
_RELATIVE_DIRECTORY_PATH_RE = re.compile(
    r"(?<![\w])((?:(?:\.{1,2}[\\/])|(?:\.[A-Za-z0-9_.-]+[\\/]))(?:[^\s\"'`]+[\\/])*[^\s\"'`]+)",
    re.IGNORECASE,
)
_TEXTUAL_WRITE_FILE_SUFFIXES = {
    ".txt",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".env",
    ".csv",
    ".log",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".xml",
}

_FILESYSTEM_TARGET_MARKERS = (
    "desktop",
    "downloads",
    "download",
    "documents",
    "document",
    "docs",
    "pictures",
    "photos",
    "music",
    "videos",
    "home",
    "桌面",
    "下载",
    "下載",
    "文档",
    "文件档案",
    "文件檔案",
    "デスクトップ",
    "ダウンロード",
    "書類",
    "ドキュメント",
    "เดสก์ท็อป",
    "ดาวน์โหลด",
    "เอกสาร",
)
_FILESYSTEM_TRAILING_TAIL_RE = re.compile(
    r"(?i)\s+(?:sekarang|now|please|tolong|tampilkan|tampilin|show|display|list|lihat|lihatkan|"
    r"buka|open|masuk|enter|read|baca|dong|ya|lagi|again|pc)$"
)
_RELATIVE_DIRECTORY_QUERY_RE = re.compile(
    r"(?i)(?:\b(?:subfolder|folder|direktori|directory|dir)\b|文件夹|文件夾|资料夹|資料夾|目录|目錄|フォルダ|ディレクトリ|โฟลเดอร์|ไดเรกทอรี)\s+(.+)$"
)
_RELATIVE_DIRECTORY_SUFFIX_RE = re.compile(
    r"(?i)\s+(?:ada\b.*|isinya\b.*|isi\b.*|apa\b.*|what\b.*|which\b.*|show\b.*|display\b.*|list\b.*|lihat\b.*|lihatkan\b.*|tampilkan\b.*|open\b.*|buka\b.*|please\b.*|tolong\b.*|ke\s+chat\s+ini\b.*|ke\s+channel\s+ini\b.*|ke\s+sini\b.*|kesini\b.*|to\s+(?:this\s+)?chat\b.*|chat\s+here\b.*|channel\s+here\b.*|最初.*|件だけ.*|รายการ.*)$"
)
_SPECIAL_DIR_SUBFOLDER_PATTERNS = (
    re.compile(r"(?i)desktop(?:の|的)\s*([A-Za-z0-9._-]+)\s*(?:folder|directory|dir)\b"),
    re.compile(r"(?i)\bdesktop\b(?:\s+|[/\\]|-|\u2014|\u2013|of|inside|in|di|pada|dalam|ke|の|的)?\s*([A-Za-z0-9._-]+)\s*(?:folder|directory|dir)\b"),
    re.compile(r"桌面(?:的|内|裡|里|中)?\s*([A-Za-z0-9._-]+)\s*(?:文件夹|文件夾|資料夾|目录|目錄)"),
    re.compile(r"デスクトップ(?:の|内の)?\s*([A-Za-z0-9._-]+)\s*(?:フォルダ|ディレクトリ)"),
    re.compile(r"เดสก์ท็อป(?:ของ|ใน)?\s*([A-Za-z0-9._-]+)\s*(?:โฟลเดอร์|ไดเรกทอรี)"),
)
_SPECIAL_DIR_NORMALIZED_SUBFOLDER_RE = re.compile(
    r"(?i)\b(?:desktop|downloads?|documents?|docs|pictures?|photos?|music|videos?|home)\b"
    r"[^A-Za-z0-9._-]*([A-Za-z0-9._-]+)\s*(?:folder|directory|dir)\b"
)
_SPECIAL_DIR_ASCII_SUBFOLDER_RE = re.compile(
    r"(?i)\b([A-Za-z0-9._-]+)\s*(?:folder|directory|dir)\b"
)
_SPECIAL_DIR_PREFIX_RE = re.compile(
    r"(?i)^\s*(?:desktop|downloads?|documents?|docs|pictures?|photos?|music|videos?|home)\b"
)



def _filesystem_home_dir() -> Path:
    return Path.home()


def _normalize_filesystem_candidate(value: str) -> str:
    cleaned = str(value or "").strip().strip("\"'`").rstrip(".,;:!?)]}")
    while cleaned:
        next_cleaned = _FILESYSTEM_TRAILING_TAIL_RE.sub("", cleaned).strip().rstrip(".,;:!?)]}")
        if next_cleaned == cleaned:
            break
        cleaned = next_cleaned
    return cleaned


def _trim_candidate_after_filelike(candidate: str) -> str:
    raw = str(candidate or "").strip()
    if not raw:
        return ""
    matches = list(_FILELIKE_QUERY_RE.finditer(raw))
    if not matches:
        return raw
    last_match = matches[-1]
    trailing = raw[last_match.end() :].strip()
    if trailing:
        return raw[: last_match.end()]
    return raw


def _extract_explicit_path_candidate(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    quoted = re.findall(r"[\"'`]+([^\"'`]+)[\"'`]+", raw)
    for candidate in quoted:
        cleaned = _trim_candidate_after_filelike(_normalize_filesystem_candidate(candidate))
        if cleaned and (_FILELIKE_QUERY_RE.search(cleaned) or _PATHLIKE_QUERY_RE.search(cleaned)):
            return cleaned

    path_match = _PATHLIKE_QUERY_RE.search(raw)
    if path_match:
        cleaned = _trim_candidate_after_filelike(_normalize_filesystem_candidate(path_match.group(1)))
        if cleaned:
            return cleaned

    relative_file_match = _RELATIVE_FILE_PATH_RE.search(raw)
    if relative_file_match:
        cleaned = _trim_candidate_after_filelike(
            _normalize_filesystem_candidate(relative_file_match.group(1))
        )
        if cleaned:
            return cleaned

    relative_dir_match = _RELATIVE_DIRECTORY_PATH_RE.search(raw)
    if relative_dir_match:
        cleaned = _normalize_filesystem_candidate(relative_dir_match.group(1))
        if cleaned:
            return cleaned
    return None

def _looks_like_textual_write_target(path: str) -> bool:
    suffix = Path(str(path or "").strip()).suffix.lower()
    return suffix in _TEXTUAL_WRITE_FILE_SUFFIXES


def _looks_like_explicit_filesystem_path(path: str | None) -> bool:
    candidate = str(path or "").strip()
    if not candidate:
        return False
    return bool(
        candidate.startswith((".", "~", "/"))
        or re.match(r"^[A-Za-z]:[\\/]", candidate)
        or "\\" in candidate
        or "/" in candidate
    )


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


def _resolve_special_directory_path(text: str) -> str | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None
    if re.search(
        r"(?i)\b(current (?:working )?(?:directory|folder)|working directory|current dir|cwd|this folder|this directory)\b|folder kerja saat ini|direktori kerja saat ini|folder saat ini|direktori saat ini|folder ini|direktori ini",
        normalized,
    ):
        return str(Path.cwd().expanduser().resolve())
    home = _filesystem_home_dir()
    if re.search(r"(?i)\bdesktop\b|桌面|デスクトップ|เดสก์ท็อป", normalized):
        return str(home / "Desktop")
    if re.search(r"(?i)\bdownloads?\b|下载|下載|ダウンロード|ดาวน์โหลด", normalized):
        return str(home / "Downloads")
    if re.search(r"(?i)\bdocuments?\b|\bdocs\b|文档|文件档案|文件檔案|書類|ドキュメント|เอกสาร", normalized):
        return str(home / "Documents")
    if re.search(r"(?i)\bpictures?\b|\bphotos?\b", normalized):
        return str(home / "Pictures")
    if re.search(r"(?i)\bmusic\b", normalized):
        return str(home / "Music")
    if re.search(r"(?i)\bvideos?\b", normalized):
        return str(home / "Videos")
    if re.search(r"(?i)\bhome\b", normalized):
        return str(home)
    return None


def _extract_relative_directory_candidate(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    match = _RELATIVE_DIRECTORY_QUERY_RE.search(raw)
    if not match:
        return None
    candidate = _normalize_filesystem_candidate(match.group(1))
    if not candidate:
        return None
    candidate = _RELATIVE_DIRECTORY_SUFFIX_RE.sub("", candidate).strip(" ,.;:!?")
    if any(sep in candidate for sep in ("/", "\\")):
        return None
    normalized = _normalize_text(candidate)
    if normalized.startswith(("di ", "in ", "inside ", "pada ", "dalam ")):
        return None
    if re.match(
        r"(?i)^\d+\s*(?:item|items|entry|entries|hasil|baris|line|file|files|folder|folders)\b",
        candidate,
    ):
        return None
    if normalized in _FILESYSTEM_TARGET_MARKERS:
        return None
    return candidate

def _extract_read_file_path(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    explicit_path = _extract_explicit_path_candidate(raw)
    if explicit_path:
        return explicit_path

    # Finally, plain filename.ext tokens.
    file_match = _FILELIKE_QUERY_RE.search(raw)
    if file_match:
        cleaned = _normalize_filesystem_candidate(file_match.group(0))
        if cleaned:
            return cleaned
    return None


def _extract_list_dir_path(text: str, *, last_tool_context: dict[str, Any] | None = None) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    normalized_raw = _normalize_text(raw)

    fallback_path = ""
    if isinstance(last_tool_context, dict):
        fallback_path = str(last_tool_context.get("path") or "").strip()

    explicit_path = _extract_explicit_path_candidate(raw)
    if explicit_path:
        return explicit_path

    relative_dir = _extract_relative_directory_candidate(raw)
    special_dir = _resolve_special_directory_path(raw)
    if special_dir:
        for pattern in _SPECIAL_DIR_SUBFOLDER_PATTERNS:
            match = pattern.search(raw)
            if not match:
                continue
            nested_candidate = _normalize_filesystem_candidate(match.group(1))
            normalized_nested = _normalize_text(nested_candidate)
            if (
                nested_candidate
                and not any(sep in nested_candidate for sep in ("/", "\\"))
                and normalized_nested not in _FILESYSTEM_TARGET_MARKERS
            ):
                return str(Path(special_dir) / nested_candidate)
        normalized_match = _SPECIAL_DIR_NORMALIZED_SUBFOLDER_RE.search(normalized_raw)
        if normalized_match:
            nested_candidate = _normalize_filesystem_candidate(normalized_match.group(1))
            normalized_nested = _normalize_text(nested_candidate)
            if (
                nested_candidate
                and not any(sep in nested_candidate for sep in ("/", "\\"))
                and normalized_nested not in _FILESYSTEM_TARGET_MARKERS
            ):
                return str(Path(special_dir) / nested_candidate)
        if _SPECIAL_DIR_PREFIX_RE.search(normalized_raw):
            ascii_tail_match = _SPECIAL_DIR_ASCII_SUBFOLDER_RE.search(normalized_raw)
            if ascii_tail_match:
                nested_candidate = _normalize_filesystem_candidate(ascii_tail_match.group(1))
                normalized_nested = _normalize_text(nested_candidate)
                if (
                    nested_candidate
                    and not nested_candidate.isdigit()
                    and not any(sep in nested_candidate for sep in ("/", "\\"))
                    and normalized_nested not in _FILESYSTEM_TARGET_MARKERS
                ):
                    return str(Path(special_dir) / nested_candidate)
    if special_dir and relative_dir:
        return str(Path(special_dir) / relative_dir)
    if special_dir:
        return special_dir
    if relative_dir and fallback_path:
        return str(Path(fallback_path) / relative_dir)

    if fallback_path and _is_low_information_followup(raw):
        return fallback_path

    return None


_LIST_DIR_LIMIT_PATTERNS = (
    re.compile(r"(?i)\b(?:first|top|show|list)?\s*(\d{1,3})\s*(?:item|items|entry|entries|file|files|folder|folders)\b"),
    re.compile(r"(?i)\b(\d{1,3})\s*(?:item|items|entry|entries|hasil|baris|line|file|files|folder|folders)\s*(?:aja|saja|doang|only)?\b"),
    re.compile(r"(?i)\b(\d{1,3})\s*(?:aja|saja|doang)\b"),
    re.compile(r"(?i)\b(?:item|items)\s*(?:pertama|awal)\s*(\d{1,3})\b"),
    re.compile(r"最初の\s*(\d{1,3})\s*件"),
    re.compile(r"(\d{1,3})\s*件だけ"),
    re.compile(r"前\s*(\d{1,3})\s*[项項]"),
    re.compile(r"(\d{1,3})\s*[项項]"),
    re.compile(r"(\d{1,3})\s*รายการ"),
)

def _extract_list_dir_limit(text: str) -> int | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    for pattern in _LIST_DIR_LIMIT_PATTERNS:
        match = pattern.search(raw)
        if not match:
            continue
        try:
            value = int(match.group(1))
        except Exception:
            continue
        return max(1, min(200, value))
    return None
