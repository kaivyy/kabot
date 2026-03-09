"""File system tools: read, write, edit."""

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
