"""Tests for plugin lifecycle manager."""

import json
from pathlib import Path


def _write_dynamic_plugin(root: Path, plugin_id: str, version: str = "1.0.0", deps: list[str] | None = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "plugin.json").write_text(
        (
            "{\n"
            f'  "id": "{plugin_id}",\n'
            f'  "name": "{plugin_id.title()}",\n'
            f'  "version": "{version}",\n'
            '  "description": "test plugin",\n'
            '  "entry_point": "main.py",\n'
            f'  "dependencies": {json.dumps(deps or [])}\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    (root / "main.py").write_text("def register(registry=None, hooks=None):\n    return None\n", encoding="utf-8")


def test_plugin_manager_install_enable_disable_update_and_remove(tmp_path):
    from kabot.plugins.manager import PluginManager

    source = tmp_path / "source-plugin"
    _write_dynamic_plugin(source, "demo_plugin", "1.0.0")

    manager = PluginManager(tmp_path / "workspace" / "plugins")
    plugin_id = manager.install_from_path(source)
    assert plugin_id == "demo_plugin"

    listed = manager.list_plugins()
    assert len(listed) == 1
    assert listed[0]["id"] == "demo_plugin"
    assert listed[0]["enabled"] is True
    assert listed[0]["version"] == "1.0.0"

    assert manager.set_enabled("demo_plugin", False) is True
    assert manager.list_plugins()[0]["enabled"] is False

    assert manager.set_enabled("demo_plugin", True) is True
    assert manager.list_plugins()[0]["enabled"] is True

    # Update from source with a new version.
    _write_dynamic_plugin(source, "demo_plugin", "1.1.0")
    assert manager.update_plugin("demo_plugin") is True
    assert manager.list_plugins()[0]["version"] == "1.1.0"

    assert manager.uninstall_plugin("demo_plugin") is True
    assert manager.list_plugins() == []


def test_plugin_manager_doctor_detects_missing_dependency(tmp_path):
    from kabot.plugins.manager import PluginManager

    source = tmp_path / "source-plugin"
    _write_dynamic_plugin(source, "broken_plugin", "0.1.0", deps=["definitely_missing_pkg_for_test_123"])

    manager = PluginManager(tmp_path / "workspace" / "plugins")
    manager.install_from_path(source)

    report = manager.doctor("broken_plugin")
    assert report["plugin"] == "broken_plugin"
    assert report["ok"] is False
    assert any("Missing dependency" in issue for issue in report["issues"])


def test_plugin_manager_install_from_git_tracks_source_and_ref(monkeypatch, tmp_path):
    from kabot.plugins.manager import PluginManager

    source = tmp_path / "source-plugin"
    _write_dynamic_plugin(source, "git_plugin", "2.0.0")

    manager = PluginManager(tmp_path / "workspace" / "plugins")

    def _fake_clone(url: str, ref: str | None):
        assert url == "https://example.com/repo.git"
        assert ref == "v2.0.0"
        return source

    monkeypatch.setattr(manager, "_clone_git_repo", _fake_clone)
    plugin_id = manager.install_from_git("https://example.com/repo.git", ref="v2.0.0")

    assert plugin_id == "git_plugin"
    state = manager._load_state()
    src = state["sources"]["git_plugin"]
    assert src["type"] == "git"
    assert src["url"] == "https://example.com/repo.git"
    assert src["ref"] == "v2.0.0"


def test_plugin_manager_update_rolls_back_on_failure(tmp_path):
    from kabot.plugins.manager import PluginManager

    source = tmp_path / "source-plugin"
    _write_dynamic_plugin(source, "rollback_plugin", "1.0.0")
    manager = PluginManager(tmp_path / "workspace" / "plugins")
    manager.install_from_path(source)

    # Break source so update fails.
    (source / "plugin.json").unlink()
    marker = source / "SKILL.md"
    if marker.exists():
        marker.unlink()

    ok = manager.update_plugin("rollback_plugin")
    assert ok is False
    listed = manager.list_plugins()
    assert listed[0]["id"] == "rollback_plugin"
    assert listed[0]["version"] == "1.0.0"
