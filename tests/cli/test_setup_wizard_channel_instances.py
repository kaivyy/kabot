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


def test_configure_channels_discord_advanced_parses_intents_bitmask(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()

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
    assert wizard.config.channels.discord.intents == (32768 | 512)
