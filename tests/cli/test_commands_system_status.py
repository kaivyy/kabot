from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner


def test_status_displays_memory_backend_mode_and_model(monkeypatch, tmp_path):
    from kabot.cli import commands_system
    from kabot.config.schema import Config

    captured: list[str] = []

    class _FakeConsole:
        def print(self, *args, **kwargs):  # noqa: ARG002
            captured.append(" ".join(str(arg) for arg in args))

    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")

    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    workspace = Path(cfg.workspace_path)
    workspace.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(commands_system, "console", _FakeConsole())
    monkeypatch.setattr("kabot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.providers.registry.PROVIDERS", [])

    class _FakeMemory:
        def get_stats(self):
            return {
                "backend": "hybrid",
                "retrieval_mode": "full_hybrid",
                "embedding_provider": "sentence",
                "embedding_model": "all-MiniLM-L6-v2",
            }

    monkeypatch.setattr(
        "kabot.memory.memory_factory.MemoryFactory.create",
        lambda config, workspace, lazy_probe=False: _FakeMemory(),  # noqa: ARG005
    )

    commands_system.status()

    joined = "\n".join(captured)
    assert "Memory Backend: hybrid" in joined
    assert "Memory Mode: full_hybrid" in joined
    assert "Embedding Model: all-MiniLM-L6-v2" in joined


def test_status_cli_smoke_displays_memory_backend_mode_and_model(monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.config.schema import Config

    runner = CliRunner()

    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")

    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    workspace = Path(cfg.workspace_path)
    workspace.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("kabot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.providers.registry.PROVIDERS", [])
    monkeypatch.setattr("kabot.core.logger.configure_logger", lambda config, store: None)

    class _FakeMemory:
        def get_stats(self):
            return {
                "backend": "hybrid",
                "retrieval_mode": "full_hybrid",
                "embedding_provider": "sentence",
                "embedding_model": "all-MiniLM-L6-v2",
            }

    monkeypatch.setattr(
        "kabot.memory.memory_factory.MemoryFactory.create",
        lambda config, workspace, lazy_probe=False: _FakeMemory(),  # noqa: ARG005
    )

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Memory Backend: hybrid" in result.output
    assert "Memory Mode: full_hybrid" in result.output
    assert "Embedding Model: all-MiniLM-L6-v2" in result.output
