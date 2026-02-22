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


class ComponentType(IntEnum):
    """Discord component type values."""

    ACTION_ROW = 1
    BUTTON = 2
    STRING_SELECT = 3


def build_action_row(buttons: list[dict]) -> dict:
    """Build a Discord action row from button specs."""
    if not buttons:
        raise ValueError("Action row requires at least one button")

    components: list[dict] = []
    for button in buttons:
        style = int(button["style"])
        component = {
            "type": int(ComponentType.BUTTON),
            "label": button["label"],
            "style": style,
        }
        if style == int(ButtonStyle.LINK):
            component["url"] = button["url"]
        else:
            component["custom_id"] = button.get("custom_id", str(button["label"]).lower())
        components.append(component)
    return {"type": int(ComponentType.ACTION_ROW), "components": components}


def build_select_menu(
    custom_id: str,
    options: list[dict],
    placeholder: str = "",
    min_values: int = 1,
    max_values: int = 1,
) -> dict:
    """Build a Discord string select wrapped in an action row."""
    select = {
        "type": int(ComponentType.STRING_SELECT),
        "custom_id": custom_id,
        "options": [
            {
                "label": option["label"],
                "value": option["value"],
                "description": option.get("description", ""),
            }
            for option in options
        ],
        "placeholder": placeholder,
        "min_values": min_values,
        "max_values": max_values,
    }
    return {"type": int(ComponentType.ACTION_ROW), "components": [select]}
