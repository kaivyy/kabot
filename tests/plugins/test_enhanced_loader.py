"""Tests for enhanced plugin loader (Phase 10)."""

import json

from kabot.plugins.hooks import HookManager
from kabot.plugins.loader import PluginManifest, load_dynamic_plugins, load_plugins
from kabot.plugins.registry import PluginRegistry


def test_load_skill_md_format(tmp_path):
    """Test loading a SKILL.md plugin (legacy format)."""
    plugin_dir = tmp_path / "test_skill"
    plugin_dir.mkdir()

    # Create SKILL.md with frontmatter
    skill_content = """---
name: Test Skill
description: A test skill
version: 2.0.0
---

# Test Skill

This is a test skill."""

    (plugin_dir / "SKILL.md").write_text(skill_content)

    registry = PluginRegistry()
    loaded = load_plugins(tmp_path, registry)

    assert len(loaded) == 1
    assert loaded[0].name == "Test Skill"


def test_load_plugin_json_format(tmp_path):
    """Test loading a plugin.json plugin."""
    plugin_dir = tmp_path / "test_plugin"
    plugin_dir.mkdir()

    # Create plugin.json
    manifest = {
        "id": "com.test.plugin",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "entry_point": "main.py"
    }
    (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

    # Create entry point
    (plugin_dir / "main.py").write_text("# Test plugin entry point")

    registry = PluginRegistry()
    hooks = HookManager()
    loaded = load_dynamic_plugins(tmp_path, registry, hooks)

    assert len(loaded) == 1
    assert loaded[0].name == "Test Plugin"


def test_load_mixed_plugin_formats(tmp_path):
    """Test loading both plugin.json and SKILL.md plugins."""
    # Create plugin.json plugin
    json_plugin = tmp_path / "json_plugin"
    json_plugin.mkdir()
    manifest = {
        "id": "com.test.json",
        "name": "JSON Plugin",
        "version": "1.0.0",
        "entry_point": "main.py"
    }
    (json_plugin / "plugin.json").write_text(json.dumps(manifest))
    (json_plugin / "main.py").write_text("# JSON plugin")

    # Create SKILL.md plugin
    skill_plugin = tmp_path / "skill_plugin"
    skill_plugin.mkdir()
    skill_content = """---
name: Skill Plugin
version: 1.0.0
---
# Skill"""
    (skill_plugin / "SKILL.md").write_text(skill_content)

    registry = PluginRegistry()
    hooks = HookManager()

    # Load both types
    loaded_skills = load_plugins(tmp_path, registry)
    loaded_dynamic = load_dynamic_plugins(tmp_path, registry, hooks)

    assert len(loaded_skills) == 1
    assert len(loaded_dynamic) == 1
    assert loaded_skills[0].name == "Skill Plugin"
    assert loaded_dynamic[0].name == "JSON Plugin"


def test_plugin_with_missing_entry_point(tmp_path):
    """Test that plugin with missing entry point is handled gracefully."""
    plugin_dir = tmp_path / "missing_entry"
    plugin_dir.mkdir()

    manifest = {
        "id": "com.test.missing",
        "name": "Missing Entry",
        "version": "1.0.0",
        "entry_point": "nonexistent.py"
    }
    (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

    registry = PluginRegistry()
    hooks = HookManager()
    loaded = load_dynamic_plugins(tmp_path, registry, hooks)

    # Plugin should not load if entry point is missing
    assert len(loaded) == 0


def test_load_plugins_with_hooks_manager(tmp_path):
    """Test loading plugins with HookManager integration."""
    plugin_dir = tmp_path / "hooks_plugin"
    plugin_dir.mkdir()

    # Create plugin with hooks
    manifest = {
        "id": "com.test.hooks",
        "name": "Hooks Plugin",
        "version": "1.0.0",
        "entry_point": "main.py",
        "hooks": ["ON_MESSAGE_RECEIVED"]
    }
    (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

    # Create entry point with register function
    entry_code = """
async def on_message(message):
    return f"Processed: {message}"

def register(registry, hooks):
    if hooks:
        hooks.on("ON_MESSAGE_RECEIVED", on_message)
"""
    (plugin_dir / "main.py").write_text(entry_code)

    hooks_manager = HookManager()
    registry = PluginRegistry()
    loaded = load_dynamic_plugins(tmp_path, registry, hooks_manager)

    assert len(loaded) == 1
    assert hooks_manager.handler_count("ON_MESSAGE_RECEIVED") == 1


def test_plugin_manifest_validation():
    """Test PluginManifest validation."""
    # Valid manifest
    manifest = PluginManifest(
        id="com.test.valid",
        name="Valid Plugin",
        version="1.0.0"
    )
    issues = manifest.validate()
    assert len(issues) == 0

    # Invalid - missing id
    manifest = PluginManifest(
        id="",
        name="Invalid",
        version="1.0.0"
    )
    issues = manifest.validate()
    assert len(issues) > 0


def test_invalid_plugin_json_skipped(tmp_path):
    """Test that invalid plugin.json is skipped gracefully."""
    plugin_dir = tmp_path / "invalid_plugin"
    plugin_dir.mkdir()

    # Create invalid plugin.json
    (plugin_dir / "plugin.json").write_text("invalid json{")

    registry = PluginRegistry()
    hooks = HookManager()
    loaded = load_dynamic_plugins(tmp_path, registry, hooks)

    # Should skip invalid plugin
    assert len(loaded) == 0
