from kabot.cli.wizard.channel_menu import build_channel_menu_options
from kabot.config.schema import ChannelInstance, ChannelsConfig


def test_build_channel_menu_options_uses_plain_status_labels():
    channels = ChannelsConfig()
    channels.telegram.enabled = True
    channels.discord.enabled = False
    channels.instances = [
        ChannelInstance(id="tg-work", type="telegram", enabled=True, config={"token": "x"}),
        ChannelInstance(id="dc-work", type="discord", enabled=False, config={"token": "y"}),
    ]

    options = build_channel_menu_options(channels)
    titles = [choice.title for choice in options]
    values = [choice.value for choice in options]

    assert titles[0] == "Manage Channel Instances (1 active / 2 total)"
    assert any("Telegram" in title and "ENABLED" in title for title in titles)
    assert any("Discord" in title and "DISABLED" in title for title in titles)
    assert all("[green]" not in title and "[dim]" not in title for title in titles)
    assert values == [
        "instances",
        "telegram",
        "whatsapp",
        "discord",
        "slack",
        "feishu",
        "dingtalk",
        "qq",
        "email",
        "back",
    ]
