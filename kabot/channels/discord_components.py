"""Discord component builders for interactive messages."""

from __future__ import annotations

from enum import IntEnum


class ButtonStyle(IntEnum):
    """Discord button style values."""

    PRIMARY = 1
    SECONDARY = 2
    SUCCESS = 3
    DANGER = 4
    LINK = 5


def build_action_row(buttons: list[dict]) -> dict:
    """Build a Discord action row from button specs."""
    components: list[dict] = []
    for button in buttons:
        style = int(button["style"])
        component = {
            "type": 2,
            "label": button["label"],
            "style": style,
        }
        if style == int(ButtonStyle.LINK):
            component["url"] = button["url"]
        else:
            component["custom_id"] = button.get("custom_id", str(button["label"]).lower())
        components.append(component)
    return {"type": 1, "components": components}
