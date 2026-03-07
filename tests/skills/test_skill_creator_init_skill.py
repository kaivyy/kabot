from __future__ import annotations

import importlib.util
from pathlib import Path

import kabot.config.loader as config_loader
from kabot.config.schema import Config

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "kabot" / "skills" / "skill-creator" / "scripts" / "init_skill.py"


def _load_init_skill_module():
    spec = importlib.util.spec_from_file_location("skill_creator_init_skill", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_find_skills_dir_prefers_configured_workspace_over_repo_builtin(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace_skills = workspace / "skills"
    workspace_skills.mkdir(parents=True)

    cfg = Config()
    cfg.agents.defaults.workspace = str(workspace)
    monkeypatch.setattr(config_loader, "load_config", lambda: cfg)

    module = _load_init_skill_module()

    assert module.find_skills_dir() == workspace_skills


def test_find_skills_dir_uses_cwd_skills_before_repo_fallback(monkeypatch, tmp_path):
    cwd_skills = tmp_path / "skills"
    cwd_skills.mkdir(parents=True)

    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "missing-workspace")
    monkeypatch.setattr(config_loader, "load_config", lambda: cfg)
    monkeypatch.chdir(tmp_path)

    module = _load_init_skill_module()

    assert module.find_skills_dir() == cwd_skills


def test_find_skills_dir_falls_back_to_repo_builtin_when_workspace_not_available(monkeypatch, tmp_path):
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "missing-workspace")
    monkeypatch.setattr(config_loader, "load_config", lambda: cfg)
    monkeypatch.chdir(tmp_path)

    module = _load_init_skill_module()

    expected = REPO_ROOT / "kabot" / "skills"
    assert module.find_skills_dir() == expected
