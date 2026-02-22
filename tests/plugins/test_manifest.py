"""Tests for plugin manifest system (Phase 10)."""

from kabot.plugins.loader import PluginManifest


def test_plugin_manifest_from_dict():
    """Test creating manifest from dict."""
    data = {
        "id": "com.example.test",
        "name": "Test Plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "entry_point": "main.py",
        "dependencies": ["requests>=2.0.0"],
        "hooks": ["ON_MESSAGE_RECEIVED"]
    }

    manifest = PluginManifest.from_dict(data)
    assert manifest.id == "com.example.test"
    assert manifest.name == "Test Plugin"
    assert manifest.version == "1.0.0"
    assert manifest.entry_point == "main.py"
    assert "requests>=2.0.0" in manifest.dependencies
    assert "ON_MESSAGE_RECEIVED" in manifest.hooks


def test_plugin_manifest_validation():
    """Test manifest validation."""
    # Valid manifest
    manifest = PluginManifest(
        id="com.example.test",
        name="Test Plugin",
        version="1.0.0",
        entry_point="main.py"
    )
    issues = manifest.validate()
    assert len(issues) == 0

    # Invalid manifest - missing id
    manifest = PluginManifest(
        id="",
        name="Test",
        version="1.0.0"
    )
    issues = manifest.validate()
    assert len(issues) > 0
    assert any("id" in issue.lower() for issue in issues)

    # Invalid manifest - missing name
    manifest = PluginManifest(
        id="test",
        name="",
        version="1.0.0"
    )
    issues = manifest.validate()
    assert len(issues) > 0
    assert any("name" in issue.lower() for issue in issues)
