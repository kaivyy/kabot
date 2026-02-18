"""Model ID validation and alias resolution."""
from typing import Optional
from kabot.providers.registry import ModelRegistry


def validate_format(model_id: str) -> bool:
    """Check if model ID follows provider/model-name format."""
    return "/" in model_id and len(model_id.split("/")) == 2


def resolve_alias(alias: str) -> Optional[str]:
    """Resolve alias to full model ID."""
    registry = ModelRegistry()

    # Check if it's a registered alias
    if alias in registry._aliases:
        return registry._aliases[alias]

    return None


def suggest_alternatives(invalid_input: str) -> list[str]:
    """Suggest valid alternatives for invalid input."""
    registry = ModelRegistry()
    suggestions = []

    # Check if it's close to an alias
    for alias_name, model_id in registry._aliases.items():
        if alias_name in invalid_input.lower() or invalid_input.lower() in alias_name:
            suggestions.append(f"{model_id} (alias: {alias_name})")

    # Check if it's a model name without provider
    if "/" not in invalid_input:
        for model in registry.list_models():
            if invalid_input.lower() in model.id.lower():
                suggestions.append(model.id)

    return suggestions[:3]  # Return top 3
