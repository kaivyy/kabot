"""Plugin loader for scanning and loading plugins from directories."""

import yaml
from pathlib import Path
from loguru import logger
from .registry import PluginRegistry, Plugin


def load_plugins(plugin_dir: Path, registry: PluginRegistry) -> list[Plugin]:
    """
    Scan directory for SKILL.md files and register them.

    Args:
        plugin_dir: Directory containing plugin subdirectories
        registry: Plugin registry to register plugins into

    Returns:
        List of successfully loaded plugins
    """
    loaded = []
    if not plugin_dir.exists():
        return []

    for item in plugin_dir.iterdir():
        if item.is_dir():
            skill_file = item / "SKILL.md"
            if skill_file.exists():
                try:
                    # Parse frontmatter
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
