from pathlib import Path

from kabot.utils.workspace_templates import ensure_workspace_templates


def test_ensure_workspace_templates_creates_required_files(tmp_path: Path):
    workspace = tmp_path / "workspace"

    created = ensure_workspace_templates(workspace)

    assert created
    assert (workspace / "AGENTS.md").exists()
    assert (workspace / "SOUL.md").exists()
    assert (workspace / "TOOLS.md").exists()
    assert (workspace / "USER.md").exists()
    assert (workspace / "IDENTITY.md").exists()
    assert (workspace / "BOOTSTRAP.md").exists()
    assert (workspace / "memory" / "MEMORY.md").exists()
    assert len(created) >= 7


def test_ensure_workspace_templates_use_openclaw_style_bootstrap_language(tmp_path: Path):
    workspace = tmp_path / "workspace"

    ensure_workspace_templates(workspace)

    bootstrap = (workspace / "BOOTSTRAP.md").read_text(encoding="utf-8")
    soul = (workspace / "SOUL.md").read_text(encoding="utf-8")
    tools = (workspace / "TOOLS.md").read_text(encoding="utf-8")
    identity = (workspace / "IDENTITY.md").read_text(encoding="utf-8")
    user = (workspace / "USER.md").read_text(encoding="utf-8")

    assert "Who am I" in bootstrap
    assert "Delete this file" in bootstrap
    assert "You're not a chatbot" in soul
    assert "local cheat sheet" in tools
    assert "Creature" in identity
    assert "What to call them" in user


def test_ensure_workspace_templates_is_idempotent(tmp_path: Path):
    workspace = tmp_path / "workspace"

    first = ensure_workspace_templates(workspace)
    second = ensure_workspace_templates(workspace)

    assert first
    assert second == []


def test_ensure_workspace_templates_uses_stable_persona_seed_for_same_workspace(
    tmp_path: Path,
):
    workspace = tmp_path / "workspace"

    ensure_workspace_templates(workspace)
    first_soul = (workspace / "SOUL.md").read_text(encoding="utf-8")
    first_bootstrap = (workspace / "BOOTSTRAP.md").read_text(encoding="utf-8")

    for path in workspace.iterdir():
        if path.is_file():
            path.unlink()
    (workspace / "memory" / "MEMORY.md").unlink(missing_ok=True)
    if (workspace / "memory").exists():
        (workspace / "memory").rmdir()

    ensure_workspace_templates(workspace)
    second_soul = (workspace / "SOUL.md").read_text(encoding="utf-8")
    second_bootstrap = (workspace / "BOOTSTRAP.md").read_text(encoding="utf-8")

    assert first_soul == second_soul
    assert first_bootstrap == second_bootstrap


def test_ensure_workspace_templates_varies_persona_between_workspaces(tmp_path: Path):
    alpha = tmp_path / "workspace-alpha"
    beta = tmp_path / "workspace-beta"

    ensure_workspace_templates(alpha)
    ensure_workspace_templates(beta)

    alpha_soul = (alpha / "SOUL.md").read_text(encoding="utf-8")
    beta_soul = (beta / "SOUL.md").read_text(encoding="utf-8")
    alpha_bootstrap = (alpha / "BOOTSTRAP.md").read_text(encoding="utf-8")
    beta_bootstrap = (beta / "BOOTSTRAP.md").read_text(encoding="utf-8")

    assert alpha_soul != beta_soul
    assert alpha_bootstrap != beta_bootstrap
