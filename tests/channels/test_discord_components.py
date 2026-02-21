"""Tests for Discord component builders."""

from kabot.channels.discord_components import ButtonStyle, build_action_row


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
