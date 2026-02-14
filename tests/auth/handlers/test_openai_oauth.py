"""Tests for OpenAI OAuth handler."""


def test_openai_oauth_handler_exists():
    """OpenAIOAuthHandler class should exist."""
    from kabot.auth.handlers.openai_oauth import OpenAIOAuthHandler
    assert OpenAIOAuthHandler is not None


def test_openai_oauth_handler_has_name():
    """OpenAIOAuthHandler should have name property."""
    from kabot.auth.handlers.openai_oauth import OpenAIOAuthHandler
    handler = OpenAIOAuthHandler()
    assert handler.name == "OpenAI (OAuth)"


def test_openai_oauth_constants():
    """OpenAI OAuth should use real Codex PKCE credentials."""
    from kabot.auth.handlers.openai_oauth import (
        OPENAI_CLIENT_ID,
        OPENAI_AUTHORIZE_URL,
        OPENAI_TOKEN_URL,
    )
    assert OPENAI_CLIENT_ID == "app_EMoamEEZ73f0CkXaXp7hrann"
    assert OPENAI_AUTHORIZE_URL == "https://auth.openai.com/oauth/authorize"
    assert OPENAI_TOKEN_URL == "https://auth.openai.com/oauth/token"


def test_openai_pkce_generation():
    """PKCE verifier and challenge should be generated correctly."""
    from kabot.auth.handlers.openai_oauth import _generate_pkce
    verifier, challenge = _generate_pkce()
    assert len(verifier) > 20
    assert len(challenge) > 20
    assert verifier != challenge
