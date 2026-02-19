"""Tests for Qwen OAuth handler."""

import kabot.auth.handlers.qwen_oauth as qwen_oauth


def test_qwen_oauth_handler_exists():
    handler = qwen_oauth.QwenOAuthHandler()
    assert handler is not None
    assert handler.name == "Qwen (OAuth)"


def test_qwen_oauth_saves_under_qwen_portal_provider(monkeypatch):
    monkeypatch.setattr(
        qwen_oauth,
        "_request_device_code",
        lambda challenge: {
            "user_code": "ABCD-EFGH",
            "verification_uri": "https://chat.qwen.ai/verify",
            "device_code": "dev-code",
            "expires_in": 10,
            "interval": 1,
        },
    )
    monkeypatch.setattr(qwen_oauth.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(qwen_oauth.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        qwen_oauth,
        "_poll_token",
        lambda device_code, verifier: {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
            "resource_url": "https://portal.qwen.ai",
        },
    )

    handler = qwen_oauth.QwenOAuthHandler()
    result = handler.authenticate()

    assert "providers" in result
    assert "qwen-portal" in result["providers"]
    provider = result["providers"]["qwen-portal"]
    assert provider["oauth_token"] == "access"
    assert provider["refresh_token"] == "refresh"
    assert provider["token_type"] == "oauth"
    assert provider["api_base"].endswith("/v1")
