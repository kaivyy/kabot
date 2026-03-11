"""File system tools: read, write, edit, and search."""

import fnmatch
import os
import zipfile
from pathlib import Path
from typing import Any

from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.tools.base import Tool


def _resolve_path(path: str, allowed_dir: Path | None = None) -> Path:
    """Resolve path and optionally enforce directory restriction."""
    resolved = Path(path).expanduser().resolve()
    if allowed_dir and not str(resolved).startswith(str(allowed_dir.resolve())):
        raise PermissionError(f"Path {path} is outside allowed directory {allowed_dir}")
    return resolved


def _resolve_search_root(path: str | None, allowed_dir: Path | None = None) -> Path:
    if path:
        return _resolve_path(path, allowed_dir)
    if allowed_dir:
        return allowed_dir.expanduser().resolve()
    return Path.home().expanduser().resolve()


def _matches_find_query(name: str, query: str) -> bool:
    candidate = str(name or "").strip().lower()
    needle = str(query or "").strip().lower()
    if not candidate or not needle:
        return False
    if any(token in needle for token in ("*", "?", "[")):
        return fnmatch.fnmatch(candidate, needle)
    return needle in candidate


def _default_archive_path(source_path: Path) -> Path:
    return source_path.parent / f"{source_path.name}.zip"


class ReadFileTool(Tool):
    """Tool to read file contents."""

    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file at the given path."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to read"
                }
            },
            "required": ["path"]
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._allowed_dir)
            if not file_path.exists():
                return i18n_t("filesystem.file_not_found", path, path=path)
            if not file_path.is_file():
                return i18n_t("filesystem.not_file", path, path=path)

            content = file_path.read_text(encoding="utf-8")
            return content
        except PermissionError as e:
            return i18n_t("filesystem.permission_denied", path, error=str(e))
        except Exception as e:
            return i18n_t("filesystem.read_error", path, error=str(e))


class WriteFileTool(Tool):
    """Tool to write content to a file."""

    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file at the given path. Creates parent directories if needed."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to write to"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write"
                }
            },
            "required": ["path", "content"]
        }

    async def execute(self, path: str, content: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._allowed_dir)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} bytes to {path}"
        except PermissionError as e:
            return i18n_t("filesystem.permission_denied", path, error=str(e))
        except Exception as e:
            return i18n_t("filesystem.write_error", path, error=str(e))


class ArchivePathTool(Tool):
    """Tool to archive a file or directory into a zip file."""

    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "archive_path"

    @property
    def description(self) -> str:
        return "Archive a local file or folder into a .zip file and return the created archive path."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file or directory path to archive"
                },
                "archive_path": {
                    "type": "string",
                    "description": "Optional output .zip path. Defaults to <path>.zip next to the source."
                },
            },
            "required": ["path"]
        }

    async def execute(self, path: str, archive_path: str | None = None, **kwargs: Any) -> str:
        try:
            source_path = _resolve_path(path, self._allowed_dir)
            if not source_path.exists():
                return i18n_t("filesystem.file_not_found", path, path=path)

            target_path = (
                _resolve_path(archive_path, self._allowed_dir)
                if archive_path
                else _default_archive_path(source_path)
            )
            target_path.parent.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                if source_path.is_file():
                    archive.write(source_path, arcname=source_path.name)
                else:
                    entries = sorted(source_path.rglob("*"))
                    if not entries:
                        archive.writestr(f"{source_path.name}/", "")
                    for item in entries:
                        relative = item.relative_to(source_path)
                        arcname = str(Path(source_path.name) / relative).replace("\\", "/")
                        if item.is_dir():
                            if not any(item.iterdir()):
                                archive.writestr(f"{arcname}/", "")
                            continue
                        archive.write(item, arcname=arcname)

            return f"Created archive {target_path} from {source_path}"
        except PermissionError as e:
            return i18n_t("filesystem.permission_denied", path, error=str(e))
        except Exception as e:
            return i18n_t("filesystem.write_error", path, error=str(e))


