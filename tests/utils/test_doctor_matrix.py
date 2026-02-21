"""Tests for doctor environment matrix and deeper fix coverage."""

from pathlib import Path


def test_doctor_environment_matrix_includes_recommended_mode(monkeypatch, tmp_path):
    from kabot.utils.doctor import KabotDoctor
    from kabot.utils.environment import RuntimeEnvironment

    doctor = KabotDoctor(agent_id="main")
    doctor.global_dir = tmp_path / "global"
    doctor.agent_dir = doctor.global_dir / "agents" / "main"

    runtime = RuntimeEnvironment(
        platform="linux",
        is_windows=False,
        is_macos=False,
        is_linux=True,
        is_wsl=False,
        is_termux=False,
        is_vps=True,
        is_headless=True,
        is_ci=False,
        has_display=False,
    )

    monkeypatch.setattr("kabot.utils.doctor.detect_runtime_environment", lambda: runtime)
    monkeypatch.setattr("kabot.utils.doctor.shutil.which", lambda cmd: None)
    async def _fake_connectivity():
        return []

    monkeypatch.setattr(doctor, "check_skills", lambda: {"eligible": [], "missing": []})
    monkeypatch.setattr(doctor, "check_dependencies", lambda: [])
    monkeypatch.setattr(doctor, "check_connectivity", _fake_connectivity)

    report = doctor.run_full_diagnostic(fix=False)
    assert "environment" in report
    matrix = report["environment"]
    assert any(item["item"] == "Recommended Gateway Mode" and "remote" in item["detail"] for item in matrix)


def test_doctor_fix_creates_logs_and_plugins_dirs(tmp_path):
    from kabot.utils.doctor import KabotDoctor

    doctor = KabotDoctor(agent_id="main")
    doctor.global_dir = tmp_path / "global"
    doctor.agent_dir = doctor.global_dir / "agents" / "main"
    doctor.workspace = doctor.agent_dir / "workspace"

    integrity = doctor.check_state_integrity()
    doctor.apply_fixes(integrity)

    assert (doctor.agent_dir / "logs").exists()
    assert (doctor.agent_dir / "workspace" / "plugins").exists()


def test_doctor_reports_bootstrap_parity_and_fixes_missing_files(tmp_path):
    from kabot.utils.bootstrap_parity import BootstrapParityPolicy
    from kabot.utils.doctor import KabotDoctor

    doctor = KabotDoctor(agent_id="main")
    doctor.global_dir = tmp_path / "global"
    doctor.agent_dir = doctor.global_dir / "agents" / "main"
    doctor.workspace = doctor.agent_dir / "workspace"
    doctor.bootstrap_policy = BootstrapParityPolicy(
        enabled=True,
        required_files=["AGENTS.md"],
        baseline_dir=None,
        enforce_hash=False,
    )

    doctor.workspace.mkdir(parents=True, exist_ok=True)

    report_before = doctor.check_bootstrap_parity()
    assert report_before[0]["status"] == "CRITICAL"

    doctor.apply_fixes([], report_before, sync_bootstrap=False)
    assert (doctor.workspace / "AGENTS.md").exists()

    report_after = doctor.check_bootstrap_parity()
    assert report_after[0]["status"] == "OK"
