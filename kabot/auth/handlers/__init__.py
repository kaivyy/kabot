"""Authentication handlers for multiple providers and methods."""

from kabot.auth.handlers.base import AuthHandler
from kabot.auth.handlers.openai_key import OpenAIKeyHandler
from kabot.auth.handlers.openai_oauth import OpenAIOAuthHandler
from kabot.auth.handlers.anthropic_key import AnthropicKeyHandler
from kabot.auth.handlers.anthropic_token import AnthropicTokenHandler
from kabot.auth.handlers.google_key import GoogleKeyHandler
from kabot.auth.handlers.google_oauth import GoogleOAuthHandler
from kabot.auth.handlers.ollama_url import OllamaURLHandler
from kabot.auth.handlers.kimi_key import KimiKeyHandler
from kabot.auth.handlers.kimi_code import KimiCodeHandler
from kabot.auth.handlers.minimax_key import MiniMaxKeyHandler
from kabot.auth.handlers.minimax_coding import MiniMaxCodingHandler

__all__ = [
    "AuthHandler",
    "OpenAIKeyHandler",
    "OpenAIOAuthHandler",
    "AnthropicKeyHandler",
    "AnthropicTokenHandler",
    "GoogleKeyHandler",
    "GoogleOAuthHandler",
    "OllamaURLHandler",
    "KimiKeyHandler",
    "KimiCodeHandler",
    "MiniMaxKeyHandler",
    "MiniMaxCodingHandler",
]
