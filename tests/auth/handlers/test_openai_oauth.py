"""Tests for OpenAI OAuth handler."""

from kabot.auth.handlers import openai_oauth


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


def test_parse_callback_input_accepts_query_blob():
    parsed = openai_oauth._parse_callback_input("code=abc123&state=good", "expected")
    assert parsed == {"code": "abc123", "state": "good"}


def test_parse_callback_input_accepts_fragment_url():
    parsed = openai_oauth._parse_callback_input(
        "http://localhost:1455/auth/callback#code=abc123&state=good",
        "expected",
    )
    assert parsed == {"code": "abc123", "state": "good"}


def test_headless_flow_rejects_state_mismatch(monkeypatch):
    handler = openai_oauth.OpenAIOAuthHandler()
    monkeypatch.setattr(
        openai_oauth.Prompt,
        "ask",
        lambda *args, **kwargs: "http://localhost:1455/auth/callback?code=abc123&state=evil",
    )

    called = {"value": False}

    def fake_exchange(code: str, verifier: str):
        called["value"] = True
        return {"providers": {"openai_codex": {"oauth_token": "tok"}}}

    monkeypatch.setattr(handler, "_exchange_and_return", fake_exchange)

    result = handler._headless_flow("http://example.com", "expected", "verifier")
    assert result is None
    assert called["value"] is False


def test_exchange_and_return_targets_openai_codex_provider(monkeypatch):
    async def fake_exchange_code(code: str, verifier: str):
        return {
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_in": 3600,
        }

    monkeypatch.setattr(openai_oauth, "_exchange_code", fake_exchange_code)

    handler = openai_oauth.OpenAIOAuthHandler()
    result = handler._exchange_and_return("abc123", "verifier")
    assert result is not None
    assert "openai_codex" in result["providers"]
