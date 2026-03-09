from __future__ import annotations

import tomllib
from pathlib import Path


def test_runtime_dependencies_include_psutil() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    dependencies = pyproject["project"]["dependencies"]

    assert any(dep.startswith("psutil") for dep in dependencies)
