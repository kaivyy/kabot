from kabot.config.skills_settings import (
    get_skill_entry,
    get_skills_entries,
    iter_skill_env_pairs,
    normalize_skills_settings,
    resolve_allow_bundled,
    resolve_install_settings,
    resolve_load_settings,
    set_skill_entry_env,
)


def test_normalize_skills_settings_merges_legacy_and_entries():
    raw = {
        "notion": {
            "env": {
                "NOTION_API_KEY": "legacy-notion-key",
            }
        },
        "entries": {
            "notion": {
                "enabled": True,
                "env": {
                    "NOTION_API_KEY": "entries-notion-key",
                    "NOTION_WORKSPACE_ID": "ws-1",
                },
            },
            "trello": {
                "apiKey": "trello-key",
            },
        },
        "allowBundled": ["cron", "github"],
        "load": {
            "managedDir": "~/.kabot/skills",
            "extraDirs": ["~/skills-pack-a", " ~/skills-pack-b "],
        },
    }

    normalized = normalize_skills_settings(raw)
    entries = normalized["entries"]

    assert entries["notion"]["enabled"] is True
    assert entries["notion"]["env"]["NOTION_API_KEY"] == "entries-notion-key"
    assert entries["notion"]["env"]["NOTION_WORKSPACE_ID"] == "ws-1"
    assert entries["trello"]["api_key"] == "trello-key"
    assert normalized["allow_bundled"] == ["cron", "github"]
    assert normalized["load"]["managed_dir"] == "~/.kabot/skills"
    assert normalized["load"]["extra_dirs"] == ["~/skills-pack-a", "~/skills-pack-b"]


def test_iter_skill_env_pairs_reads_entries_and_legacy():
    raw = {
        "legacy-skill": {
            "env": {
                "LEGACY_KEY": "legacy-value",
            }
        },
        "entries": {
            "new-skill": {
                "env": {
                    "NEW_KEY": "new-value",
                }
            }
        },
    }

    pairs = iter_skill_env_pairs(raw)
    got = {(skill, env_key, env_val) for skill, env_key, env_val in pairs}

    assert ("legacy-skill", "LEGACY_KEY", "legacy-value") in got
    assert ("new-skill", "NEW_KEY", "new-value") in got


def test_set_skill_entry_env_writes_into_entries():
    raw = {}

    updated = set_skill_entry_env(raw, "sag", "ELEVENLABS_API_KEY", "abc123")
    entry = get_skill_entry(updated, "sag")

    assert "entries" in updated
    assert entry["env"]["ELEVENLABS_API_KEY"] == "abc123"


def test_resolve_allow_bundled_and_load_settings():
    raw = {
        "allow_bundled": ["github", "cron"],
        "load": {
            "managed_dir": "~/.kabot/skills",
            "extra_dirs": ["~/a", "~/b"],
        },
    }

    assert resolve_allow_bundled(raw) == ["github", "cron"]
    load = resolve_load_settings(raw)
    assert load["managed_dir"] == "~/.kabot/skills"
    assert load["extra_dirs"] == ["~/a", "~/b"]


def test_get_skills_entries_accepts_legacy_flat_map():
    raw = {
        "trello": {"env": {"TRELLO_API_KEY": "value"}},
    }

    entries = get_skills_entries(raw)
    assert entries["trello"]["env"]["TRELLO_API_KEY"] == "value"


def test_normalize_skills_settings_defaults_install_mode_manual():
    normalized = normalize_skills_settings({})

    install = normalized["install"]
    assert install["mode"] == "manual"
    assert install["node_manager"] == "npm"
    assert install["prefer_brew"] is True


def test_resolve_install_settings_supports_camel_and_snake_case():
    raw = {
        "install": {
            "mode": "auto",
            "nodeManager": "pnpm",
            "preferBrew": False,
        }
    }

    resolved = resolve_install_settings(raw)

    assert resolved["mode"] == "auto"
    assert resolved["node_manager"] == "pnpm"
    assert resolved["prefer_brew"] is False
