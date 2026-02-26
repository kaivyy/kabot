"""Section binders for SetupWizard."""
from kabot.cli.wizard.sections.channels import bind_channels_sections
from kabot.cli.wizard.sections.core import bind_core_sections
from kabot.cli.wizard.sections.model_auth import bind_model_auth_sections
from kabot.cli.wizard.sections.operations import bind_operations_sections
from kabot.cli.wizard.sections.tools_gateway_skills import bind_tools_gateway_skills_sections

__all__ = [
    "bind_core_sections",
    "bind_model_auth_sections",
    "bind_tools_gateway_skills_sections",
    "bind_channels_sections",
    "bind_operations_sections",
]