class EditFileTool(Tool):
    """Tool to edit a file by replacing text."""

    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return "Edit a file by replacing old_text with new_text. The old_text must exist exactly in the file."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to edit"
                },
                "old_text": {
                    "type": "string",
                    "description": "The exact text to find and replace"
                },
                "new_text": {
                    "type": "string",
                    "description": "The text to replace with"
                }
            },
            "required": ["path", "old_text", "new_text"]
        }

    async def execute(self, path: str, old_text: str, new_text: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._allowed_dir)
            if not file_path.exists():
                return i18n_t("filesystem.file_not_found", path, path=path)

            content = file_path.read_text(encoding="utf-8")

            if old_text not in content:
                # Check for common whitespace issues
                if old_text.strip() in content:
                    return i18n_t("filesystem.old_text_not_found_exact", old_text)

                # Provide a snippet of the file to help the AI find the right context
                snippet = content[:500] + "..." if len(content) > 500 else content
                return i18n_t("filesystem.old_text_not_found", old_text, path=path, snippet=snippet)

            # Count occurrences
            count = content.count(old_text)
            if count > 1:
                return i18n_t("filesystem.old_text_ambiguous", old_text, count=count)

            new_content = content.replace(old_text, new_text, 1)
            file_path.write_text(new_content, encoding="utf-8")

            return f"Successfully edited {path}"
        except PermissionError as e:
            return i18n_t("filesystem.permission_denied", path, error=str(e))
        except Exception as e:
            return i18n_t("filesystem.edit_error", path, error=str(e))


class ListDirTool(Tool):
    """Tool to list directory contents."""

    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return "List the contents of a directory."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to list"
                },
                "limit": {
                    "type": "integer",
                    "description": "Optional maximum number of entries to return"
                },
            },
            "required": ["path"]
        }

    async def execute(self, path: str, limit: int | None = None, **kwargs: Any) -> str:
        try:
            dir_path = _resolve_path(path, self._allowed_dir)
            if not dir_path.exists():
                return i18n_t("filesystem.directory_not_found", path, path=path)
            if not dir_path.is_dir():
                return i18n_t("filesystem.not_directory", path, path=path)

            items = []
            for item in sorted(dir_path.iterdir()):
                prefix = "📁 " if item.is_dir() else "📄 "
                items.append(f"{prefix}{item.name}")

            if limit is not None:
                try:
                    limit_value = int(limit)
                except Exception:
                    limit_value = 0
                if limit_value > 0:
                    items = items[:limit_value]

            if not items:
                return i18n_t("filesystem.directory_empty", path, path=path)

            return "\n".join(items)
        except PermissionError as e:
            return i18n_t("filesystem.permission_denied", path, error=str(e))
        except Exception as e:
            return i18n_t("filesystem.list_error", path, error=str(e))


class FindFilesTool(Tool):
    """Tool to search files and folders by name."""

    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "find_files"

    @property
    def description(self) -> str:
        return (
            "Search for files or folders by name, partial name, or glob pattern. "
            "Use this when the user asks you to find a file/folder before reading or sending it."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The file or folder name to search for. Supports partial matches and glob patterns like *.pdf.",
                },
                "path": {
                    "type": "string",
                    "description": "Optional root directory to search from. Defaults to the allowed directory or the user's home directory.",
                },
                "kind": {
                    "type": "string",
                    "description": "Optional result type filter: any, file, or dir.",
                    "enum": ["any", "file", "dir"],
                },
                "limit": {
                    "type": "integer",
                    "description": "Optional maximum number of matches to return.",
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        path: str | None = None,
        kind: str = "any",
        limit: int | None = None,
        **kwargs: Any,
    ) -> str:
        search_query = str(query or "").strip()
        if not search_query:
            return i18n_t("filesystem.need_query", str(kwargs.get("context_text") or query or ""))

        try:
            root = _resolve_search_root(path, self._allowed_dir)
            if not root.exists():
                return i18n_t("filesystem.directory_not_found", str(path or root), path=str(path or root))
            if not root.is_dir():
                return i18n_t("filesystem.not_directory", str(path or root), path=str(path or root))

            result_kind = str(kind or "any").strip().lower()
            if result_kind not in {"any", "file", "dir"}:
                result_kind = "any"

            try:
                max_results = int(limit) if limit is not None else 10
            except Exception:
                max_results = 10
            if max_results <= 0:
                max_results = 10

            matches: list[str] = []
            for current_root, dir_names, file_names in os.walk(root):
                current_path = Path(current_root)
                if result_kind in {"any", "dir"}:
                    for dir_name in sorted(dir_names):
                        if not _matches_find_query(dir_name, search_query):
                            continue
                        matches.append(f"DIR {(current_path / dir_name).resolve()}")
                        if len(matches) >= max_results:
                            return "\n".join(matches)
                if result_kind in {"any", "file"}:
                    for file_name in sorted(file_names):
                        if not _matches_find_query(file_name, search_query):
                            continue
                        matches.append(f"FILE {(current_path / file_name).resolve()}")
                        if len(matches) >= max_results:
                            return "\n".join(matches)

            if not matches:
                return i18n_t("filesystem.no_matches", search_query, query=search_query)
            return "\n".join(matches)
        except PermissionError as e:
            return i18n_t("filesystem.permission_denied", search_query, error=str(e))
        except Exception as e:
            return i18n_t("filesystem.search_error", search_query, error=str(e))
