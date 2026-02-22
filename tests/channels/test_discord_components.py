"""Tests for Discord component builders."""

import pytest

from kabot.channels.discord_components import (
    ButtonStyle,
    build_action_row,
    build_select_menu,
)


class TestDiscordComponents:
    def test_build_action_row_buttons(self):
        row = build_action_row(
            buttons=[
                {"label": "Approve", "style": ButtonStyle.SUCCESS, "custom_id": "approve"},
                {"label": "Reject", "style": ButtonStyle.DANGER, "custom_id": "reject"},
            ]
        )
        assert row["type"] == 1
        assert len(row["components"]) == 2
        assert row["components"][0]["label"] == "Approve"

    def test_button_style_mapping(self):
        assert ButtonStyle.PRIMARY == 1
        assert ButtonStyle.DANGER == 4

    def test_url_button(self):
        row = build_action_row(
            buttons=[
                {"label": "Visit", "style": ButtonStyle.LINK, "url": "https://example.com"},
            ]
        )
        assert row["components"][0]["url"] == "https://example.com"

    def test_empty_buttons_raises(self):
        with pytest.raises(ValueError):
            build_action_row(buttons=[])

    def test_build_select_menu(self):
        row = build_select_menu(
            custom_id="model_pick",
            options=[
                {"label": "GPT-4", "value": "gpt4"},
                {"label": "Claude", "value": "claude"},
            ],
            placeholder="Pick a model",
        )
        assert row["type"] == 1
        select = row["components"][0]
        assert select["type"] == 3
        assert select["custom_id"] == "model_pick"
        assert len(select["options"]) == 2
