"""Tests for legacy Threads config migration into integrations.meta."""

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
