from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "kabot" / "skills" / "skill-creator" / "scripts"
VALIDATE_PATH = SCRIPT_DIR / "quick_validate.py"
PACKAGE_PATH = SCRIPT_DIR / "package_skill.py"


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def test_quick_validate_accepts_assets_dir_skill(tmp_path):
    module = _load_module(VALIDATE_PATH, "skill_creator_quick_validate")
    skill_dir = tmp_path / "weather-watch"
    (skill_dir / "assets").mkdir(parents=True)
    (skill_dir / "references").mkdir()
    (skill_dir / "scripts").mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: weather-watch\n"
        'description: "Track weather conditions and forecasts."\n'
        "---\n\n"
        "# Weather Watch\n",
        encoding="utf-8",
    )
    (skill_dir / "assets" / "README.md").write_text("asset notes\n", encoding="utf-8")

    valid, message = module.validate_skill(skill_dir)

    assert valid is True
    assert "valid" in message.lower()


def test_package_skill_includes_assets_and_scripts(tmp_path):
    validate_module = _load_module(VALIDATE_PATH, "quick_validate")
    package_module = _load_module(PACKAGE_PATH, "skill_creator_package_skill")
    skill_dir = tmp_path / "meta-threads-official"
    (skill_dir / "assets").mkdir(parents=True)
    (skill_dir / "references").mkdir()
    (skill_dir / "scripts").mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: meta-threads-official\n"
        'description: "Connect to the official Meta Threads API."\n'
        "---\n\n"
        "# Meta Threads Official\n",
        encoding="utf-8",
    )
    (skill_dir / "assets" / "post-template.json").write_text("{}", encoding="utf-8")
    (skill_dir / "scripts" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (skill_dir / "references" / "api.md").write_text("# API\n", encoding="utf-8")
    out_dir = tmp_path / "dist"
    out_dir.mkdir()

    # ensure the packaged script imports the validator module that we loaded above
    sys.modules["quick_validate"] = validate_module
    try:
        archive = package_module.package_skill(skill_dir, out_dir)
    finally:
        sys.modules.pop("quick_validate", None)

    assert archive is not None
    assert archive.exists()
    assert archive.suffix == ".skill"
    with zipfile.ZipFile(archive, "r") as bundle:
        names = set(bundle.namelist())
    assert "meta-threads-official/SKILL.md" in names
    assert "meta-threads-official/assets/post-template.json" in names
    assert "meta-threads-official/references/api.md" in names
    assert "meta-threads-official/scripts/main.py" in names
