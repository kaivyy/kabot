from __future__ import annotations

import tomllib
from pathlib import Path


def test_runtime_dependencies_include_psutil() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    dependencies = pyproject["project"]["dependencies"]

    assert any(dep.startswith("psutil") for dep in dependencies)


def test_runtime_dependencies_include_mcp() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    dependencies = pyproject["project"]["dependencies"]

    assert any(dep.startswith("mcp") for dep in dependencies)


def test_runtime_dependencies_include_beautifulsoup4() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    dependencies = pyproject["project"]["dependencies"]

    assert any(dep.startswith("beautifulsoup4") for dep in dependencies)


def test_install_script_bootstraps_browser_runtime() -> None:
    install_script = (Path(__file__).resolve().parents[1] / "install.sh").read_text(encoding="utf-8")

    assert 'ensure_python_package "bs4" "beautifulsoup4"' in install_script
    assert 'ensure_python_package "playwright" "playwright"' in install_script
    assert '"$VENV_DIR/bin/python" -m playwright install chromium' in install_script
