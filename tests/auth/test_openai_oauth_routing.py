"""Routing tests for OpenAI Codex OAuth credentials."""

from kabot.auth.manager import AuthManager
from kabot.config.schema import Config


def test_save_credentials_maps_openai_codex_hyphenated_provider(monkeypatch):
    cfg = Config()
    flags = {"saved": False}

    monkeypatch.setattr("kabot.auth.manager.load_config", lambda: cfg)
    monkeypatch.setattr(
        "kabot.auth.manager.save_config",
        lambda _cfg: flags.__setitem__("saved", True),
    )

    manager = AuthManager()
    ok = manager._save_credentials(
        {
            "providers": {
                "openai-codex": {
                    "oauth_token": "tok",
                    "refresh_token": "ref",
                    "token_type": "oauth",
                }
            }
        }
    )

    assert ok is True
    assert flags["saved"] is True
    assert "default" in cfg.providers.openai_codex.profiles
    assert cfg.providers.openai_codex.profiles["default"].oauth_token == "tok"


def test_save_credentials_maps_qwen_portal_to_dashscope(monkeypatch):
    cfg = Config()
    flags = {"saved": False}

    monkeypatch.setattr("kabot.auth.manager.load_config", lambda: cfg)
    monkeypatch.setattr(
        "kabot.auth.manager.save_config",
        lambda _cfg: flags.__setitem__("saved", True),
    )

    manager = AuthManager()
    ok = manager._save_credentials(
        {
            "providers": {
                "qwen-portal": {
                    "oauth_token": "tok",
                    "refresh_token": "ref",
                    "token_type": "oauth",
                    "api_base": "https://portal.qwen.ai/v1",
                }
            }
        }
    )

    assert ok is True
    assert flags["saved"] is True
    assert "default" in cfg.providers.dashscope.profiles
    assert cfg.providers.dashscope.profiles["default"].oauth_token == "tok"
    assert cfg.providers.dashscope.profiles["default"].api_base == "https://portal.qwen.ai/v1"
