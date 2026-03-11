"""Tests for doctor CLI command surface."""

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


def test_doctor_command_exposes_bootstrap_sync_flag(runner):
    from kabot.cli.commands import app

    result = runner.invoke(app, ["doctor", "--help"])
    assert result.exit_code == 0
    assert "--bootstrap-sync" in result.output
    assert "--parity-report" in result.output
    assert "--parity-json" in result.output


def test_doctor_parity_report_uses_parity_renderer(monkeypatch, runner):
    from kabot.cli.commands import app

    called: dict[str, bool] = {"parity": False}

    class _FakeDoctor:
        def __init__(self, agent_id: str = "main") -> None:
            self.agent_id = agent_id

        def render_report(self, fix: bool = False, sync_bootstrap: bool = False) -> None:
            _ = fix, sync_bootstrap

        def render_parity_report(self) -> None:
            called["parity"] = True

    monkeypatch.setattr("kabot.utils.doctor.KabotDoctor", _FakeDoctor)
    result = runner.invoke(app, ["doctor", "--parity-report"])

    assert result.exit_code == 0
    assert called["parity"] is True


def test_doctor_parity_report_writes_json_file(monkeypatch, runner, tmp_path):
    from kabot.cli.commands import app

    called: dict[str, bool] = {"render": False, "run": False}
    output_path = tmp_path / "parity.json"

    class _FakeDoctor:
        def __init__(self, agent_id: str = "main") -> None:
            self.agent_id = agent_id

        def render_report(self, fix: bool = False, sync_bootstrap: bool = False) -> None:
            _ = fix, sync_bootstrap

        def render_parity_report(self) -> None:
            called["render"] = True

        def run_parity_diagnostic(self):
            called["run"] = True
            return {"adapter_registry": {"enabled": 9}, "generated_at": "2026-03-02T00:00:00"}

    monkeypatch.setattr("kabot.utils.doctor.KabotDoctor", _FakeDoctor)
    result = runner.invoke(app, ["doctor", "--parity-report", "--parity-json", str(output_path)])

    assert result.exit_code == 0
    assert called["run"] is True
    assert called["render"] is False
    assert output_path.exists()
    text = output_path.read_text(encoding="utf-8")
    assert "\"adapter_registry\"" in text


def test_doctor_parity_report_writes_json_stdout(monkeypatch, runner):
    from kabot.cli.commands import app

    class _FakeDoctor:
        def __init__(self, agent_id: str = "main") -> None:
            self.agent_id = agent_id

        def render_report(self, fix: bool = False, sync_bootstrap: bool = False) -> None:
            _ = fix, sync_bootstrap

        def render_parity_report(self) -> None:
            raise AssertionError("render_parity_report should not be used when --parity-json is set")

        def run_parity_diagnostic(self):
            return {"ok": True}

    monkeypatch.setattr("kabot.utils.doctor.KabotDoctor", _FakeDoctor)
    result = runner.invoke(app, ["doctor", "--parity-report", "--parity-json", "-"])

    assert result.exit_code == 0
    assert "\"ok\": true" in result.output.lower()


def test_doctor_routing_mode_uses_routing_renderer(monkeypatch, runner):
    from kabot.cli.commands import app

    called: dict[str, bool] = {"routing": False}

    class _FakeDoctor:
        def __init__(self, agent_id: str = "main") -> None:
            self.agent_id = agent_id

        def render_report(self, fix: bool = False, sync_bootstrap: bool = False) -> None:
            _ = fix, sync_bootstrap

        def render_parity_report(self) -> None:
            raise AssertionError("render_parity_report should not be called for routing mode")

        def render_routing_report(self) -> None:
            called["routing"] = True

    monkeypatch.setattr("kabot.utils.doctor.KabotDoctor", _FakeDoctor)
    result = runner.invoke(app, ["doctor", "routing"])

    assert result.exit_code == 0
    assert called["routing"] is True


def test_doctor_smoke_agent_invokes_smoke_matrix_with_threshold_args(monkeypatch, runner):
    from kabot.cli.commands import app

    captured: dict[str, list[str] | None] = {"argv": None}

    def _fake_main(argv=None):
        captured["argv"] = list(argv or [])
        return 0

    monkeypatch.setattr("kabot.cli.agent_smoke_matrix.main", _fake_main)
    result = runner.invoke(
        app,
        [
            "doctor",
            "smoke-agent",
            "--smoke-json",
            "--smoke-no-default-cases",
            "--smoke-skill",
            "weather",
            "--smoke-skill-locales",
            "en,id",
            "--smoke-timeout",
            "15",
            "--smoke-max-first-response-ms",
            "800",
            "--smoke-max-context-build-ms",
            "250",
        ],
    )

    assert result.exit_code == 0
    assert captured["argv"] is not None
    assert "--json" in captured["argv"]
    assert "--no-default-cases" in captured["argv"]
    assert "--skill" in captured["argv"]
    assert captured["argv"][captured["argv"].index("--skill") + 1] == "weather"
    assert "--skill-locales" in captured["argv"]
    assert captured["argv"][captured["argv"].index("--skill-locales") + 1] == "en,id"
    assert "--timeout" in captured["argv"]
    assert captured["argv"][captured["argv"].index("--timeout") + 1] == "15"
    assert "--max-first-response-ms" in captured["argv"]
    assert captured["argv"][captured["argv"].index("--max-first-response-ms") + 1] == "800"
    assert "--max-context-build-ms" in captured["argv"]
    assert captured["argv"][captured["argv"].index("--max-context-build-ms") + 1] == "250"


def test_doctor_smoke_agent_passes_mcp_local_echo_flag(monkeypatch, runner):
    from kabot.cli.commands import app

    captured: dict[str, list[str] | None] = {"argv": None}

    def _fake_main(argv=None):
        captured["argv"] = list(argv or [])
        return 0

    monkeypatch.setattr("kabot.cli.agent_smoke_matrix.main", _fake_main)
    result = runner.invoke(app, ["doctor", "smoke-agent", "--smoke-mcp-local-echo"])

    assert result.exit_code == 0
    assert captured["argv"] is not None
    assert "--mcp-local-echo" in captured["argv"]
