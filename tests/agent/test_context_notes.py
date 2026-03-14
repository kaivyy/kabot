from pathlib import Path
from types import SimpleNamespace

from kabot.agent.loop_core.message_runtime_parts.context_notes import (
    _build_grounded_filesystem_inspection_note,
    _build_session_continuity_action_note,
)


def test_build_session_continuity_action_note_surfaces_grounded_state(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    working_directory = workspace / "bot"
    working_directory.mkdir()
    recent_file = working_directory / "tes.md"
    recent_file.write_text("demo", encoding="utf-8")

    loop = SimpleNamespace(workspace=workspace)
    session = SimpleNamespace(
        metadata={
            "working_directory": str(working_directory),
            "delivery_route": {
                "channel": "telegram",
                "chat_id": "chat-1",
                "thread_id": "42",
            },
        }
    )

    note = _build_session_continuity_action_note(
        loop,
        session,
        last_tool_context={"tool": "list_dir", "path": str(working_directory)},
        pending_followup_tool="message",
        pending_followup_source="send tes.md here",
        recent_file_path=str(recent_file),
    )

    assert "Current working directory from session" in note
    assert str(working_directory) in note
    assert '"channel": "telegram"' in note
    assert "Do not rely on fixed language-specific keywords" in note
    assert str(recent_file) in note


def test_build_session_continuity_action_note_skips_empty_state(tmp_path):
    loop = SimpleNamespace(workspace=Path(tmp_path))
    session = SimpleNamespace(metadata={})

    note = _build_session_continuity_action_note(loop, session)

    assert note == ""


def test_build_grounded_filesystem_inspection_note_prefers_grounded_project_root(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project_dir = workspace / "openclaw"
    project_dir.mkdir()
    readme_path = project_dir / "README.md"
    readme_path.write_text("# OpenClaw", encoding="utf-8")

    loop = SimpleNamespace(workspace=workspace)
    session = SimpleNamespace(metadata={"working_directory": str(project_dir)})

    note = _build_grounded_filesystem_inspection_note(
        loop,
        session,
        last_tool_context={"tool": "list_dir", "path": str(project_dir)},
        recent_file_path=str(readme_path),
    )

    assert "[System Note: Grounded filesystem inspection]" in note
    assert f"Preferred inspection root: {project_dir}" in note
    assert "Start with list_dir, read_file, find_files, or exec" in note
    assert "Do not answer with a generic technology guess" in note
