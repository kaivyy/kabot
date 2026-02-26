from pathlib import Path

from kabot.utils.workspace_templates import ensure_workspace_templates


def test_ensure_workspace_templates_creates_required_files(tmp_path: Path):
    workspace = tmp_path / "workspace"

    created = ensure_workspace_templates(workspace)

    assert created
    assert (workspace / "AGENTS.md").exists()
    assert (workspace / "SOUL.md").exists()
    assert (workspace / "USER.md").exists()
    assert (workspace / "memory" / "MEMORY.md").exists()


def test_ensure_workspace_templates_is_idempotent(tmp_path: Path):
    workspace = tmp_path / "workspace"

    first = ensure_workspace_templates(workspace)
    second = ensure_workspace_templates(workspace)

    assert first
    assert second == []
