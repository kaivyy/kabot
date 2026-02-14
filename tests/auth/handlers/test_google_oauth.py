"""Tests for Google OAuth handler."""

def test_google_oauth_handler_exists():
    """GoogleOAuthHandler class should exist."""
    from kabot.auth.handlers.google_oauth import GoogleOAuthHandler
    assert GoogleOAuthHandler is not None


def test_google_oauth_handler_has_name():
    """GoogleOAuthHandler should have name property."""
    from kabot.auth.handlers.google_oauth import GoogleOAuthHandler
    handler = GoogleOAuthHandler()
    assert handler.name == "Google Gemini (OAuth)"


def test_google_oauth_constants():
    """Google OAuth should use real Antigravity credentials."""
    from kabot.auth.handlers.google_oauth import (
        GOOGLE_CLIENT_ID,
        GOOGLE_CLIENT_SECRET,
        GOOGLE_AUTH_URL,
        GOOGLE_TOKEN_URL,
        REDIRECT_PORT,
    )
    assert GOOGLE_CLIENT_ID.endswith(".apps.googleusercontent.com")
    assert GOOGLE_CLIENT_SECRET.startswith("GOCSPX-")
    assert GOOGLE_AUTH_URL == "https://accounts.google.com/o/oauth2/v2/auth"
    assert GOOGLE_TOKEN_URL == "https://oauth2.googleapis.com/token"
    assert REDIRECT_PORT == 51121


def test_google_pkce_generation():
    """PKCE verifier and challenge should be generated correctly."""
    from kabot.auth.handlers.google_oauth import _generate_pkce
    verifier, challenge = _generate_pkce()
    assert len(verifier) > 20
    assert len(challenge) > 20
    # Challenge should be different from verifier (it's the SHA256 hash)
    assert verifier != challenge
