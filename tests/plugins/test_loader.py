"""Tests for plugin loader."""

import pytest
from pathlib import Path
from kabot.plugins.loader import load_plugins
from kabot.plugins.registry import PluginRegistry


@pytest.fixture
def plugin_dir(tmp_path):
    """Create a temporary plugin directory with test plugins."""
    d = tmp_path / "plugins"
    d.mkdir()

    # Create a dummy plugin
    (d / "hello-world").mkdir()
    (d / "hello-world" / "SKILL.md").write_text("""---
name: hello-world
description: A friendly plugin
---
# Hello World
This is a test plugin.""")
    return d


def test_load_plugins(plugin_dir):
    """Test loading plugins from directory."""
    registry = PluginRegistry()
    loaded = load_plugins(plugin_dir, registry)

    assert len(loaded) == 1
    plugin = registry.get("hello-world")
    assert plugin is not None
    assert plugin.description == "A friendly plugin"


def test_load_plugins_empty_dir(tmp_path):
    """Test loading from empty directory."""
    registry = PluginRegistry()
    loaded = load_plugins(tmp_path, registry)
    assert len(loaded) == 0


def test_load_plugins_nonexistent_dir(tmp_path):
    """Test loading from non-existent directory."""
    registry = PluginRegistry()
    loaded = load_plugins(tmp_path / "nonexistent", registry)
    assert len(loaded) == 0
