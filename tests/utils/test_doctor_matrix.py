"""Tests for doctor environment matrix and deeper fix coverage."""



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


def test_doctor_parity_report_contains_mandatory_sections(monkeypatch, tmp_path):
    from kabot.utils.doctor import KabotDoctor

    doctor = KabotDoctor(agent_id="main")
    doctor.global_dir = tmp_path / "global"
    doctor.agent_dir = doctor.global_dir / "agents" / "main"
    doctor.workspace = doctor.agent_dir / "workspace"
    doctor.workspace.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(doctor, "_check_bridge_health", lambda: {"status": "down", "detail": "bridge not running"})
    report = doctor.run_parity_diagnostic()

    assert "runtime_resilience" in report
    assert "fallback_state_machine" in report
    assert "adapter_registry" in report
    assert "migration_status" in report
    assert "bridge_health" in report
    assert "skills_precedence" in report
    assert "soak_gate" in report


def test_doctor_parity_report_reads_soak_gate_file(tmp_path):
    from kabot.utils.doctor import KabotDoctor

    doctor = KabotDoctor(agent_id="main")
    doctor.global_dir = tmp_path / "global"
    doctor.agent_dir = doctor.global_dir / "agents" / "main"
    doctor.workspace = doctor.agent_dir / "workspace"
    doctor.workspace.mkdir(parents=True, exist_ok=True)
    logs_dir = doctor.global_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "soak_latest.json").write_text(
        """
{
  "runtime_hours": 24,
  "duplicate_side_effects": 0,
  "tool_protocol_breaks": 0,
  "p95_first_response_ms": 3500
}
""".strip(),
        encoding="utf-8",
    )

    report = doctor.run_parity_diagnostic()
    assert report["soak_gate"]["available"] is True
    assert report["soak_gate"]["passed"] is True


def test_doctor_parity_report_adapter_registry_includes_instance_health(monkeypatch, tmp_path):
    from kabot.config.schema import ChannelInstance, Config
    from kabot.utils.doctor import KabotDoctor

    doctor = KabotDoctor(agent_id="main")
    doctor.global_dir = tmp_path / "global"
    doctor.agent_dir = doctor.global_dir / "agents" / "main"
    doctor.workspace = doctor.agent_dir / "workspace"
    doctor.workspace.mkdir(parents=True, exist_ok=True)
    doctor.config = Config()
    doctor.config.channels.instances = [
        ChannelInstance(
            id="signal_ops",
            type="signal",
            enabled=True,
            config={"bridge_url": "ws://localhost:3011", "allow_from": []},
        )
    ]
    monkeypatch.setattr(doctor, "_bridge_url_reachable", lambda _url: True)

    report = doctor.run_parity_diagnostic()
    adapter = report["adapter_registry"]

    assert adapter["configured_instances"] == 1
    assert adapter["instance_channels"][0]["key"] == "signal:signal_ops"
    assert adapter["instance_channels"][0]["reachable"] is True
    assert adapter["instance_channels"][0]["constructable"] is True
    assert adapter["instance_channels"][0]["status"] == "ready"
    assert adapter["ready_instances"] == 1
    assert adapter["not_ready_instances"] == 0
    assert "legacy_channels" in adapter


def test_doctor_parity_report_adapter_registry_marks_unreachable_bridge(monkeypatch, tmp_path):
    from kabot.config.schema import ChannelInstance, Config
    from kabot.utils.doctor import KabotDoctor

    doctor = KabotDoctor(agent_id="main")
    doctor.global_dir = tmp_path / "global"
    doctor.agent_dir = doctor.global_dir / "agents" / "main"
    doctor.workspace = doctor.agent_dir / "workspace"
    doctor.workspace.mkdir(parents=True, exist_ok=True)
    doctor.config = Config()
    doctor.config.channels.instances = [
        ChannelInstance(
            id="signal_ops",
            type="signal",
            enabled=True,
            config={"bridge_url": "ws://localhost:3011", "allow_from": []},
        )
    ]
    monkeypatch.setattr(doctor, "_bridge_url_reachable", lambda _url: False)

    report = doctor.run_parity_diagnostic()
    adapter = report["adapter_registry"]
    row = adapter["instance_channels"][0]

    assert row["status"] == "not_ready"
    assert "bridge_unreachable" in row["reasons"]
    assert adapter["not_ready_instances"] == 1
    assert adapter["instance_reason_counts"]["bridge_unreachable"] == 1


