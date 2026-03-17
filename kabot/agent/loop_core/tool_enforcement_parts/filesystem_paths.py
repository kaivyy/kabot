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
    r"(?i)\s+(?:now|please|show|display|list|"
    r"open|enter|read|again|pc|"
    r"chat\s+here|to\s+(?:this\s+)?chat|to\s+(?:this\s+)?channel|channel\s+here)$"
)
_RELATIVE_DIRECTORY_QUERY_RE = re.compile(
    r"(?i)(?:\b(?:subfolder|folder|directory|dir)\b|文件夹|文件夾|资料夹|資料夾|目录|目錄|フォルダ|ディレクトリ|โฟลเดอร์|ไดเรกทอรี)\s+(.+)$"
)
_RELATIVE_DIRECTORY_COMMAND_RE = re.compile(
    r"(?i)^\s*(?:open|enter|cd|chdir|goto|go\s+to|list|show)\s+([A-Za-z0-9._\\/-]+)\s*$"
)
_RELATIVE_DIRECTORY_SUFFIX_RE = re.compile(
    r"(?i)\s+(?:what\b.*|which\b.*|show\b.*|display\b.*|list\b.*|open\b.*|please\b.*|to\s+(?:this\s+)?chat\b.*|chat\s+here\b.*|channel\s+here\b.*|最初.*|件だけ.*|รายการ.*)$"
)
_SPECIAL_DIR_SUBFOLDER_PATTERNS = (
    re.compile(r"(?i)desktop(?:の|的)\s*([A-Za-z0-9._-]+)\s*(?:folder|directory|dir)\b"),
    re.compile(r"(?i)\bdesktop\b(?:\s+|[/\\]|-|\u2014|\u2013|of|inside|in|の|的)?\s*([A-Za-z0-9._-]+)\s*(?:folder|directory|dir)\b"),
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
    r"(?i)\b(?:(?:yes)\s+)?(?:(?:use|with|via)\s+)?path\s+"
    r"(?:desktop|downloads?|documents?|docs|pictures?|photos?|music|videos?|home)\b\s+([A-Za-z0-9._-]+)\b"
)
_SPECIAL_DIR_PREFIX_RE = re.compile(
    r"(?i)^\s*(?:desktop|downloads?|documents?|docs|pictures?|photos?|music|videos?|home)\b"
)
_CURRENT_DIR_REQUEST_RE = re.compile(
    r"(?i)\b(current (?:working )?(?:directory|folder)|working directory|current dir|cwd|this folder|this directory)\b"
)
_SPECIAL_DIR_DESKTOP_RE = re.compile(
    r"(?i)\bdesktop\b|\u684c\u9762|\u30c7\u30b9\u30af\u30c8\u30c3\u30d7|\u0e40\u0e14\u0e2a\u0e01\u0e4c\u0e17\u0e47\u0e2d\u0e1b"
)
_SPECIAL_DIR_DOWNLOADS_RE = re.compile(
    r"(?i)\bdownloads?\b|\u4e0b\u8f7d|\u4e0b\u8f09|\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9|\u0e14\u0e32\u0e27\u0e19\u0e4c\u0e42\u0e2b\u0e25\u0e14"
)
_SPECIAL_DIR_DOCUMENTS_RE = re.compile(
    r"(?i)\bdocuments?\b|\bdocs\b|\u6587\u6863|\u6587\u4ef6\u6863\u6848|\u6587\u4ef6\u6a94\u6848|\u66f8\u985e|\u30c9\u30ad\u30e5\u30e1\u30f3\u30c8|\u0e40\u0e2d\u0e01\u0e2a\u0e32\u0e23"
)
_SPECIAL_DIR_PICTURES_RE = re.compile(r"(?i)\bpictures?\b|\bphotos?\b")
_SPECIAL_DIR_MUSIC_RE = re.compile(r"(?i)\bmusic\b")
_SPECIAL_DIR_VIDEOS_RE = re.compile(r"(?i)\bvideos?\b")
_SPECIAL_DIR_HOME_RE = re.compile(r"(?i)\bhome\b")
_SPECIAL_DIR_CONTEXT_NOUN_RE = re.compile(
    r"(?i)\b(?:folder|directory|dir|path|file(?:/folder)?|files?|contents?|content|listing)\b|"
    r"文件夹|文件夾|資料夾|目录|目錄|文件|檔案|内容|內容|フォルダ|ディレクトリ|ファイル|内容|中|โฟลเดอร์|ไดเรกทอรี|ไฟล์|เนื้อหา"
)
_SPECIAL_DIR_ACTION_RE = re.compile(
    r"(?i)\b(?:open|enter|show|display|list|check|inspect|view|read|"
    r"send|share|attach|upload|find|search|locate|use\s+path)\b|"
    r"\u663e\u793a|\u6253\u5f00|\u958b\u555f|\u8868\u793a|\u958b\u3044\u3066|\u958b\u304f|\u898b\u305b\u3066|\u958b\u3051\u3066|"
    r"\u0e40\u0e1b\u0e34\u0e14|\u0e14\u0e39|\u0e41\u0e2a\u0e14\u0e07"
)
_SPECIAL_DIR_PREPOSITION_RE = re.compile(
    r"(?i)\b(?:in|inside|from|to|under|within)\b|"
    r"\u5185|\u91cc|\u88e1|\u4e2d|\u306e|\u306b|\u304b\u3089|\u3078|\u0e43\u0e19|\u0e08\u0e32\u0e01|\u0e44\u0e1b\u0e17\u0e35\u0e48"
)
_SPECIAL_DIR_TERMINAL_TAIL_RE = re.compile(
    r"(?i)^\s*(?:folder|directory|dir|path|files?|contents?|content|listing|pc|computer|laptop|"
    r"please|now|here|chat\s+here|to\s+(?:this\s+)?chat|"
    r"to\s+(?:this\s+)?channel|channel\s+here|"
    r"\u6587\u4ef6\u5939|\u6587\u4ef6\u593e|\u8cc7\u6599\u593e|\u76ee\u5f55|\u76ee\u9304|\u30d5\u30a9\u30eb\u30c0|"
    r"\u30c7\u30a3\u30ec\u30af\u30c8\u30ea|\u30d5\u30a1\u30a4\u30eb|\u30d1\u30b9|\u0e42\u0e1f\u0e25\u0e40\u0e14\u0e2d\u0e23\u0e4c|"
    r"\u0e44\u0e14\u0e40\u0e23\u0e01\u0e17\u0e2d\u0e23\u0e35|\u0e44\u0e1f\u0e25\u0e4c|\u0e17\u0e35\u0e48\u0e19\u0e35\u0e48|"
    r"\u6700\u521d.*|\u4ef6\u3060\u3051.*|\u5217\u8868.*|\u0e23\u0e32\u0e22\u0e01\u0e32\u0e23.*)?\s*$"
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
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return None
    if _CURRENT_DIR_REQUEST_RE.search(normalized):
        return str(Path.cwd().expanduser().resolve())
    if _special_directory_match_has_payload_context(raw, normalized, _SPECIAL_DIR_DESKTOP_RE):
        return str(_resolve_special_directory_home_child("desktop", "Desktop"))
    if _special_directory_match_has_payload_context(raw, normalized, _SPECIAL_DIR_DOWNLOADS_RE):
        return str(_resolve_special_directory_home_child("downloads", "Downloads"))
    if _special_directory_match_has_payload_context(raw, normalized, _SPECIAL_DIR_DOCUMENTS_RE):
        return str(_resolve_special_directory_home_child("documents", "Documents"))
    if _special_directory_match_has_payload_context(raw, normalized, _SPECIAL_DIR_PICTURES_RE):
        return str(_resolve_special_directory_home_child("pictures", "Pictures"))
    if _special_directory_match_has_payload_context(raw, normalized, _SPECIAL_DIR_MUSIC_RE):
        return str(_resolve_special_directory_home_child("music", "Music"))
    if _special_directory_match_has_payload_context(raw, normalized, _SPECIAL_DIR_VIDEOS_RE):
        return str(_resolve_special_directory_home_child("videos", "Videos"))
    if _special_directory_match_has_payload_context(raw, normalized, _SPECIAL_DIR_HOME_RE):
        return str(_filesystem_home_dir())
    return None


def _special_directory_match_has_payload_context(
    raw: str,
    normalized_raw: str,
    token_re: re.Pattern[str],
) -> bool:
    match = token_re.search(normalized_raw)
    if not match:
        return False
    if _SPECIAL_DIR_PATH_HINT_RE.search(normalized_raw):
        return True
    if any(pattern.search(raw) for pattern in _SPECIAL_DIR_SUBFOLDER_PATTERNS):
        return True
    if _SPECIAL_DIR_NORMALIZED_SUBFOLDER_RE.search(normalized_raw):
        return True

    window_start = max(0, match.start() - 32)
    window_end = min(len(raw), match.end() + 48)
    local_window = raw[window_start:window_end]
    if _SPECIAL_DIR_CONTEXT_NOUN_RE.search(local_window):
        return True

    before = raw[max(0, match.start() - 24) : match.start()]
    if _SPECIAL_DIR_PREPOSITION_RE.search(before) and _SPECIAL_DIR_ACTION_RE.search(normalized_raw):
        return True

    if _SPECIAL_DIR_ACTION_RE.search(normalized_raw):
        tail = raw[match.end() :]
        tail = _FILESYSTEM_TRAILING_TAIL_RE.sub("", tail).strip()
        if not tail:
            return True
        if _SPECIAL_DIR_TERMINAL_TAIL_RE.fullmatch(tail):
            return True
    return False


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
            if _normalize_text(command_candidate) in _FILESYSTEM_TARGET_MARKERS:
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
    candidate = re.split(r"[,;:!?]", candidate, maxsplit=1)[0].strip()
    candidate = candidate.rstrip("\\/").strip()
    candidate = re.sub(
        r"(?i)\s+(?:in|inside|within|under)\s+"
        r"(?:workspace|current working directory|working directory|current dir|cwd)\b.*$",
        "",
        candidate,
    ).strip()
    if not candidate:
        return None
    if any(sep in candidate for sep in ("/", "\\")):
        return None
    normalized = _normalize_text(candidate)
    if normalized.startswith(("in ", "inside ")):
        return None
    tokens = [token for token in normalized.split() if token]
    if len(tokens) > 3:
        head_candidate = tokens[0] if tokens else ""
        if (
            head_candidate
            and not head_candidate.isdigit()
            and re.fullmatch(r"[A-Za-z0-9._-]+", head_candidate)
            and head_candidate not in _FILESYSTEM_TARGET_MARKERS
        ):
            return head_candidate
        return None
    if any(
        token in {
            "yang",
            "apa",
            "what",
            "which",
            "please",
            "check",
            "show",
        }
        for token in tokens
    ):
        return None
    if re.match(
        r"(?i)^\d+\s*(?:item|items|entry|entries|line|file|files|folder|folders)\b",
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
        # This avoids cases like: "send file X in folder bot\\ here"
        # being interpreted as path "bot\\ here".
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
    if relative_dir:
        return relative_dir

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
