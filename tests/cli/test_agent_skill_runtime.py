from pathlib import Path

from typer.testing import CliRunner

from kabot.config.schema import Config
from kabot.providers.base import LLMResponse


def _write_skill(skill_root: Path, skill_name: str, body: str, *, description: str = "test skill") -> None:
    skill_dir = skill_root / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )


class _RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def get_default_model(self) -> str:
        return "openai-codex/gpt-5.3-codex"

    async def chat(
        self,
        messages,
        tools=None,
        model=None,
        max_tokens=4096,
        temperature=0.7,
    ):
        self.calls.append(messages)
        return LLMResponse(content="AI_OK")


def _garble_utf8(text: str) -> str:
    return text.encode("utf-8").decode("latin1")


def test_agent_cli_explicit_skill_prompts_stay_ai_driven_and_skip_catalog_summary(monkeypatch, tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    _write_skill(
        workspace / "skills",
        "weather",
        "Use live weather tools, then answer naturally in the user's language.",
        description="weather helper",
    )
    _write_skill(
        workspace / "skills",
        "1password",
        "Use 1Password vault context for login and credential tasks.",
        description="vault credential helper",
    )
    _write_skill(
        workspace / "skills",
        "writing-plans",
        "Turn requirements into a concise implementation plan before execution.",
        description="planning helper",
    )

    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(workspace)

    provider = _RecordingProvider()

    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)
    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.get_data_dir", lambda: Path(tmp_path / "data"))
    monkeypatch.setattr("kabot.core.logger.configure_logger", lambda config, store: None)
    monkeypatch.setattr("kabot.cli.commands._make_provider", lambda config: provider)
    monkeypatch.setattr("kabot.cli.commands._inject_skill_env", lambda config: None)

    prompts = [
        "Please use the weather skill for this request.",
        "Tolong pakai skill 1password untuk request ini ya.",
        "Tolong pakai skill weather untuk permintaan ini ya.",
        "请用 writing-plans 技能处理这个请求。",
        "ช่วยใช้สกิล weather กับงานนี้หน่อย",
        "writing-plans スキルを使ってこの依頼を手伝って",
    ]

    for idx, prompt in enumerate(prompts, start=1):
        result = runner.invoke(
            app,
            ["agent", "-m", prompt, "--session", f"cli:skill:{idx}", "--no-markdown", "--logs"],
        )
        assert result.exit_code == 0
        assert "AI_OK" in result.output

    final_agent_calls = [
        messages
        for messages in provider.calls
        if isinstance(messages, list)
        and len(messages) >= 2
        and isinstance(messages[0], dict)
        and messages[0].get("role") == "system"
    ]

    assert len(final_agent_calls) == len(prompts)
    for messages in final_agent_calls:
        assert [message["role"] for message in messages[:2]] == ["system", "user"]
        system_prompt = str(messages[0]["content"])
        assert "Auto-Selected Skills" in system_prompt
        assert "Available Skills (Reference Documents)" not in system_prompt


def test_agent_cli_probe_mode_uses_compact_system_prompt(monkeypatch, tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "AGENTS.md").write_text("A" * 5000, encoding="utf-8")
    _write_skill(
        workspace / "skills",
        "weather",
        "Use live weather tools, then answer naturally in the user's language.",
        description="weather helper",
    )

    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(workspace)

    provider = _RecordingProvider()

    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)
    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.get_data_dir", lambda: Path(tmp_path / "data"))
    monkeypatch.setattr("kabot.core.logger.configure_logger", lambda config, store: None)
    monkeypatch.setattr("kabot.cli.commands._make_provider", lambda config: provider)
    monkeypatch.setattr("kabot.cli.commands._inject_skill_env", lambda config: None)

    result = runner.invoke(
        app,
        [
            "agent",
            "-m",
            "Please use the weather skill for this request.",
            "--session",
            "cli:compact:1",
            "--no-markdown",
            "--logs",
        ],
    )

    assert result.exit_code == 0
    assert "AI_OK" in result.output

    final_agent_calls = [
        messages
        for messages in provider.calls
        if isinstance(messages, list)
        and len(messages) >= 2
        and isinstance(messages[0], dict)
        and messages[0].get("role") == "system"
    ]

    assert len(final_agent_calls) == 1
    system_prompt = str(final_agent_calls[0][0]["content"])
    assert "Auto-Selected Skills" in system_prompt
    assert "## AGENTS.md" not in system_prompt


def test_agent_cli_repairs_mojibake_message_before_runtime(monkeypatch, tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(workspace)

    provider = _RecordingProvider()
    clean_prompt = "请用 weather 技能处理这个请求。"
    garbled_prompt = _garble_utf8(clean_prompt)

    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)
    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.get_data_dir", lambda: Path(tmp_path / "data"))
    monkeypatch.setattr("kabot.core.logger.configure_logger", lambda config, store: None)
    monkeypatch.setattr("kabot.cli.commands._make_provider", lambda config: provider)
    monkeypatch.setattr("kabot.cli.commands._inject_skill_env", lambda config: None)

    result = runner.invoke(
        app,
        ["agent", "-m", garbled_prompt, "--session", "cli:garbled:1", "--no-markdown", "--logs"],
    )

    assert result.exit_code == 0
    assert "AI_OK" in result.output

    final_agent_calls = [
        messages
        for messages in provider.calls
        if isinstance(messages, list)
        and len(messages) >= 2
        and isinstance(messages[1], dict)
        and messages[1].get("role") == "user"
    ]
    assert len(final_agent_calls) == 1
    assert final_agent_calls[0][1]["content"] == clean_prompt


def test_agent_cli_temporal_query_uses_local_fast_reply_without_provider(monkeypatch, tmp_path):
    from kabot.cli.commands import app

    runner = CliRunner()
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    cfg = Config()
    cfg.logging.file_enabled = False
    cfg.logging.db_enabled = False
    cfg.agents.defaults.workspace = str(workspace)

    provider = _RecordingProvider()

    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)
    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    monkeypatch.setattr("kabot.config.loader.get_data_dir", lambda: Path(tmp_path / "data"))
    monkeypatch.setattr("kabot.core.logger.configure_logger", lambda config, store: None)
    monkeypatch.setattr("kabot.cli.commands._make_provider", lambda config: provider)
    monkeypatch.setattr("kabot.cli.commands._inject_skill_env", lambda config: None)
    monkeypatch.setattr(
        "kabot.agent.loop_core.message_runtime.build_temporal_fast_reply",
        lambda text, *, locale=None, now_local=None: "Sekarang hari Senin.",
    )

    result = runner.invoke(
        app,
        ["agent", "-m", "hari apa sekarang?", "--session", "cli:temporal:1", "--no-markdown", "--logs"],
    )

    assert result.exit_code == 0
    assert "Sekarang hari Senin." in result.output
    assert provider.calls == []
