"""Tests for bootstrap parity utilities."""

from pathlib import Path

from kabot.utils.bootstrap_parity import (
    BootstrapParityPolicy,
    apply_bootstrap_fixes,
    check_bootstrap_parity,
)


def test_check_bootstrap_parity_marks_missing_files_as_critical(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    policy = BootstrapParityPolicy(
        enabled=True,
        required_files=["AGENTS.md", "SOUL.md"],
        baseline_dir=None,
        enforce_hash=False,
    )

    report = check_bootstrap_parity(workspace, policy)
    statuses = {item["file"]: item["status"] for item in report}
    assert statuses["AGENTS.md"] == "CRITICAL"
    assert statuses["SOUL.md"] == "CRITICAL"


def test_apply_bootstrap_fixes_copies_from_baseline_and_syncs_hash(tmp_path: Path):
    workspace = tmp_path / "workspace"
    baseline = tmp_path / "baseline"
    workspace.mkdir(parents=True, exist_ok=True)
    baseline.mkdir(parents=True, exist_ok=True)

    (baseline / "AGENTS.md").write_text("# Agent Instructions\n\nDo A.\n", encoding="utf-8")
    (baseline / "SOUL.md").write_text("# Soul\n\nDo B.\n", encoding="utf-8")
    (workspace / "SOUL.md").write_text("# Soul\n\nOld content.\n", encoding="utf-8")

    policy = BootstrapParityPolicy(
        enabled=True,
        required_files=["AGENTS.md", "SOUL.md"],
        baseline_dir=baseline,
        enforce_hash=True,
    )

    before = check_bootstrap_parity(workspace, policy)
    by_file = {item["file"]: item for item in before}
    assert by_file["AGENTS.md"]["status"] == "CRITICAL"
    assert by_file["SOUL.md"]["status"] == "WARN"

    changes = apply_bootstrap_fixes(workspace, policy, sync_mismatch=True)
    assert any("AGENTS.md" in change for change in changes)
    assert any("SOUL.md" in change for change in changes)
    assert (workspace / "AGENTS.md").read_text(encoding="utf-8") == (baseline / "AGENTS.md").read_text(encoding="utf-8")
    assert (workspace / "SOUL.md").read_text(encoding="utf-8") == (baseline / "SOUL.md").read_text(encoding="utf-8")

    after = check_bootstrap_parity(workspace, policy)
    assert all(item["status"] == "OK" for item in after)

