"""Authentication handlers for multiple providers and methods."""

from kabot.auth.handlers.base import AuthHandler
from kabot.auth.handlers.openai_key import OpenAIKeyHandler
from kabot.auth.handlers.anthropic_key import AnthropicKeyHandler
from kabot.auth.handlers.google_key import GoogleKeyHandler
from kabot.auth.handlers.ollama_url import OllamaURLHandler
from kabot.auth.handlers.kimi_key import KimiKeyHandler
from kabot.auth.handlers.kimi_code import KimiCodeHandler
from kabot.auth.handlers.minimax_key import MiniMaxKeyHandler
from kabot.auth.handlers.minimax_coding import MiniMaxCodingHandler

__all__ = [
    "AuthHandler",
    "OpenAIKeyHandler",
    "AnthropicKeyHandler",
    "GoogleKeyHandler",
    "OllamaURLHandler",
    "KimiKeyHandler",
    "KimiCodeHandler",
    "MiniMaxKeyHandler",
    "MiniMaxCodingHandler",
]
