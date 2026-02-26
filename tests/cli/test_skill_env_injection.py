from types import SimpleNamespace

from kabot.cli.commands import _inject_skill_env

import os


def test_inject_skill_env_reads_entries_format(monkeypatch):
    monkeypatch.delenv("NOTION_API_KEY", raising=False)

    config = SimpleNamespace(
        skills={
            "entries": {
                "notion": {
                    "env": {
                        "NOTION_API_KEY": "entries-key",
                    }
                }
            }
        }
    )

    _inject_skill_env(config)

    assert "NOTION_API_KEY" in os.environ
    assert os.environ["NOTION_API_KEY"] == "entries-key"


def test_inject_skill_env_reads_legacy_format(monkeypatch):
    monkeypatch.delenv("LEGACY_KEY", raising=False)

    config = SimpleNamespace(
        skills={
            "legacy-skill": {
                "env": {
                    "LEGACY_KEY": "legacy-value",
                }
            }
        }
    )

    _inject_skill_env(config)

    assert os.environ["LEGACY_KEY"] == "legacy-value"
