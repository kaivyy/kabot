from kabot.auth.handlers.openai import OpenAIHandler
from kabot.auth.handlers.anthropic import AnthropicHandler
from kabot.auth.handlers.google import GoogleHandler
from kabot.auth.handlers.ollama import OllamaHandler

# Dictionary mapping provider IDs to their handler classes
AUTH_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "description": "GPT-4o, o1-preview, etc.",
        "handler": OpenAIHandler
    },
    "anthropic": {
        "name": "Anthropic",
        "description": "Claude 3.5 Sonnet, Opus, etc.",
        "handler": AnthropicHandler
    },
    "google": {
        "name": "Google Gemini",
        "description": "Gemini 1.5 Pro, Flash",
        "handler": GoogleHandler
    },
    "ollama": {
        "name": "Ollama",
        "description": "Local models (Llama 3, Mistral)",
        "handler": OllamaHandler
    }
}

def get_auth_choices():
    """Returns a list of choices for the interactive menu."""
    return [
        {"name": f"{meta['name']} - {meta['description']}", "value": key}
        for key, meta in AUTH_PROVIDERS.items()
    ]
