from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from typer.testing import CliRunner

from kabot.agent.loop import AgentLoop
from kabot.bus.queue import MessageBus
from kabot.config.schema import AgentConfig, Config
from kabot.cron.service import CronService


def test_agent_cli_passes_active_config_into_agent_loop(monkeypatch, tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")

    captured: dict[str, object] = {}

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.get_data_dir", lambda: Path(tmp_path / "data"))
    monkeypatch.setattr("kabot.core.logger.configure_logger", lambda config, store: None)
    monkeypatch.setattr("kabot.cli.commands._make_provider", lambda config: object())

    class _DummyAgentLoop:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.tools = type("_Tools", (), {"get": lambda self, name: None})()
            self.heartbeat = type("_Heartbeat", (), {"inject_cron_result": lambda *args, **kwargs: None})()

        def _required_tool_for_query(self, message):
            return None

        async def process_direct(
            self,
            message,
            session_key,
            suppress_post_response_warmup=False,
            probe_mode=False,
            persist_history=False,
        ):
            assert persist_history is True
            return "ok"

    class _DummyCron:
        def __init__(self, store_path):
            self.on_job = None

        def stop(self):
            return None

    monkeypatch.setattr("kabot.agent.loop.AgentLoop", _DummyAgentLoop)
    monkeypatch.setattr("kabot.cron.service.CronService", _DummyCron)

    result = runner.invoke(app, ["agent", "-m", "halo", "--no-markdown"])

    assert result.exit_code == 0
    assert "ok" in result.output
    assert captured["workspace"] == cfg.workspace_path
    assert captured["config"] is cfg
    assert captured["lazy_probe_memory"] is True


def test_agent_cli_one_shot_without_explicit_session_uses_workspace_scoped_session(monkeypatch, tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")

    captured: dict[str, object] = {}

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.get_data_dir", lambda: Path(tmp_path / "data"))
    monkeypatch.setattr("kabot.core.logger.configure_logger", lambda config, store: None)
    monkeypatch.setattr("kabot.cli.commands._make_provider", lambda config: object())
    monkeypatch.setattr(
        "kabot.cli.commands_agent_command._make_workspace_scoped_one_shot_session_id",
        lambda agent_id, workspace: "agent:main:cli:direct:workspace-test",
    )

    class _DummyAgentLoop:
        def __init__(self, **kwargs):
            self.tools = type("_Tools", (), {"get": lambda self, name: None})()
            self.heartbeat = type("_Heartbeat", (), {"inject_cron_result": lambda *args, **kwargs: None})()

        def _required_tool_for_query(self, message):
            return None

        async def process_direct(
            self,
            message,
            session_key,
            suppress_post_response_warmup=False,
            probe_mode=False,
            persist_history=False,
        ):
            captured["session_key"] = session_key
            return "ok"

    class _DummyCron:
        def __init__(self, store_path):
            self.on_job = None

        def stop(self):
            return None

    monkeypatch.setattr("kabot.agent.loop.AgentLoop", _DummyAgentLoop)
    monkeypatch.setattr("kabot.cron.service.CronService", _DummyCron)

    result = runner.invoke(app, ["agent", "-m", "halo", "--no-markdown"])

    assert result.exit_code == 0
    assert "ok" in result.output
    assert captured["session_key"] == "agent:main:cli:direct:workspace-test"


def test_agent_cli_one_shot_reuses_workspace_scoped_session_across_invocations(monkeypatch, tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")

    captured: list[str] = []

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.get_data_dir", lambda: Path(tmp_path / "data"))
    monkeypatch.setattr("kabot.core.logger.configure_logger", lambda config, store: None)
    monkeypatch.setattr("kabot.cli.commands._make_provider", lambda config: object())
    monkeypatch.setattr(
        "kabot.cli.commands_agent_command._make_workspace_scoped_one_shot_session_id",
        lambda agent_id, workspace: "agent:main:cli:direct:workspace-test",
    )

    class _DummyAgentLoop:
        def __init__(self, **kwargs):
            self.tools = type("_Tools", (), {"get": lambda self, name: None})()
            self.heartbeat = type("_Heartbeat", (), {"inject_cron_result": lambda *args, **kwargs: None})()

        def _required_tool_for_query(self, message):
            return None

        async def process_direct(
            self,
            message,
            session_key,
            suppress_post_response_warmup=False,
            probe_mode=False,
            persist_history=False,
        ):
            captured.append(session_key)
            return "ok"

    class _DummyCron:
        def __init__(self, store_path):
            self.on_job = None

        def stop(self):
            return None

    monkeypatch.setattr("kabot.agent.loop.AgentLoop", _DummyAgentLoop)
    monkeypatch.setattr("kabot.cron.service.CronService", _DummyCron)

    first = runner.invoke(app, ["agent", "-m", "buka folder desktop", "--no-markdown"])
    second = runner.invoke(app, ["agent", "-m", "buka folder bot", "--no-markdown"])

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert captured == [
        "agent:main:cli:direct:workspace-test",
        "agent:main:cli:direct:workspace-test",
    ]


def test_agent_cli_one_shot_closes_runtime_resources(monkeypatch, tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")

    captured: dict[str, object] = {"closed": False}

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.get_data_dir", lambda: Path(tmp_path / "data"))
    monkeypatch.setattr("kabot.core.logger.configure_logger", lambda config, store: None)
    monkeypatch.setattr("kabot.cli.commands._make_provider", lambda config: object())

    class _DummyAgentLoop:
        def __init__(self, **kwargs):
            self.tools = type("_Tools", (), {"get": lambda self, name: None})()
            self.heartbeat = type("_Heartbeat", (), {"inject_cron_result": lambda *args, **kwargs: None})()

        def _required_tool_for_query(self, message):
            return None

        async def process_direct(
            self,
            message,
            session_key,
            suppress_post_response_warmup=False,
            probe_mode=False,
            persist_history=False,
        ):
            return "ok"

        async def close_runtime_resources(self):
            captured["closed"] = True

    class _DummyCron:
        def __init__(self, store_path):
            self.on_job = None

        def stop(self):
            return None

    monkeypatch.setattr("kabot.agent.loop.AgentLoop", _DummyAgentLoop)
    monkeypatch.setattr("kabot.cron.service.CronService", _DummyCron)

    result = runner.invoke(app, ["agent", "-m", "halo", "--no-markdown"])

    assert result.exit_code == 0
    assert "ok" in result.output
    assert captured["closed"] is True


def test_agent_cli_uses_workspace_bound_agent_from_current_cwd(monkeypatch, tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(tmp_path / "default-workspace")
    cfg.agents.agents = [
        AgentConfig(
            id="repo",
            workspace=str(tmp_path / "projects" / "acme"),
            model="openai/gpt-4o",
        )
    ]

    cwd = tmp_path / "projects" / "acme" / "subdir"
    cwd.mkdir(parents=True)

    captured: dict[str, object] = {}

    monkeypatch.chdir(cwd)
    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.get_data_dir", lambda: Path(tmp_path / "data"))
    monkeypatch.setattr("kabot.core.logger.configure_logger", lambda config, store: None)
    monkeypatch.setattr("kabot.cli.commands._make_provider", lambda config: object())

    class _DummyAgentLoop:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.tools = type("_Tools", (), {"get": lambda self, name: None})()
            self.heartbeat = type("_Heartbeat", (), {"inject_cron_result": lambda *args, **kwargs: None})()

        def _required_tool_for_query(self, message):
            return None

        async def process_direct(
            self,
            message,
            session_key,
            suppress_post_response_warmup=False,
            probe_mode=False,
            persist_history=False,
        ):
            captured["direct_agent_binding"] = getattr(self, "_direct_agent_binding", None)
            return "ok"

    class _DummyCron:
        def __init__(self, store_path):
            self.on_job = None

        def stop(self):
            return None

    monkeypatch.setattr("kabot.agent.loop.AgentLoop", _DummyAgentLoop)
    monkeypatch.setattr("kabot.cron.service.CronService", _DummyCron)

    result = runner.invoke(app, ["agent", "-m", "halo", "--no-markdown"])

    assert result.exit_code == 0
    assert "ok" in result.output
    assert captured["workspace"] == (tmp_path / "projects" / "acme")
    assert captured["direct_agent_binding"] == "repo"


def test_agent_cli_one_shot_respects_explicit_session(monkeypatch, tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")

    captured: dict[str, object] = {}

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.get_data_dir", lambda: Path(tmp_path / "data"))
    monkeypatch.setattr("kabot.core.logger.configure_logger", lambda config, store: None)
    monkeypatch.setattr("kabot.cli.commands._make_provider", lambda config: object())
    monkeypatch.setattr(
        "kabot.cli.commands_agent_command._make_workspace_scoped_one_shot_session_id",
        lambda agent_id, workspace: "agent:main:cli:direct:workspace-test",
    )

    class _DummyAgentLoop:
        def __init__(self, **kwargs):
            self.tools = type("_Tools", (), {"get": lambda self, name: None})()
            self.heartbeat = type("_Heartbeat", (), {"inject_cron_result": lambda *args, **kwargs: None})()

        def _required_tool_for_query(self, message):
            return None

        async def process_direct(
            self,
            message,
            session_key,
            suppress_post_response_warmup=False,
            probe_mode=False,
            persist_history=False,
        ):
            captured["session_key"] = session_key
            return "ok"

    class _DummyCron:
        def __init__(self, store_path):
            self.on_job = None

        def stop(self):
            return None

    monkeypatch.setattr("kabot.agent.loop.AgentLoop", _DummyAgentLoop)
    monkeypatch.setattr("kabot.cron.service.CronService", _DummyCron)

    result = runner.invoke(app, ["agent", "-m", "halo", "--session", "cli:keep", "--no-markdown"])

    assert result.exit_code == 0
    assert "ok" in result.output
    assert captured["session_key"] == "cli:keep"


def test_agent_cli_tty_mode_does_not_crash_when_wiring_exec_approval(monkeypatch, tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.get_data_dir", lambda: Path(tmp_path / "data"))
    monkeypatch.setattr("kabot.core.logger.configure_logger", lambda config, store: None)
    monkeypatch.setattr("kabot.cli.commands._make_provider", lambda config: object())
    monkeypatch.setattr(
        "kabot.cli.commands_agent_command.sys.stdin",
        type("_TTY", (), {"isatty": lambda self: True})(),
    )

    class _DummyAgentLoop:
        def __init__(self, **kwargs):
            self.tools = type("_Tools", (), {"get": lambda self, name: None})()
            self.heartbeat = type("_Heartbeat", (), {"inject_cron_result": lambda *args, **kwargs: None})()

        def _required_tool_for_query(self, message):
            return None

        async def process_direct(
            self,
            message,
            session_key,
            suppress_post_response_warmup=False,
            probe_mode=False,
            persist_history=False,
        ):
            return "ok"

    class _DummyCron:
        def __init__(self, store_path):
            self.on_job = None

        def stop(self):
            return None

    monkeypatch.setattr("kabot.agent.loop.AgentLoop", _DummyAgentLoop)
    monkeypatch.setattr("kabot.cron.service.CronService", _DummyCron)

    result = runner.invoke(app, ["agent", "-m", "halo", "--no-markdown"])

    assert result.exit_code == 0
    assert "ok" in result.output


def test_agent_cli_logs_print_route_snapshot_summary(monkeypatch, tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.get_data_dir", lambda: Path(tmp_path / "data"))
    monkeypatch.setattr("kabot.core.logger.configure_logger", lambda config, store: None)
    monkeypatch.setattr("kabot.cli.commands._make_provider", lambda config: object())
    monkeypatch.setattr("kabot.cli.commands_agent_command.logger.enable", lambda *_args, **_kwargs: None)

    class _DummySessions:
        def __init__(self):
            self.session = SimpleNamespace(
                metadata={
                    "last_route_decision_snapshot": {
                        "route_profile": "GENERAL",
                        "route_complex": True,
                        "turn_category": "action",
                        "continuity_source": "parser",
                        "required_tool": "weather",
                        "required_tool_query": "cek suhu cilacap sekarang",
                        "external_skill_lane": False,
                        "forced_skill_names": ["weather"],
                    }
                }
            )

        def get_or_create(self, _key):
            return self.session

    class _DummyAgentLoop:
        def __init__(self, **kwargs):
            self.tools = type("_Tools", (), {"get": lambda self, name: None})()
            self.heartbeat = type("_Heartbeat", (), {"inject_cron_result": lambda *args, **kwargs: None})()
            self.sessions = _DummySessions()

        def _required_tool_for_query(self, message):
            return None

        async def process_direct(
            self,
            message,
            session_key,
            suppress_post_response_warmup=False,
            probe_mode=False,
            persist_history=False,
        ):
            return "ok"

    class _DummyCron:
        def __init__(self, store_path):
            self.on_job = None

        def stop(self):
            return None

    monkeypatch.setattr("kabot.agent.loop.AgentLoop", _DummyAgentLoop)
    monkeypatch.setattr("kabot.cron.service.CronService", _DummyCron)

    result = runner.invoke(app, ["agent", "-m", "halo", "--no-markdown", "--logs"])

    assert result.exit_code == 0
    assert "ok" in result.output
    assert "route snapshot: GENERAL/action | tool=weather | continuity=parser | forced=weather" in result.output


def test_agent_cli_one_shot_disables_markdown_when_runtime_requests_raw_output(monkeypatch, tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")

    printed: list[tuple[str, bool]] = []

    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.get_data_dir", lambda: Path(tmp_path / "data"))
    monkeypatch.setattr("kabot.core.logger.configure_logger", lambda config, store: None)
    monkeypatch.setattr("kabot.cli.commands._make_provider", lambda config: object())
    monkeypatch.setattr(
        "kabot.cli.commands_agent_command._print_agent_response",
        lambda response, render_markdown: printed.append((response, render_markdown)),
    )

    class _DummyAgentLoop:
        def __init__(self, **kwargs):
            self.tools = type("_Tools", (), {"get": lambda self, name: None})()
            self.heartbeat = type("_Heartbeat", (), {"inject_cron_result": lambda *args, **kwargs: None})()
            self._last_outbound_metadata = {}

        def _required_tool_for_query(self, message):
            return None

        async def process_direct(
            self,
            message,
            session_key,
            suppress_post_response_warmup=False,
            probe_mode=False,
            persist_history=False,
        ):
            self._last_outbound_metadata = {"render_markdown": False}
            return "**raw**"

    class _DummyCron:
        def __init__(self, store_path):
            self.on_job = None

        def stop(self):
            return None

    monkeypatch.setattr("kabot.agent.loop.AgentLoop", _DummyAgentLoop)
    monkeypatch.setattr("kabot.cron.service.CronService", _DummyCron)

    result = runner.invoke(app, ["agent", "-m", "halo"])

    assert result.exit_code == 0
    assert printed == [("**raw**", False)]


def test_agent_loop_uses_provided_config_without_reloading_global_config(monkeypatch, tmp_path):
    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")
    cfg.memory.backend = "disabled"

    provider = MagicMock()
    provider.get_default_model.return_value = "openai-codex/gpt-5.3-codex"

    captured: dict[str, object] = {}

    def _fake_create(config_dict, workspace, lazy_probe=False):
        captured["config_dict"] = config_dict
        captured["workspace"] = workspace
        captured["lazy_probe"] = lazy_probe

        class _NullMemory:
            def get_conversation_context(self, *args, **kwargs):
                return []

            def add_fact(self, *args, **kwargs):
                return None

            def search(self, *args, **kwargs):
                return []

            def recall(self, *args, **kwargs):
                return []

        return _NullMemory()

    def _boom():
        raise AssertionError("load_config should not be called when AgentLoop already received config")

    monkeypatch.setattr("kabot.config.loader.load_config", _boom)
    monkeypatch.setattr("kabot.memory.memory_factory.MemoryFactory.create", _fake_create)

    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=cfg.workspace_path,
        config=cfg,
        model="openai-codex/gpt-5.3-codex",
        cron_service=CronService(tmp_path / "cron_jobs.json"),
    )

    assert loop.config is cfg
    assert captured["workspace"] == cfg.workspace_path
    assert isinstance(captured["config_dict"], dict)
    assert captured["config_dict"]["agents"]["defaults"]["workspace"] == str(cfg.workspace_path)
    assert captured["lazy_probe"] is False


def test_agent_loop_forwards_lazy_probe_memory_flag_to_memory_factory(monkeypatch, tmp_path):
    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")
    cfg.memory.backend = "hybrid"

    provider = MagicMock()
    provider.get_default_model.return_value = "openai-codex/gpt-5.3-codex"

    captured: dict[str, object] = {}

    def _fake_create(config_dict, workspace, lazy_probe=False):
        captured["workspace"] = workspace
        captured["lazy_probe"] = lazy_probe

        class _Memory:
            def create_session(self, *args, **kwargs):
                return None

            async def add_message(self, *args, **kwargs):
                return None

            def get_conversation_context(self, *args, **kwargs):
                return []

        return _Memory()

    monkeypatch.setattr("kabot.memory.memory_factory.MemoryFactory.create", _fake_create)

    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=cfg.workspace_path,
        config=cfg,
        model="openai-codex/gpt-5.3-codex",
        cron_service=CronService(tmp_path / "cron_jobs.json"),
        lazy_probe_memory=True,
    )

    assert loop.config is cfg
    assert captured["workspace"] == cfg.workspace_path
    assert captured["lazy_probe"] is True
