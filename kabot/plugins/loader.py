"""
Enhanced Plugin Loader for Kabot (Phase 10).

Supports two plugin formats:
1. SKILL.md (existing) — Static skill definitions with frontmatter
2. plugin.json (new) — Dynamic plugins with code execution and hooks
"""

import importlib
import importlib.util
import json
import sys
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from kabot.plugins.registry import PluginRegistry, Plugin
from kabot.plugins.hooks import HookManager


@dataclass
class PluginManifest:
    """Parsed plugin manifest from plugin.json."""
    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    entry_point: str = "main.py"
    permissions: list[str] = field(default_factory=list)    # e.g., ["network", "filesystem", "tools"]
    hooks: list[str] = field(default_factory=list)          # e.g., ["on_message_received", "pre_llm_call"]
    tools: list[str] = field(default_factory=list)          # Tool names this plugin provides
    dependencies: list[str] = field(default_factory=list)   # Python packages required

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PluginManifest":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            entry_point=data.get("entry_point", "main.py"),
            permissions=data.get("permissions", []),
            hooks=data.get("hooks", []),
            tools=data.get("tools", []),
            dependencies=data.get("dependencies", []),
        )

    def validate(self) -> list[str]:
        """Validate manifest and return list of issues."""
        issues = []
        if not self.id:
            issues.append("Missing 'id' field")
        if not self.name:
            issues.append("Missing 'name' field")
        return issues


def load_plugins(plugin_dir: Path, registry: PluginRegistry) -> list[Plugin]:
    """
    Scan directory for SKILL.md files and register them.
    (Original loader, maintained for backward compatibility.)
    """
    loaded = []
    if not plugin_dir.exists():
        return []

    for item in plugin_dir.iterdir():
        if item.is_dir():
            skill_file = item / "SKILL.md"
            if skill_file.exists():
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            frontmatter = parts[1]
                            meta = yaml.safe_load(frontmatter)

                            plugin = Plugin(
                                name=meta.get("name", item.name),
                                description=meta.get("description", ""),
                                path=str(skill_file),
                                enabled=True
                            )
                            registry.register(plugin)
                            loaded.append(plugin)
                            logger.info(f"Loaded plugin: {plugin.name}")
                except Exception as e:
                    logger.error(f"Failed to load plugin {item.name}: {e}")

    return loaded


def load_dynamic_plugins(
    plugin_dir: Path,
    registry: PluginRegistry,
    hook_manager: HookManager | None = None,
) -> list[Plugin]:
    """
    Scan directory for plugin.json manifests and load dynamic plugins.
    
    Dynamic plugins can:
    - Register hooks via HookManager
    - Provide tools via a `register()` function
    - Run initialization code
    
    Args:
        plugin_dir: Directory containing plugin folders
        registry: Plugin registry to register into
        hook_manager: HookManager for hook registration
    
    Returns:
        List of successfully loaded plugins
    """
    loaded = []
    if not plugin_dir.exists():
        return []

    for item in plugin_dir.iterdir():
        if not item.is_dir():
            continue

        manifest_file = item / "plugin.json"
        if not manifest_file.exists():
            continue

        try:
            # Parse manifest
            with open(manifest_file, encoding="utf-8") as f:
                manifest_data = json.load(f)
            
            manifest = PluginManifest.from_dict(manifest_data)
            
            # Validate manifest
            issues = manifest.validate()
            if issues:
                logger.warning(f"Plugin {item.name} manifest issues: {', '.join(issues)}")
                continue

            # Check entry point exists
            entry_file = item / manifest.entry_point
            if not entry_file.exists():
                logger.warning(f"Plugin {manifest.id}: entry point '{manifest.entry_point}' not found")
                continue

            # Load the plugin module
            module = _load_module(manifest.id, entry_file)
            if module is None:
                continue

            # Call register() if it exists
            if hasattr(module, "register"):
                try:
                    module.register(registry=registry, hooks=hook_manager)
                    logger.info(f"Plugin {manifest.name} registered hooks/tools")
                except Exception as e:
                    logger.error(f"Plugin {manifest.id} register() failed: {e}")

            # Create plugin record
            plugin = Plugin(
                name=manifest.name,
                description=manifest.description,
                path=str(item),
                enabled=True,
            )
            registry.register(plugin)
            loaded.append(plugin)
            logger.info(f"Loaded dynamic plugin: {manifest.name} v{manifest.version}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid plugin.json in {item.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to load dynamic plugin {item.name}: {e}")

    return loaded


def _load_module(module_name: str, file_path: Path) -> Any:
    """Dynamically load a Python module from a file path."""
    try:
        spec = importlib.util.spec_from_file_location(
            f"kabot.plugins.{module_name}",
            str(file_path),
        )
        if spec is None or spec.loader is None:
            logger.error(f"Could not create module spec for {file_path}")
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    except Exception as e:
        logger.error(f"Failed to load module {module_name}: {e}")
        return None
