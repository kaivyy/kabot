"""Regression tests for config loader UTF-8 BOM handling."""

import json
from pathlib import Path

from kabot.config.loader import load_config


def test_load_config_accepts_utf8_bom(tmp_path: Path):
    config_path = tmp_path / "config.json"
    payload = {
        "providers": {"openaiCodex": {"profiles": {"default": {"oauthToken": "tok"}}}},
        "agents": {"defaults": {"model": "openai-codex/gpt-5.3-codex"}},
    }
    # Simulate PowerShell Set-Content UTF8 behavior (BOM-prefixed JSON).
    config_path.write_text(json.dumps(payload), encoding="utf-8-sig")

    cfg = load_config(config_path)

    assert cfg.providers.openai_codex.profiles["default"].oauth_token == "tok"
