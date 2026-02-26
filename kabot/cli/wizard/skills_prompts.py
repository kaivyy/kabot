"""Hybrid prompt adapters for the skills setup flow.

Uses richer checkbox UI when available and falls back to questionary.
"""

from __future__ import annotations

import sys
from typing import Any

import questionary


def _option_title(label: str, hint: str | None) -> str:
    clean_label = str(label or "").strip()
    clean_hint = str(hint or "").strip()
    if not clean_hint:
        return clean_label
    return f"{clean_label} ({clean_hint})"


def skills_checkbox(
    message: str,
    options: list[dict[str, Any]],
    *,
    default_values: list[str] | None = None,
) -> list[str]:
    """Show a checkbox prompt for skills with optional hints.

    Args:
        message: Prompt message.
        options: List of {"value","label","hint?"}.
        default_values: Optional default selected values.
    """
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return [str(v).strip() for v in (default_values or []) if str(v).strip()]

    choices = [
        questionary.Choice(
            title=_option_title(opt.get("label", ""), opt.get("hint")),
            value=str(opt.get("value", "")).strip(),
            checked=(str(opt.get("value", "")).strip() in (default_values or [])),
        )
        for opt in options
        if str(opt.get("value", "")).strip()
    ]

    # Optional richer UX path when InquirerPy is available.
    try:
        from InquirerPy import inquirer  # type: ignore

        iq_choices = [
            {
                "name": _option_title(opt.get("label", ""), opt.get("hint")),
                "value": str(opt.get("value", "")).strip(),
                "enabled": str(opt.get("value", "")).strip() in (default_values or []),
            }
            for opt in options
            if str(opt.get("value", "")).strip()
        ]
        selected = inquirer.checkbox(
            message=message,
            choices=iq_choices,
            instruction="(space=select, enter=confirm)",
        ).execute()
        return [str(v).strip() for v in (selected or []) if str(v).strip()]
    except Exception:
        try:
            selected = questionary.checkbox(
                message,
                choices=choices,
                style=questionary.Style(
                    [
                        ("qmark", "fg:cyan bold"),
                        ("question", "bold"),
                        ("pointer", "fg:cyan bold"),
                        ("highlighted", "fg:cyan bold"),
                        ("selected", "fg:green"),
                    ]
                ),
            ).ask()
        except Exception:
            selected = default_values or []
        return [str(v).strip() for v in (selected or []) if str(v).strip()]
