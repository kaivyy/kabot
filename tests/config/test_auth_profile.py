# tests/config/test_auth_profile.py
from kabot.config.schema import AuthProfile

def test_auth_profile_has_refresh_fields():
    profile = AuthProfile(
        name="work",
        oauth_token="access_abc",
        refresh_token="refresh_xyz",
        expires_at=1739577600000,
        token_type="oauth",
        client_id="app_EMo...",
    )
    assert profile.refresh_token == "refresh_xyz"
    assert profile.expires_at == 1739577600000
    assert profile.token_type == "oauth"
    assert profile.client_id == "app_EMo..."

def test_auth_profile_is_expired():
    import time
    expired = AuthProfile(
        name="old",
        oauth_token="old_token",
        expires_at=int(time.time() * 1000) - 60_000,  # Expired 1 minute ago
        token_type="oauth",
    )
    assert expired.is_expired()

    valid = AuthProfile(
        name="fresh",
        oauth_token="fresh_token",
        expires_at=int(time.time() * 1000) + 3600_000,  # Valid for 1 hour
        token_type="oauth",
    )
    assert not valid.is_expired()

def test_api_key_never_expires():
    profile = AuthProfile(name="apikey", api_key="sk-abc")
    assert not profile.is_expired()
