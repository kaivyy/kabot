"""Tests for legacy Threads config migration into integrations.meta."""

import json
from pathlib import Path

from kabot.config.loader import load_config
from kabot.config.loader import _migrate_config, convert_keys
from kabot.config.schema import Config


def test_migrate_legacy_threads_block_into_integrations_meta():
    raw = {
        "threads": {
            "enabled": True,
            "user_id": "26179670184998096",
            "access_token_env": "THREADS_ACCESS_TOKEN",
        }
    }

    migrated = _migrate_config(raw)
    cfg = Config.model_validate(convert_keys(migrated))

    assert cfg.integrations.meta.enabled is True
    assert cfg.integrations.meta.threads_user_id == "26179670184998096"
    assert cfg.integrations.meta.access_token_env == "THREADS_ACCESS_TOKEN"


def test_migrate_legacy_threads_does_not_override_existing_meta():
    raw = {
        "integrations": {
            "meta": {
                "enabled": True,
                "threadsUserId": "existing-id",
            }
        },
        "threads": {
            "enabled": True,
            "user_id": "legacy-id",
        },
    }

    migrated = _migrate_config(raw)
    cfg = Config.model_validate(convert_keys(migrated))

    assert cfg.integrations.meta.threads_user_id == "existing-id"


def test_migrate_skills_legacy_flat_map_to_entries():
    raw = {
        "skills": {
            "notion": {"env": {"NOTION_API_KEY": "secret"}},
            "allowBundled": ["cron"],
            "load": {"managedDir": "~/.kabot/skills"},
        }
    }

    migrated = _migrate_config(raw)
    skills = migrated.get("skills", {})

    assert "entries" in skills
    assert "notion" in skills["entries"]
    assert skills["entries"]["notion"]["env"]["NOTION_API_KEY"] == "secret"
    assert skills["install"]["mode"] == "manual"


def test_load_config_persists_migrated_skills_and_creates_timestamped_backup(tmp_path: Path):
    config_path = tmp_path / "config.json"
    payload = {
        "skills": {
            "notion": {"env": {"NOTION_API_KEY": "from-legacy"}},
        },
        "agents": {"defaults": {"model": "openai-codex/gpt-5.3-codex"}},
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    cfg = load_config(config_path)

    assert cfg.skills["entries"]["notion"]["env"]["NOTION_API_KEY"] == "from-legacy"

    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    assert "entries" in persisted["skills"]
    backup_files = list((tmp_path / "backups").glob("config.*.pre-migration.json"))
    assert len(backup_files) == 1
