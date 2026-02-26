from pathlib import Path

from kabot.cli.setup_wizard import SetupWizard
from kabot.config.schema import AgentConfig, ChannelInstance


def test_add_channel_instance_record_dedupes_instance_id(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()
    wizard.config.channels.instances.append(
        ChannelInstance(
            id="telegram_bot",
            type="telegram",
            enabled=True,
            config={"token": "123", "allow_from": []},
        )
    )

    created = wizard._add_channel_instance_record(
        instance_id="telegram_bot",
        channel_type="telegram",
        config_dict={"token": "456", "allow_from": []},
    )

    assert created.id == "telegram_bot_2"
    assert wizard.config.channels.instances[-1].id == "telegram_bot_2"


def test_add_channel_instance_record_auto_creates_agent(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()

    created = wizard._add_channel_instance_record(
        instance_id="work_bot",
        channel_type="telegram",
        config_dict={"token": "123", "allow_from": []},
        agent_binding="work",
        auto_create_agent=True,
        model_override="openai/gpt-4o-mini",
    )

    assert created.agent_binding == "work"
    assert any(agent.id == "work" for agent in wizard.config.agents.agents)
    agent = next(agent for agent in wizard.config.agents.agents if agent.id == "work")
    assert agent.model == "openai/gpt-4o-mini"


def test_ensure_agent_exists_updates_existing_model(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()
    wizard.config.agents.agents.append(AgentConfig(id="research", model=None))

    resolved = wizard._ensure_agent_exists("research", model_override="openai/gpt-4.1")

    assert resolved == "research"
    agent = next(agent for agent in wizard.config.agents.agents if agent.id == "research")
    assert agent.model == "openai/gpt-4.1"


def test_ensure_agent_exists_initializes_workspace_templates(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()

    resolved = wizard._ensure_agent_exists("ops")

    assert resolved == "ops"
    workspace = tmp_path / ".kabot" / "workspace-ops"
    assert (workspace / "AGENTS.md").exists()
    assert (workspace / "SOUL.md").exists()
    assert (workspace / "USER.md").exists()
    assert (workspace / "memory" / "MEMORY.md").exists()


def test_configure_channels_discord_advanced_parses_intents_bitmask(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()
    monkeypatch.setattr(wizard, "_configure_legacy_channel_ai_binding", lambda _channel_type: None)

    menu_choices = iter(["discord", "back"])
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.ClackUI.clack_select",
        lambda *args, **kwargs: next(menu_choices),
    )

    confirms = iter([True, True])  # enable discord, configure advanced
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.Confirm.ask",
        lambda *args, **kwargs: next(confirms),
    )

    prompts = iter(
        [
            "discord-token-123",
            "",
            "wss://gateway.discord.gg/?v=10&encoding=json",
            "32768,512",
        ]
    )
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.Prompt.ask",
        lambda *args, **kwargs: next(prompts),
    )

    wizard._configure_channels()

    assert wizard.config.channels.discord.enabled is True
    assert wizard.config.channels.discord.token == "discord-token-123"
    assert wizard.config.channels.discord.allow_from == []
    assert wizard.config.channels.discord.intents == (32768 | 512)


def test_configure_channels_menu_uses_plain_status_labels(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()
    wizard.config.channels.telegram.enabled = True
    wizard.config.channels.discord.enabled = False

    captured = {}

    def _fake_select(*args, **kwargs):
        captured["choices"] = kwargs.get("choices", [])
        return "back"

    monkeypatch.setattr("kabot.cli.setup_wizard.ClackUI.clack_select", _fake_select)
    monkeypatch.setattr(wizard, "_save_setup_state", lambda *args, **kwargs: None)

    wizard._configure_channels()

    titles = [choice.title for choice in captured["choices"]]
    assert any("Telegram" in title and "ENABLED" in title for title in titles)
    assert any("Discord" in title and "DISABLED" in title for title in titles)
    assert all("[green]" not in title and "[dim]" not in title for title in titles)


def test_parse_allow_from_values_dedupes_and_splits(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()

    parsed = wizard._parse_allow_from_values("123, 456\n789,123,,  456")

    assert parsed == ["123", "456", "789"]


def test_prompt_instance_config_telegram_includes_allow_from(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()

    prompts = iter(["123:token", "111,222"])
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.Prompt.ask",
        lambda *args, **kwargs: next(prompts),
    )

    config = wizard._prompt_instance_config("telegram")

    assert config == {"token": "123:token", "allow_from": ["111", "222"]}


def test_pick_agent_model_override_browse_returns_selected_model(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()

    monkeypatch.setattr(
        "kabot.cli.setup_wizard.ClackUI.clack_select",
        lambda *args, **kwargs: "browse",
    )
    monkeypatch.setattr(
        wizard,
        "_providers_with_saved_credentials",
        lambda: ["groq", "openai"],
    )
    monkeypatch.setattr(
        wizard,
        "_model_browser",
        lambda **kwargs: "groq/meta-llama/llama-4-scout-17b-16e-instruct",
    )

    selected = wizard._pick_agent_model_override()

    assert selected == "groq/meta-llama/llama-4-scout-17b-16e-instruct"


def test_configure_legacy_channel_ai_binding_creates_channel_binding(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()

    confirms = iter([True, True])  # configure binding, auto-create dedicated agent
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.Confirm.ask",
        lambda *args, **kwargs: next(confirms),
    )
    monkeypatch.setattr(wizard, "_pick_agent_model_override", lambda: "groq/meta-llama/llama-4-scout-17b-16e-instruct")

    wizard._configure_legacy_channel_ai_binding("telegram")

    assert any(agent.id == "telegram_main" for agent in wizard.config.agents.agents)
    binding = wizard._find_channel_default_binding("telegram")
    assert binding is not None
    assert binding.agent_id == "telegram_main"


def test_configure_legacy_channel_ai_binding_remove_binding_when_shared_default(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()
    wizard._upsert_channel_default_binding("telegram", "telegram_main")

    confirms = iter([True, False])  # configure binding, then choose no specific binding
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.Confirm.ask",
        lambda *args, **kwargs: next(confirms),
    )

    wizard._configure_legacy_channel_ai_binding("telegram")

    assert wizard._find_channel_default_binding("telegram") is None


def test_configure_channel_instances_shows_list_and_edit_delete_options(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()
    wizard.config.channels.instances.append(
        ChannelInstance(
            id="telegram_ops",
            type="telegram",
            enabled=True,
            config={"token": "123", "allow_from": ["8086618307"]},
        )
    )

    captured = {}
    monkeypatch.setattr("kabot.cli.setup_wizard.ClackUI.section_start", lambda *args, **kwargs: None)
    monkeypatch.setattr("kabot.cli.setup_wizard.ClackUI.section_end", lambda *args, **kwargs: None)

    def _fake_select(*args, **kwargs):
        captured["choices"] = kwargs.get("choices", [])
        return "back"

    monkeypatch.setattr("kabot.cli.setup_wizard.ClackUI.clack_select", _fake_select)

    wizard._configure_channel_instances()

    output = capsys.readouterr().out
    assert "telegram_ops" in output
    titles = [choice.title for choice in captured["choices"]]
    assert "Edit Instance" in titles
    assert "Delete Instance" in titles


def test_edit_channel_instance_updates_fields(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()
    wizard.config.channels.instances.append(
        ChannelInstance(
            id="telegram_main",
            type="telegram",
            enabled=True,
            config={"token": "123", "allow_from": ["1001"]},
            agent_binding="agent_a",
        )
    )

    monkeypatch.setattr("kabot.cli.setup_wizard.ClackUI.clack_select", lambda *args, **kwargs: 0)
    confirms = iter([False, False, True])  # enabled, change binding, edit allowFrom
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.Confirm.ask",
        lambda *args, **kwargs: next(confirms),
    )
    monkeypatch.setattr(
        wizard,
        "_prompt_allow_from_list",
        lambda _label, _current: ["2002", "3003"],
    )

    wizard._edit_channel_instance()

    edited = wizard.config.channels.instances[0]
    assert edited.enabled is False
    assert edited.agent_binding == "agent_a"
    assert edited.config["allow_from"] == ["2002", "3003"]


def test_delete_channel_instance_removes_selected_instance(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()
    wizard.config.channels.instances.extend(
        [
            ChannelInstance(
                id="telegram_main",
                type="telegram",
                enabled=True,
                config={"token": "123", "allow_from": []},
            ),
            ChannelInstance(
                id="telegram_backup",
                type="telegram",
                enabled=True,
                config={"token": "456", "allow_from": []},
            ),
        ]
    )

    monkeypatch.setattr("kabot.cli.setup_wizard.ClackUI.clack_select", lambda *args, **kwargs: 0)
    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", lambda *args, **kwargs: True)

    wizard._delete_channel_instance()

    ids = [instance.id for instance in wizard.config.channels.instances]
    assert ids == ["telegram_backup"]


def test_configure_whatsapp_connect_now_starts_background_bridge(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()

    confirms = iter([True, True, True])  # enable WhatsApp, connect now, keep bridge background
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.Confirm.ask",
        lambda *args, **kwargs: next(confirms),
    )
    monkeypatch.setattr(wizard, "_prompt_allow_from_list", lambda *_args, **_kwargs: ["628123"])

    monkeypatch.setattr("kabot.cli.bridge_utils.get_bridge_dir", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.cli.bridge_utils.is_bridge_reachable", lambda *_args, **_kwargs: False)

    captured = {"login_kwargs": None, "background_calls": 0}

    def _fake_login(*args, **kwargs):
        captured["login_kwargs"] = kwargs
        return True

    def _fake_background(*args, **kwargs):
        captured["background_calls"] += 1
        return True

    monkeypatch.setattr("kabot.cli.bridge_utils.run_bridge_login", _fake_login)
    monkeypatch.setattr("kabot.cli.bridge_utils.start_bridge_background", _fake_background)

    wizard._configure_whatsapp()

    assert wizard.config.channels.whatsapp.enabled is True
    assert wizard.config.channels.whatsapp.allow_from == ["628123"]
    assert captured["background_calls"] == 1
    assert captured["login_kwargs"] == {
        "stop_when_connected": True,
        "timeout_seconds": 180,
        "bridge_url": "ws://localhost:3001",
        "restart_if_running": False,
    }


def test_configure_whatsapp_connect_now_restarts_existing_bridge(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()

    confirms = iter([True, True, True, False])  # enable, connect now, restart, skip keep background
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.Confirm.ask",
        lambda *args, **kwargs: next(confirms),
    )
    monkeypatch.setattr(wizard, "_prompt_allow_from_list", lambda *_args, **_kwargs: [])

    monkeypatch.setattr("kabot.cli.bridge_utils.get_bridge_dir", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.cli.bridge_utils.is_bridge_reachable", lambda *_args, **_kwargs: True)

    captured = {"stopped": 0, "login_kwargs": None}
    monkeypatch.setattr(
        "kabot.cli.bridge_utils.stop_bridge_processes",
        lambda **kwargs: captured.__setitem__("stopped", captured["stopped"] + 1) or [1234],
    )
    monkeypatch.setattr(
        "kabot.cli.bridge_utils.run_bridge_login",
        lambda *args, **kwargs: captured.__setitem__("login_kwargs", kwargs) or True,
    )

    wizard._configure_whatsapp()

    assert captured["stopped"] == 1
    assert captured["login_kwargs"] == {
        "stop_when_connected": True,
        "timeout_seconds": 180,
        "bridge_url": "ws://localhost:3001",
        "restart_if_running": True,
    }


def test_configure_whatsapp_connect_now_without_restart_uses_existing_bridge(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()

    confirms = iter([True, True, False, False])  # enable, connect now, no restart, skip keep background
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.Confirm.ask",
        lambda *args, **kwargs: next(confirms),
    )
    monkeypatch.setattr(wizard, "_prompt_allow_from_list", lambda *_args, **_kwargs: [])

    monkeypatch.setattr("kabot.cli.bridge_utils.get_bridge_dir", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.cli.bridge_utils.is_bridge_reachable", lambda *_args, **_kwargs: True)

    captured = {"stopped": 0, "login_kwargs": None}
    monkeypatch.setattr(
        "kabot.cli.bridge_utils.stop_bridge_processes",
        lambda **kwargs: captured.__setitem__("stopped", captured["stopped"] + 1) or [],
    )
    monkeypatch.setattr(
        "kabot.cli.bridge_utils.run_bridge_login",
        lambda *args, **kwargs: captured.__setitem__("login_kwargs", kwargs) or True,
    )

    wizard._configure_whatsapp()

    assert captured["stopped"] == 0
    assert captured["login_kwargs"] == {
        "stop_when_connected": True,
        "timeout_seconds": 180,
        "bridge_url": "ws://localhost:3001",
        "restart_if_running": False,
    }
