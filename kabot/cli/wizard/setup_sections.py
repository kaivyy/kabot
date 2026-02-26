"""Bind extracted SetupWizard section methods from modular section files."""

from __future__ import annotations

from kabot.cli.wizard.sections import (
    bind_channels_sections,
    bind_core_sections,
    bind_model_auth_sections,
    bind_operations_sections,
    bind_tools_gateway_skills_sections,
)


def bind_setup_wizard_sections(cls):
    bind_core_sections(cls)
    bind_model_auth_sections(cls)
    bind_tools_gateway_skills_sections(cls)
    bind_channels_sections(cls)
    bind_operations_sections(cls)
    return cls
