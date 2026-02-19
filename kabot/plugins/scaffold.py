"""Plugin scaffolding utilities."""

from __future__ import annotations

import re
from pathlib import Path


def _sanitize_plugin_name(name: str) -> str:
    raw = (name or "").strip().lower()
    cleaned = re.sub(r"[^a-z0-9_-]+", "_", raw)
    cleaned = cleaned.strip("_-")
    return cleaned or "plugin"


def _render_template(template_path: Path, replacements: dict[str, str]) -> str:
    content = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def scaffold_plugin(base_dir: Path, name: str, kind: str = "dynamic", overwrite: bool = False) -> Path:
    """Create a plugin scaffold under base_dir and return plugin path."""
    kind_normalized = (kind or "").strip().lower()
    if kind_normalized != "dynamic":
        raise ValueError("Only kind='dynamic' is currently supported")

    plugin_id = _sanitize_plugin_name(name)
    root = Path(base_dir).expanduser()
    out = root / plugin_id
    if out.exists():
        if not overwrite:
            raise ValueError(f"Plugin directory already exists: {out}")
        for child in out.iterdir():
            if child.is_dir():
                import shutil

                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        out.mkdir(parents=True, exist_ok=True)

    templates_dir = Path(__file__).parent / "templates" / kind_normalized
    if not templates_dir.exists():
        raise ValueError(f"Templates not found for kind '{kind_normalized}'")

    replacements = {
        "plugin_id": plugin_id,
        "plugin_name": plugin_id.replace("_", " ").title(),
        "description": f"{plugin_id} dynamic plugin",
    }

    mapping = {
        "plugin.json.tpl": "plugin.json",
        "main.py.tpl": "main.py",
    }
    for template_name, output_name in mapping.items():
        src = templates_dir / template_name
        rendered = _render_template(src, replacements)
        (out / output_name).write_text(rendered, encoding="utf-8")

    return out
