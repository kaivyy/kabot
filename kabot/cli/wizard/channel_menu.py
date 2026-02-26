"""Menu composition helpers for setup wizard channel screens."""

from __future__ import annotations

import questionary

from kabot.config.schema import ChannelsConfig


def _status_label(enabled: bool) -> str:
    return "ENABLED" if enabled else "DISABLED"


def _channel_label(name: str, enabled: bool) -> str:
    return f"{name:<10} [{_status_label(enabled)}]"


def _instance_label(channels: ChannelsConfig) -> str:
    if not channels.instances:
        return "Manage Channel Instances (Add Multiple Bots)"
    active_instances = sum(1 for inst in channels.instances if inst.enabled)
    return (
        f"Manage Channel Instances ({active_instances} active / {len(channels.instances)} total)"
    )


def build_channel_menu_options(channels: ChannelsConfig) -> list[questionary.Choice]:
    """Build channel configuration menu options with plain text status labels."""
    return [
        questionary.Choice(_instance_label(channels), value="instances"),
        questionary.Choice(_channel_label("Telegram", channels.telegram.enabled), value="telegram"),
        questionary.Choice(_channel_label("WhatsApp", channels.whatsapp.enabled), value="whatsapp"),
        questionary.Choice(_channel_label("Discord", channels.discord.enabled), value="discord"),
        questionary.Choice(_channel_label("Slack", channels.slack.enabled), value="slack"),
        questionary.Choice(_channel_label("Feishu", channels.feishu.enabled), value="feishu"),
        questionary.Choice(_channel_label("DingTalk", channels.dingtalk.enabled), value="dingtalk"),
        questionary.Choice(_channel_label("QQ", channels.qq.enabled), value="qq"),
        questionary.Choice(_channel_label("Email", channels.email.enabled), value="email"),
        questionary.Choice("Back", value="back"),
    ]
