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
