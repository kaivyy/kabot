# Phase 6: Plugin System Implementation Plan

> **Goal:** Enable dynamic loading of skills/tools from a `plugins/` directory, matching OpenClaw's flexibility.

## Task 18: Plugin Loader & Registry

**Files:**
- Create: `kabot/plugins/loader.py`
- Create: `kabot/plugins/registry.py`
- Modify: `kabot/config/schema.py`
- Test: `tests/plugins/test_loader.py`

**Step 1: Write the failing test**

```python
# tests/plugins/test_loader.py
import pytest
from pathlib import Path
from kabot.plugins.loader import load_plugins
from kabot.plugins.registry import PluginRegistry

@pytest.fixture
def plugin_dir(tmp_path):
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
    registry = PluginRegistry()
    loaded = load_plugins(plugin_dir, registry)
    
    assert len(loaded) == 1
    plugin = registry.get("hello-world")
    assert plugin is not None
    assert plugin.description == "A friendly plugin"
```

**Step 2: Implement Loader & Registry**

```python
# kabot/plugins/registry.py
from dataclasses import dataclass

@dataclass
class Plugin:
    name: str
    description: str
    path: str
    enabled: bool = True

class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin):
        self._plugins[plugin.name] = plugin
        
    def get(self, name: str) -> Plugin | None:
        return self._plugins.get(name)
        
    def list_all(self) -> list[Plugin]:
        return list(self._plugins.values())
```

```python
# kabot/plugins/loader.py
import yaml
from pathlib import Path
from loguru import logger
from .registry import PluginRegistry, Plugin

def load_plugins(plugin_dir: Path, registry: PluginRegistry) -> list[Plugin]:
    """Scan directory for SKILL.md files and register them."""
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
                        _, frontmatter, _ = content.split("---", 2)
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
```

**Step 3: Run tests, commit**

```bash
pytest tests/plugins/test_loader.py -v
git commit -m "feat(plugins): add plugin loader and registry"
```

---

## Task 19: Skill Discovery Command

**Files:**
- Modify: `kabot/cli/commands.py`

**Goal:** CLI command `kabot plugins list` to show available plugins.

**Step 1: Implement `plugins list` command**

```python
@app.command(name="plugins")
def plugins_cmd(action: str = "list"):
    """Manage plugins."""
    from kabot.plugins.registry import PluginRegistry
    from kabot.plugins.loader import load_plugins
    from kabot.config.loader import load_config
    
    config = load_config()
    registry = PluginRegistry()
    load_plugins(config.workspace_path / "plugins", registry)
    
    if action == "list":
        table = Table(title="Installed Plugins")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        table.add_column("Status")
        
        for p in registry.list_all():
            status = "[green]Enabled[/green]" if p.enabled else "[red]Disabled[/red]"
            table.add_row(p.name, p.description, status)
            
        console.print(table)
```

**Step 2: Commit**

```bash
git commit -m "feat(cli): add plugins list command"
```
