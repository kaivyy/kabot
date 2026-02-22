"""Plugin lifecycle manager for install/update/enable/disable/doctor flows."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml


class PluginManager:
    """Manage workspace plugins with persisted lifecycle state."""

    def __init__(self, plugins_dir: Path):
        self.plugins_dir = Path(plugins_dir).expanduser()
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self._state_path = self.plugins_dir / ".state.json"

    def _clone_git_repo(self, url: str, ref: str | None = None) -> Path:
        """Clone a git repo to a temporary directory and optionally checkout ref."""
        temp_dir = Path(tempfile.mkdtemp(prefix="kabot-plugin-git-"))
        clone_cmd = ["git", "clone", url, str(temp_dir)]
        clone_result = subprocess.run(clone_cmd, capture_output=True, text=True)
        if clone_result.returncode != 0:
            raise ValueError(clone_result.stderr.strip() or f"git clone failed for {url}")

        if ref:
            checkout_cmd = ["git", "-C", str(temp_dir), "checkout", ref]
            checkout_result = subprocess.run(checkout_cmd, capture_output=True, text=True)
            if checkout_result.returncode != 0:
                raise ValueError(checkout_result.stderr.strip() or f"git checkout failed for ref {ref}")

        return temp_dir

    def _load_state(self) -> dict[str, Any]:
        if not self._state_path.exists():
            return {"disabled": [], "sources": {}}
        try:
            with open(self._state_path, encoding="utf-8") as f:
                data = json.load(f)
            disabled = data.get("disabled", [])
            if not isinstance(disabled, list):
                disabled = []
            sources = data.get("sources", {})
            if not isinstance(sources, dict):
                sources = {}
            return {"disabled": disabled, "sources": sources}
        except Exception:
            return {"disabled": [], "sources": {}}

    def _save_state(self, state: dict[str, Any]) -> None:
        tmp = self._state_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        tmp.replace(self._state_path)

    def _parse_skill_frontmatter(self, skill_file: Path) -> dict[str, str]:
        """Parse SKILL.md frontmatter metadata."""
        try:
            content = skill_file.read_text(encoding="utf-8")
        except Exception:
            return {}
        if not content.startswith("---"):
            return {}
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}
        try:
            meta = yaml.safe_load(parts[1]) or {}
        except Exception:
            return {}
        if not isinstance(meta, dict):
            return {}
        return {str(k): str(v) for k, v in meta.items() if isinstance(k, str)}

    def _metadata_from_dir(self, plugin_dir: Path) -> dict[str, Any] | None:
        """Build plugin metadata from plugin folder."""
        manifest_file = plugin_dir / "plugin.json"
        skill_file = plugin_dir / "SKILL.md"

        metadata: dict[str, Any] = {
            "id": plugin_dir.name,
            "name": plugin_dir.name,
            "description": "",
            "version": "-",
            "type": "unknown",
            "path": str(plugin_dir),
            "issues": [],
        }

        if manifest_file.exists():
            metadata["type"] = "dynamic"
            try:
                with open(manifest_file, encoding="utf-8") as f:
                    payload = json.load(f)
                plugin_id = payload.get("id") or plugin_dir.name
                metadata["id"] = str(plugin_id)
                metadata["name"] = str(payload.get("name") or plugin_id)
                metadata["description"] = str(payload.get("description") or "")
                metadata["version"] = str(payload.get("version") or "-")
                metadata["entry_point"] = str(payload.get("entry_point") or "main.py")
                deps = payload.get("dependencies", [])
                metadata["dependencies"] = deps if isinstance(deps, list) else []
            except Exception as exc:
                metadata["issues"].append(f"Invalid plugin.json: {exc}")
            return metadata

        if skill_file.exists():
            metadata["type"] = "skill"
            meta = self._parse_skill_frontmatter(skill_file)
            if meta:
                metadata["id"] = meta.get("name", plugin_dir.name)
                metadata["name"] = meta.get("name", plugin_dir.name)
                metadata["description"] = meta.get("description", "")
            else:
                metadata["issues"].append("Invalid SKILL.md frontmatter")
            return metadata

        return None

    def list_plugins(self) -> list[dict[str, Any]]:
        """List plugins in workspace with enabled state and source info."""
        state = self._load_state()
        disabled = set(state.get("disabled", []))
        sources = state.get("sources", {})
        rows: list[dict[str, Any]] = []

        for item in sorted(self.plugins_dir.iterdir(), key=lambda p: p.name.lower()):
            if not item.is_dir() or item.name.startswith("."):
                continue

            meta = self._metadata_from_dir(item)
            if not meta:
                continue
            plugin_id = str(meta["id"])
            meta["enabled"] = plugin_id not in disabled
            source_entry = sources.get(plugin_id, {})
            if isinstance(source_entry, dict):
                meta["source"] = source_entry.get("path")
            else:
                meta["source"] = None
            rows.append(meta)

        return rows

    def install_from_path(
        self,
        source_path: Path,
        target_name: str | None = None,
        overwrite: bool = False,
    ) -> str:
        """Install plugin from local folder path and persist source link."""
        source = Path(source_path).expanduser().resolve()
        if not source.exists() or not source.is_dir():
            raise ValueError(f"Plugin source directory not found: {source}")

        source_meta = self._metadata_from_dir(source)
        if not source_meta:
            raise ValueError("Source must contain plugin.json or SKILL.md")

        plugin_id = str(source_meta["id"])
        destination_name = (target_name or plugin_id).strip() or plugin_id
        destination = self.plugins_dir / destination_name
        if destination.exists():
            if not overwrite:
                raise ValueError(f"Plugin destination already exists: {destination}")
            shutil.rmtree(destination)

        shutil.copytree(source, destination)

        state = self._load_state()
        state_sources = state.setdefault("sources", {})
        state_sources[plugin_id] = {"path": str(source), "type": "local_dir"}
        disabled = set(state.get("disabled", []))
        if plugin_id in disabled:
            disabled.remove(plugin_id)
        state["disabled"] = sorted(disabled)
        self._save_state(state)
        return plugin_id

    def install_from_git(
        self,
        repo_url: str,
        ref: str | None = None,
        target_name: str | None = None,
        overwrite: bool = False,
    ) -> str:
        """Install plugin from git repo, with optional pinned ref."""
        checkout_dir = self._clone_git_repo(repo_url, ref)
        try:
            plugin_id = self.install_from_path(checkout_dir, target_name=target_name, overwrite=overwrite)
            state = self._load_state()
            state.setdefault("sources", {})[plugin_id] = {
                "type": "git",
                "url": repo_url,
                "ref": ref,
            }
            self._save_state(state)
            return plugin_id
        finally:
            shutil.rmtree(checkout_dir, ignore_errors=True)

    def _find_plugin(self, plugin_id: str) -> dict[str, Any] | None:
        for row in self.list_plugins():
            if row["id"] == plugin_id:
                return row
        return None

    def set_enabled(self, plugin_id: str, enabled: bool) -> bool:
        """Enable or disable a plugin."""
        if not self._find_plugin(plugin_id):
            return False
        state = self._load_state()
        disabled = set(state.get("disabled", []))
        if enabled:
            disabled.discard(plugin_id)
        else:
            disabled.add(plugin_id)
        state["disabled"] = sorted(disabled)
        self._save_state(state)
        return True

    def update_plugin(self, plugin_id: str, source_path: Path | None = None) -> bool:
        """Update installed plugin from source path or linked install source."""
        installed = self._find_plugin(plugin_id)
        if not installed:
            return False

        state = self._load_state()
        destination = Path(installed["path"])
        source_entry = state.get("sources", {}).get(plugin_id, {})

        # Prepare rollback backup.
        backup_dir = self.plugins_dir / ".tmp-update-backup"
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / destination.name
        if destination.exists():
            shutil.copytree(destination, backup_path)

        try:
            if source_path is not None:
                self.install_from_path(source_path, target_name=destination.name, overwrite=True)
                return True

            if not isinstance(source_entry, dict):
                return False

            source_type = source_entry.get("type")
            if source_type == "git":
                url = source_entry.get("url")
                if not isinstance(url, str) or not url.strip():
                    return False
                ref = source_entry.get("ref")
                ref_str = str(ref) if isinstance(ref, str) and ref.strip() else None
                self.install_from_git(url, ref=ref_str, target_name=destination.name, overwrite=True)
                return True

            src = source_entry.get("path")
            if isinstance(src, str) and src.strip():
                self.install_from_path(Path(src), target_name=destination.name, overwrite=True)
                return True
            return False
        except Exception:
            if backup_path.exists():
                if destination.exists():
                    shutil.rmtree(destination, ignore_errors=True)
                shutil.copytree(backup_path, destination)
            return False
        finally:
            shutil.rmtree(backup_dir, ignore_errors=True)

    def uninstall_plugin(self, plugin_id: str) -> bool:
        """Remove installed plugin from workspace."""
        installed = self._find_plugin(plugin_id)
        if not installed:
            return False
        destination = Path(installed["path"])
        if destination.exists():
            shutil.rmtree(destination)

        state = self._load_state()
        state["disabled"] = [name for name in state.get("disabled", []) if name != plugin_id]
        if isinstance(state.get("sources"), dict):
            state["sources"].pop(plugin_id, None)
        self._save_state(state)
        return True

    def _doctor_single(self, plugin: dict[str, Any]) -> dict[str, Any]:
        issues = list(plugin.get("issues", []))
        plugin_path = Path(plugin["path"])

        if plugin.get("type") == "dynamic":
            manifest_file = plugin_path / "plugin.json"
            if not manifest_file.exists():
                issues.append("Missing plugin.json")
            else:
                try:
                    with open(manifest_file, encoding="utf-8") as f:
                        payload = json.load(f)
                except Exception as exc:
                    payload = {}
                    issues.append(f"Invalid plugin.json: {exc}")

                entry = payload.get("entry_point", "main.py")
                entry_path = plugin_path / str(entry)
                if not entry_path.exists():
                    issues.append(f"Missing entry point: {entry}")

                deps = payload.get("dependencies", [])
                if isinstance(deps, list):
                    for dep in deps:
                        if not isinstance(dep, str) or not dep.strip():
                            continue
                        if importlib.util.find_spec(dep.strip()) is None:
                            issues.append(f"Missing dependency: {dep.strip()}")

        if plugin.get("type") == "skill":
            skill_file = plugin_path / "SKILL.md"
            if not skill_file.exists():
                issues.append("Missing SKILL.md")

        return {
            "plugin": plugin["id"],
            "ok": len(issues) == 0,
            "issues": issues,
        }

    def doctor(self, plugin_id: str | None = None) -> dict[str, Any] | list[dict[str, Any]]:
        """Run plugin diagnostics for one plugin or all installed plugins."""
        plugins = self.list_plugins()
        if plugin_id:
            target = next((p for p in plugins if p["id"] == plugin_id), None)
            if not target:
                return {"plugin": plugin_id, "ok": False, "issues": ["Plugin not found"]}
            return self._doctor_single(target)
        return [self._doctor_single(p) for p in plugins]
