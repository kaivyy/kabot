"""Multi-method authentication menu structure."""

from typing import Any, Dict, List

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
            },
            "gemini_cli": {
                "label": "Google Gemini CLI OAuth",
                "description": "Official CLI integration (Auto-extract secrets)",
                "handler": "kabot.auth.handlers.google_gemini_cli.GoogleGeminiCLIHandler"
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
            },
            "oauth": {
                "label": "Browser Login (OAuth)",
                "description": "MiniMax portal login",
                "handler": "kabot.auth.handlers.minimax_oauth.MiniMaxOAuthHandler"
            }
        }
    },
    "dashscope": {
        "name": "Qwen (DashScope)",
        "description": "Alibaba Cloud Qwen models",
        "methods": {
            "api_key": {
                "label": "API Key (Manual)",
                "description": "Standard DashScope API key",
                "handler": "kabot.auth.handlers.simple.DashScopeKeyHandler"
            },
            "oauth": {
                "label": "Browser Login (OAuth)",
                "description": "Qwen Portal OAuth",
                "handler": "kabot.auth.handlers.qwen_oauth.QwenOAuthHandler"
            }
        }
    },
    "deepseek": {
        "name": "DeepSeek",
        "description": "DeepSeek Coder, Chat V2",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "DeepSeek API key",
                "handler": "kabot.auth.handlers.simple.DeepSeekKeyHandler"
            }
        }
    },
    "mistral": {
        "name": "Mistral",
        "description": "Mistral Large, Pixtral, Voxtral",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "Mistral API key",
                "handler": "kabot.auth.handlers.simple.MistralKeyHandler"
            }
        }
    },
    "kilocode": {
        "name": "Kilo Gateway",
        "description": "Unified gateway for multiple providers",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "Kilo Gateway API key",
                "handler": "kabot.auth.handlers.simple.KiloCodeKeyHandler"
            }
        }
    },
    "together": {
        "name": "Together AI",
        "description": "GLM, Llama, DeepSeek, Kimi catalog",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "Together API key",
                "handler": "kabot.auth.handlers.simple.TogetherKeyHandler"
            }
        }
    },
    "venice": {
        "name": "Venice AI",
        "description": "Privacy-focused + anonymized premium routes",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "Venice API key",
                "handler": "kabot.auth.handlers.simple.VeniceKeyHandler"
            }
        }
    },
    "huggingface": {
        "name": "Hugging Face",
        "description": "Inference router for many OSS models",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "HF token (HF_TOKEN)",
                "handler": "kabot.auth.handlers.simple.HuggingFaceKeyHandler"
            }
        }
    },
    "qianfan": {
        "name": "Qianfan",
        "description": "Baidu unified OpenAI-compatible endpoint",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "Qianfan API key",
                "handler": "kabot.auth.handlers.simple.QianfanKeyHandler"
            }
        }
    },
    "nvidia": {
        "name": "NVIDIA",
        "description": "NVIDIA hosted inference (OpenAI-compatible)",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "NVIDIA API key",
                "handler": "kabot.auth.handlers.simple.NvidiaKeyHandler"
            }
        }
    },
    "xai": {
        "name": "xAI",
        "description": "Grok models via xAI API",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "xAI API key",
                "handler": "kabot.auth.handlers.simple.XAIKeyHandler"
            }
        }
    },
    "cerebras": {
        "name": "Cerebras",
        "description": "Cerebras Inference API",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "Cerebras API key",
                "handler": "kabot.auth.handlers.simple.CerebrasKeyHandler"
            }
        }
    },
    "opencode": {
        "name": "OpenCode Zen",
        "description": "Curated coding-oriented model access",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "OpenCode Zen API key",
                "handler": "kabot.auth.handlers.simple.OpenCodeKeyHandler"
            }
        }
    },
    "xiaomi": {
        "name": "Xiaomi MiMo",
        "description": "MiMo provider endpoint",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "Xiaomi MiMo API key",
                "handler": "kabot.auth.handlers.simple.XiaomiKeyHandler"
            }
        }
    },
    "volcengine": {
        "name": "Volcano Engine",
        "description": "Doubao and China-region model gateway",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "Volcano Engine API key",
                "handler": "kabot.auth.handlers.simple.VolcengineKeyHandler"
            }
        }
    },
    "byteplus": {
        "name": "BytePlus",
        "description": "International ARK model gateway",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "BytePlus API key",
                "handler": "kabot.auth.handlers.simple.BytePlusKeyHandler"
            }
        }
    },
    "synthetic": {
        "name": "Synthetic",
        "description": "Anthropic-compatible routed model catalog",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "Synthetic API key",
                "handler": "kabot.auth.handlers.simple.SyntheticKeyHandler"
            }
        }
    },
    "cloudflare-ai-gateway": {
        "name": "Cloudflare AI Gateway",
        "description": "Proxy Anthropic/OpenAI traffic via Cloudflare gateway",
        "methods": {
            "api_key": {
                "label": "API Key + Gateway IDs",
                "description": "Cloudflare gateway key and account/gateway IDs",
                "handler": "kabot.auth.handlers.simple.CloudflareAIGatewayKeyHandler"
            }
        }
    },
    "vercel-ai-gateway": {
        "name": "Vercel AI Gateway",
        "description": "Unified AI routing through Vercel gateway",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "Vercel AI Gateway API key",
                "handler": "kabot.auth.handlers.simple.VercelAIGatewayKeyHandler"
            }
        }
    },
    "groq": {
        "name": "Groq",
        "description": "Llama 4 Scout (Fast inference)",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "Groq Cloud API key",
                "handler": "kabot.auth.handlers.simple.GroqKeyHandler"
            }
        }
    },
    "openrouter": {
        "name": "OpenRouter",
        "description": "Aggregator for Claude, GPT, Llama, etc.",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "OpenRouter API key",
                "handler": "kabot.auth.handlers.simple.OpenRouterKeyHandler"
            }
        }
    },
    "zhipu": {
        "name": "Zhipu AI (GLM)",
        "description": "ChatGLM-4, GLM-4V",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "Zhipu AI BigModel key",
                "handler": "kabot.auth.handlers.simple.ZhipuKeyHandler"
            }
        }
    },
    "aihubmix": {
        "name": "AIHubMix",
        "description": "Mixed model aggregator",
        "methods": {
            "api_key": {
                "label": "API Key",
                "description": "AIHubMix API key",
                "handler": "kabot.auth.handlers.simple.AiHubMixKeyHandler"
            }
        }
    },
    "letta": {
        "name": "Letta (MemGPT)",
        "description": "Long-term memory agent server",
        "methods": {
            "api_key": {
                "label": "API Key + URL",
                "description": "Connect to Letta server",
                "handler": "kabot.auth.handlers.simple.LettaKeyHandler"
            }
        }
    },
    "vllm": {
        "name": "vLLM",
        "description": "Open-source LLM inference server",
        "methods": {
            "api_key": {
                "label": "Configuration",
                "description": "Connect to vLLM server",
                "handler": "kabot.auth.handlers.simple.VLLMHandler"
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

