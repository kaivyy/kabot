"""Multi-method authentication menu structure."""

from typing import Dict, List, Any

# Provider definitions with multiple auth methods per provider
AUTH_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "name": "OpenAI",
        "description": "GPT-4o, o1-preview, etc.",
        "methods": {
            "api_key": {
                "label": "API Key (Manual)",
                "description": "Standard API key (sk-...)",
                "handler": "kabot.auth.handlers.openai_key.OpenAIKeyHandler"
            },
            "oauth": {
                "label": "Browser Login (OAuth)",
                "description": "ChatGPT subscription login",
                "handler": "kabot.auth.handlers.openai_oauth.OpenAIOAuthHandler"
            }
        }
    },
    "anthropic": {
        "name": "Anthropic",
        "description": "Claude 3.5 Sonnet, Opus, etc.",
        "methods": {
            "api_key": {
                "label": "API Key (Manual)",
                "description": "Standard API key (sk-ant-...)",
                "handler": "kabot.auth.handlers.anthropic_key.AnthropicKeyHandler"
            },
            "setup_token": {
                "label": "Setup Token",
                "description": "From 'claude setup-token' command",
                "handler": "kabot.auth.handlers.anthropic_token.AnthropicTokenHandler"
            }
        }
    },
    "google": {
        "name": "Google Gemini",
        "description": "Gemini 1.5 Pro, Flash",
        "methods": {
            "api_key": {
                "label": "API Key (Manual)",
                "description": "Standard API key (AIza...)",
                "handler": "kabot.auth.handlers.google_key.GoogleKeyHandler"
            },
            "oauth": {
                "label": "Browser Login (OAuth)",
                "description": "Google account login",
                "handler": "kabot.auth.handlers.google_oauth.GoogleOAuthHandler"
            }
        }
    },
    "ollama": {
        "name": "Ollama",
        "description": "Local models (Llama 3, Mistral)",
        "methods": {
            "url": {
                "label": "Local URL",
                "description": "Configure local Ollama server",
                "handler": "kabot.auth.handlers.ollama_url.OllamaURLHandler"
            }
        }
    },
    "kimi": {
        "name": "Kimi (Moonshot AI)",
        "description": "Kimi K1, K2.5 - Long context",
        "methods": {
            "api_key": {
                "label": "API Key (General)",
                "description": "Standard Moonshot API key",
                "handler": "kabot.auth.handlers.kimi_key.KimiKeyHandler"
            },
            "kimi_code": {
                "label": "Kimi Code (Subscription)",
                "description": "Coding-specialized subscription plan",
                "handler": "kabot.auth.handlers.kimi_code.KimiCodeHandler"
            }
        }
    },
    "minimax": {
        "name": "MiniMax",
        "description": "MiniMax M2, M2.1 models",
        "methods": {
            "api_key": {
                "label": "API Key (Pay-as-you-go)",
                "description": "Token-based billing",
                "handler": "kabot.auth.handlers.minimax_key.MiniMaxKeyHandler"
            },
            "coding_plan": {
                "label": "Coding Plan (Subscription)",
                "description": "Unlimited monthly subscription",
                "handler": "kabot.auth.handlers.minimax_coding.MiniMaxCodingHandler"
            }
        }
    }
}


def get_auth_choices() -> List[Dict[str, str]]:
    """Returns list of provider choices for interactive menu."""
    return [
        {"name": f"{meta['name']} - {meta['description']}", "value": key}
        for key, meta in AUTH_PROVIDERS.items()
    ]


def get_method_choices(provider_id: str) -> List[Dict[str, str]]:
    """Returns list of method choices for a specific provider."""
    if provider_id not in AUTH_PROVIDERS:
        return []

    methods = AUTH_PROVIDERS[provider_id]["methods"]
    return [
        {
            "id": method_id,
            "label": method_info["label"],
            "description": method_info["description"]
        }
        for method_id, method_info in methods.items()
    ]
