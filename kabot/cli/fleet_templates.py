"""Predefined multi-bot fleet templates for setup wizard."""

from __future__ import annotations

from typing import Any

FLEET_TEMPLATES: dict[str, dict[str, Any]] = {
    "content_pipeline": {
        "label": "Content Pipeline (Ideation -> Research -> Publish)",
        "roles": [
            {
                "role": "ideation",
                "default_model": "anthropic/claude-3-5-sonnet-latest",
            },
            {
                "role": "research",
                "default_model": "openai/gpt-4.1",
            },
            {
                "role": "publish",
                "default_model": "openai-codex/gpt-5.3-codex",
            },
        ],
    },
}


def get_template_roles(template_id: str) -> list[dict[str, Any]]:
    """Return role definitions for a template id."""
    template = FLEET_TEMPLATES.get(template_id, {})
    roles = template.get("roles", [])
    if isinstance(roles, list):
        return roles
    return []
