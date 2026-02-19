from pathlib import Path

from typer.testing import CliRunner

from kabot.config.schema import Config


def test_agent_one_shot_continues_when_cron_start_fails(monkeypatch, tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()

    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.get_data_dir", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.core.logger.configure_logger", lambda config, store: None)
    monkeypatch.setattr("kabot.cli.commands._make_provider", lambda config: object())

    class _DummyAgentLoop:
        def __init__(self, **kwargs):
            self.tools = type("_Tools", (), {"get": lambda self, name: None})()

        async def process_direct(self, message, session_key):
            return "ok"

    class _DummyCron:
        def __init__(self, store_path):
            self.on_job = None

        async def start(self):
            raise RuntimeError("cron lock busy")

        def stop(self):
            return None

    monkeypatch.setattr("kabot.agent.loop.AgentLoop", _DummyAgentLoop)
    monkeypatch.setattr("kabot.cron.service.CronService", _DummyCron)

    result = runner.invoke(app, ["agent", "-m", "ping", "--no-markdown"])

    assert result.exit_code == 0
    assert "Cron scheduler unavailable for this run" in result.output
    assert "ok" in result.output