def test_doctor_parity_report_adapter_registry_marks_disabled_legacy(monkeypatch, tmp_path):
    from kabot.config.schema import Config
    from kabot.utils.doctor import KabotDoctor

    doctor = KabotDoctor(agent_id="main")
    doctor.global_dir = tmp_path / "global"
    doctor.agent_dir = doctor.global_dir / "agents" / "main"
    doctor.workspace = doctor.agent_dir / "workspace"
    doctor.workspace.mkdir(parents=True, exist_ok=True)
    doctor.config = Config()
    doctor.config.channels.adapters = {"telegram": False}
    doctor.config.channels.telegram.enabled = True
    doctor.config.channels.telegram.token = "dummy"

    report = doctor.run_parity_diagnostic()
    adapter = report["adapter_registry"]
    rows = [row for row in adapter["legacy_channels"] if row["key"] == "telegram"]
    assert rows
    row = rows[0]

    assert row["status"] == "not_ready"
    assert "adapter_disabled_by_flag" in row["reasons"]
    assert adapter["not_ready_legacy"] >= 1


def test_doctor_routing_diagnostic_has_expected_sanity_matrix(tmp_path):
    from kabot.utils.doctor import KabotDoctor

    doctor = KabotDoctor(agent_id="main")
    doctor.global_dir = tmp_path / "global"
    doctor.agent_dir = doctor.global_dir / "agents" / "main"
    doctor.workspace = doctor.agent_dir / "workspace"
    doctor.workspace.mkdir(parents=True, exist_ok=True)

    report = doctor.run_routing_diagnostic()

    assert "routing" in report
    assert "guard" in report

    routing = report["routing"]
    guard = report["guard"]

    # Keep matrix stable as pre-deploy smoke baseline.
    assert routing["total"] == 20
    assert guard["total"] == 6
    assert routing["failed"] == 0
    assert guard["failed"] == 0


def test_doctor_full_diagnostic_includes_memory_stack_summary(monkeypatch, tmp_path):
    from kabot.config.schema import Config
    from kabot.utils.doctor import KabotDoctor

    doctor = KabotDoctor(agent_id="main")
    doctor.global_dir = tmp_path / "global"
    doctor.agent_dir = doctor.global_dir / "agents" / "main"
    doctor.workspace = doctor.agent_dir / "workspace"
    doctor.workspace.mkdir(parents=True, exist_ok=True)
    doctor.config = Config()

    async def _fake_connectivity():
        return []

    monkeypatch.setattr(doctor, "check_skills", lambda: {"eligible": [], "missing": []})
    monkeypatch.setattr(doctor, "check_dependencies", lambda: [])
    monkeypatch.setattr(doctor, "check_connectivity", _fake_connectivity)
    monkeypatch.setattr(
        doctor,
        "_memory_diagnostic",
        lambda: {
            "status": "ok",
            "backend": "hybrid",
            "retrieval_mode": "full_hybrid",
            "embedding_provider": "sentence",
            "embedding_model": "all-MiniLM-L6-v2",
            "lazy_probe": True,
            "hybrid_loaded": False,
        },
    )

    report = doctor.run_full_diagnostic(fix=False)

    assert report["memory"]["backend"] == "hybrid"
    assert report["memory"]["retrieval_mode"] == "full_hybrid"
    assert report["memory"]["embedding_model"] == "all-MiniLM-L6-v2"
