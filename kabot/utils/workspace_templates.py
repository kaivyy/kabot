"""Workspace template bootstrap helpers."""

from __future__ import annotations

from pathlib import Path

DEFAULT_BOOTSTRAP_TEMPLATES: dict[str, str] = {
    "AGENTS.md": """# Agent Instructions

You are a helpful AI assistant. Be concise, accurate, and friendly.

## Guidelines

- Always explain what you're doing before taking actions
- Ask for clarification when the request is ambiguous
- Use tools to help accomplish tasks
- Remember important information in your memory files
""",
    "SOUL.md": """# Soul

I am kabot, a lightweight AI assistant.

## Personality

- Helpful and friendly
- Concise and to the point
- Curious and eager to learn

## Values

- Accuracy over speed
- User privacy and safety
- Transparency in actions
""",
    "USER.md": """# User

Information about the user goes here.

## Preferences

- Communication style: (casual/formal)
- Timezone: (your timezone)
- Language: (your preferred language)
""",
}


DEFAULT_MEMORY_TEMPLATE = """# Long-term Memory

This file stores important information that should persist across sessions.

## User Information

(Important facts about the user)

## Preferences

(User preferences learned over time)

## Important Notes

(Things to remember)
"""


def ensure_workspace_templates(workspace: Path) -> list[Path]:
    """Ensure baseline bootstrap files exist for a workspace.

    Returns list of files created in this call.
    """
    workspace.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    for filename, content in DEFAULT_BOOTSTRAP_TEMPLATES.items():
        file_path = workspace / filename
        if file_path.exists():
            continue
        file_path.write_text(content, encoding="utf-8")
        created.append(file_path)

    memory_dir = workspace / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text(DEFAULT_MEMORY_TEMPLATE, encoding="utf-8")
        created.append(memory_file)

    return created
