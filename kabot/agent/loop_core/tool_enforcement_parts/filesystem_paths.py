"""Filesystem/path extraction helpers for tool enforcement."""

from __future__ import annotations

import os
import re
from pathlib import Path, PureWindowsPath
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
    r"buka|open|masuk|enter|read|baca|dong|ya|lagi|again|pc|"
    r"ke\s+sini|kesini|ke\s+chat\s+ini|chat\s+ini|chat\s+here|"
    r"to\s+(?:this\s+)?chat|to\s+(?:this\s+)?channel|channel\s+here|channel\s+ini)$"
)
_RELATIVE_DIRECTORY_QUERY_RE = re.compile(
    r"(?i)(?:\b(?:subfolder|folder|direktori|directory|dir)\b|文件夹|文件夾|资料夹|資料夾|目录|目錄|フォルダ|ディレクトリ|โฟลเดอร์|ไดเรกทอรี)\s+(.+)$"
)
_RELATIVE_DIRECTORY_COMMAND_RE = re.compile(
    r"(?i)^\s*(?:buka|open|masuk|enter|cd|chdir|goto|go\s+to|lihat|list|tampilkan|show)\s+([A-Za-z0-9._\\/-]+)\s*$"
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
_SPECIAL_DIR_PATH_HINT_RE = re.compile(
    r"(?i)\b(?:(?:ya|yes)\s+)?(?:(?:pakai|gunakan|use|with|via)\s+)?path\s+"
    r"(?:desktop|downloads?|documents?|docs|pictures?|photos?|music|videos?|home)\b\s+([A-Za-z0-9._-]+)\b"
)
_SPECIAL_DIR_PREFIX_RE = re.compile(
    r"(?i)^\s*(?:desktop|downloads?|documents?|docs|pictures?|photos?|music|videos?|home)\b"
)


def _filesystem_home_dir() -> Path:
    return Path.home()


_SPECIAL_DIR_ENV_MAP = {
    "desktop": "XDG_DESKTOP_DIR",
    "downloads": "XDG_DOWNLOAD_DIR",
    "documents": "XDG_DOCUMENTS_DIR",
    "pictures": "XDG_PICTURES_DIR",
    "music": "XDG_MUSIC_DIR",
    "videos": "XDG_VIDEOS_DIR",
}


def _expand_special_directory_value(raw_value: str, home: Path) -> Path | None:
    raw = str(raw_value or "").strip()
    if not raw:
        return None
    cleaned = raw.strip().strip("\"'")
    if not cleaned:
        return None
    cleaned = cleaned.replace("${HOME}", str(home)).replace("$HOME", str(home))
    candidate = Path(cleaned).expanduser()
    if not candidate.is_absolute():
        candidate = home / candidate
    return candidate


def _resolve_special_directory_override(name: str, home: Path) -> Path | None:
    env_key = _SPECIAL_DIR_ENV_MAP.get(str(name or "").strip().lower())
    if not env_key:
        return None

    env_value = str(os.environ.get(env_key) or "").strip()
    if env_value:
        return _expand_special_directory_value(env_value, home)

    user_dirs_path = home / ".config" / "user-dirs.dirs"
    try:
        contents = user_dirs_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    match = re.search(rf"(?m)^\s*{re.escape(env_key)}\s*=\s*(.+?)\s*$", contents)
    if not match:
        return None
    return _expand_special_directory_value(match.group(1), home)


def _resolve_special_directory_home_child(name: str, default_child: str) -> Path:
    home = _filesystem_home_dir()
    override = _resolve_special_directory_override(name, home)
    if override is not None:
        return override
    return home / default_child


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


def _is_placeholder_filesystem_path(candidate: str) -> bool:
    normalized = str(candidate or "").strip().lower().replace("/", "\\")
    if not normalized:
        return False
    if normalized.startswith("c:\\path\\to\\"):
        return True
    if normalized.startswith("\\path\\to\\"):
        return True
    if normalized.startswith("path\\to\\"):
        return True
    if "\\path\\to\\" in normalized and re.search(r"(?i)\\file\.[a-z0-9]{1,8}$", normalized):
        return True
    return False


def _extract_explicit_path_candidate(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    quoted = re.findall(r"[\"'`]+([^\"'`]+)[\"'`]+", raw)
    for candidate in quoted:
        cleaned = _trim_candidate_after_filelike(_normalize_filesystem_candidate(candidate))
        if cleaned and (_FILELIKE_QUERY_RE.search(cleaned) or _PATHLIKE_QUERY_RE.search(cleaned)):
            if not _is_placeholder_filesystem_path(cleaned):
                return cleaned

    path_match = _PATHLIKE_QUERY_RE.search(raw)
    if path_match:
        cleaned = _trim_candidate_after_filelike(_normalize_filesystem_candidate(path_match.group(1)))
        if cleaned and not _is_placeholder_filesystem_path(cleaned):
            return cleaned

    relative_file_match = _RELATIVE_FILE_PATH_RE.search(raw)
    if relative_file_match:
        cleaned = _trim_candidate_after_filelike(
            _normalize_filesystem_candidate(relative_file_match.group(1))
        )
        if cleaned and not _is_placeholder_filesystem_path(cleaned):
            return cleaned

    relative_dir_match = _RELATIVE_DIRECTORY_PATH_RE.search(raw)
    if relative_dir_match:
        cleaned = _normalize_filesystem_candidate(relative_dir_match.group(1))
        if cleaned and not _is_placeholder_filesystem_path(cleaned):
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


def _looks_like_windows_rooted_path(path: str | None) -> bool:
    candidate = str(path or "").strip()
    if not candidate:
        return False
    return bool(re.match(r"(?i)^(?:[a-z]:[\\/]|\\\\)", candidate))


def _join_context_path(base_path: str, child_path: str) -> str:
    base = str(base_path or "").strip()
    child = str(child_path or "").strip()
    if not base:
        return child
    if not child:
        return base
    if _looks_like_windows_rooted_path(base):
        return str(PureWindowsPath(base) / PureWindowsPath(child))
    return str(Path(base) / child)


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


def _resolve_special_directory_path(text: str) -> str | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None
    if re.search(
        r"(?i)\b(current (?:working )?(?:directory|folder)|working directory|current dir|cwd|this folder|this directory)\b|folder kerja saat ini|direktori kerja saat ini|folder saat ini|direktori saat ini|folder ini|direktori ini",
        normalized,
    ):
        return str(Path.cwd().expanduser().resolve())
    if re.search(r"(?i)\bdesktop\b|\u684c\u9762|\u30c7\u30b9\u30af\u30c8\u30c3\u30d7|\u0e40\u0e14\u0e2a\u0e01\u0e4c\u0e17\u0e47\u0e2d\u0e1b", normalized):
        return str(_resolve_special_directory_home_child("desktop", "Desktop"))
    if re.search(r"(?i)\bdownloads?\b|\u4e0b\u8f7d|\u4e0b\u8f09|\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9|\u0e14\u0e32\u0e27\u0e19\u0e4c\u0e42\u0e2b\u0e25\u0e14", normalized):
        return str(_resolve_special_directory_home_child("downloads", "Downloads"))
    if re.search(r"(?i)\bdocuments?\b|\bdocs\b|\u6587\u6863|\u6587\u4ef6\u6863\u6848|\u6587\u4ef6\u6a94\u6848|\u66f8\u985e|\u30c9\u30ad\u30e5\u30e1\u30f3\u30c8|\u0e40\u0e2d\u0e01\u0e2a\u0e32\u0e23", normalized):
        return str(_resolve_special_directory_home_child("documents", "Documents"))
    if re.search(r"(?i)\bpictures?\b|\bphotos?\b", normalized):
        return str(_resolve_special_directory_home_child("pictures", "Pictures"))
    if re.search(r"(?i)\bmusic\b", normalized):
        return str(_resolve_special_directory_home_child("music", "Music"))
    if re.search(r"(?i)\bvideos?\b", normalized):
        return str(_resolve_special_directory_home_child("videos", "Videos"))
    if re.search(r"(?i)\bhome\b", normalized):
        return str(_filesystem_home_dir())
    return None


def _extract_relative_directory_candidate(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    command_match = _RELATIVE_DIRECTORY_COMMAND_RE.search(raw)
    if command_match:
        command_candidate = _normalize_filesystem_candidate(command_match.group(1))
        command_candidate = command_candidate.rstrip("\\/").strip()
        if command_candidate:
            if re.match(r"(?i)^(?:[a-z]:[\\/]|\\\\|/|~[\\/])", command_candidate):
                return None
            if re.search(r"(?i)\.(?:com|net|org|io|ai|co|id|app|dev)$", command_candidate):
                return None
            if not command_candidate.isdigit():
                return command_candidate

    match = _RELATIVE_DIRECTORY_QUERY_RE.search(raw)
    if not match:
        return None
    candidate = _normalize_filesystem_candidate(match.group(1))
    if not candidate:
        return None
    candidate = _RELATIVE_DIRECTORY_SUFFIX_RE.sub("", candidate).strip(" ,.;:!?")
    candidate = candidate.rstrip("\\/").strip()
    if not candidate:
        return None
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
    file_match = _FILELIKE_QUERY_RE.search(raw)

    if explicit_path:
        explicit_suffix = Path(str(explicit_path).rstrip("\\/")).suffix.lower()
        # When the extracted explicit path is directory-shaped but the sentence
        # also includes an explicit filename token, prefer the filename token.
        # This avoids cases like: "kirim file X di folder bot\\ kesini"
        # being interpreted as path "bot\\ kesini".
        if not explicit_suffix and file_match:
            cleaned_file = _normalize_filesystem_candidate(file_match.group(0))
            if cleaned_file:
                return cleaned_file
        return explicit_path

    # Finally, plain filename.ext tokens.
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
    fallback_dir_path = fallback_path
    if fallback_dir_path:
        try:
            fallback_obj = Path(fallback_dir_path)
            if fallback_obj.suffix:
                fallback_dir_path = str(fallback_obj.parent)
        except Exception:
            pass

    explicit_path = _extract_explicit_path_candidate(raw)
    if explicit_path:
        trimmed_explicit = str(explicit_path).strip().rstrip("\\/")
        if Path(trimmed_explicit).suffix:
            return None
        if fallback_dir_path and trimmed_explicit and not re.match(r"(?i)^(?:[a-z]:[\\/]|\\\\|/|~[\\/])", trimmed_explicit):
            explicit_parts = [part for part in re.split(r"[\\/]", trimmed_explicit) if part]
            if len(explicit_parts) == 1:
                fallback_name = (
                    PureWindowsPath(fallback_dir_path).name.strip().lower()
                    if _looks_like_windows_rooted_path(fallback_dir_path)
                    else Path(fallback_dir_path).name.strip().lower()
                )
                if fallback_name and fallback_name == explicit_parts[0].lower():
                    return fallback_dir_path
            return _join_context_path(fallback_dir_path, trimmed_explicit)
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
        path_hint_match = _SPECIAL_DIR_PATH_HINT_RE.search(normalized_raw)
        if path_hint_match:
            nested_candidate = _normalize_filesystem_candidate(path_hint_match.group(1))
            normalized_nested = _normalize_text(nested_candidate)
            if (
                nested_candidate
                and not nested_candidate.isdigit()
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
        return _join_context_path(special_dir, relative_dir)
    if special_dir:
        return special_dir
    if relative_dir and fallback_dir_path:
        fallback_name = (
            PureWindowsPath(fallback_dir_path).name.strip().lower()
            if _looks_like_windows_rooted_path(fallback_dir_path)
            else Path(fallback_dir_path).name.strip().lower()
        )
        if fallback_name and fallback_name == relative_dir.strip().lower():
            return fallback_dir_path
        return _join_context_path(fallback_dir_path, relative_dir)

    if fallback_dir_path and _is_low_information_followup(raw):
        return fallback_dir_path

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
