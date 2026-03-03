import os
from pathlib import Path

from kabot.cli.setup_wizard import SetupWizard


class _FakeSkillsLoader:
    def __init__(self, *_args, **_kwargs):
        pass

    def list_skills(self, filter_unavailable=False):
        _ = filter_unavailable
        return [
            {
                "name": "demo-skill",
                "eligible": False,
                "primaryEnv": None,
                "missing": {
                    "bins": ["demo-cli"],
                    "env": [],
                    "os": [],
                },
                "install": [
                    {
                        "id": "legacy-cmd",
                        "kind": "cmd",
                        "label": "Install demo-cli",
                        "cmd": "echo install-demo",
                    }
                ],
            }
        ]


class _FakeCheckboxPrompt:
    def __init__(self, values):
        self._values = values

    def ask(self):
        return self._values


def test_configure_skills_manual_mode_does_not_execute_subprocess(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.agent.skills.SkillsLoader", _FakeSkillsLoader)

    wizard = SetupWizard()
    monkeypatch.setattr(wizard, "_install_builtin_skills_with_progress", lambda: False)

    monkeypatch.setattr(
        "kabot.cli.wizard.skills_prompts.skills_checkbox",
        lambda *args, **kwargs: ["skip", "demo-skill"],
    )
    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("subprocess.run must not be called")),
    )

    wizard._configure_skills()

    output = capsys.readouterr().out
    assert "Install plan for demo-skill" in output
    assert "echo install-demo" in output


class _FakeNodeInstallSkillsLoader:
    def __init__(self, *_args, **_kwargs):
        pass

    def list_skills(self, filter_unavailable=False):
        _ = filter_unavailable
        return [
            {
                "name": "node-skill",
                "eligible": False,
                "primaryEnv": None,
                "missing": {"bins": ["node-skill-cli"], "env": [], "os": []},
                "install": [
                    {
                        "id": "node",
                        "kind": "node",
                        "package": "@demo/node-skill",
                        "label": "Install node skill",
                    }
                ],
            }
        ]


def test_configure_skills_prompts_node_manager_only_for_node_installers(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.agent.skills.SkillsLoader", _FakeNodeInstallSkillsLoader)

    wizard = SetupWizard()
    monkeypatch.setattr(wizard, "_install_builtin_skills_with_progress", lambda: False)

    monkeypatch.setattr(
        "kabot.cli.wizard.skills_prompts.skills_checkbox",
        lambda *args, **kwargs: ["node-skill"],
    )

    selected_messages = []

    def _fake_select(message, choices, default=None):
        selected_messages.append(message)
        if "Preferred node manager" in message:
            return "pnpm"
        return "back"

    monkeypatch.setattr("kabot.cli.wizard.sections.tools_gateway_skills.ClackUI.clack_select", _fake_select)
    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", lambda *args, **kwargs: True)

    wizard._configure_skills()

    install_cfg = wizard.config.skills.get("install", {})
    assert install_cfg.get("node_manager") == "pnpm"
    assert any("Preferred node manager" in message for message in selected_messages)


class _FakeEnvAwareSkillsLoader:
    def __init__(self, *_args, **_kwargs):
        pass

    def list_skills(self, filter_unavailable=False):
        _ = filter_unavailable
        has_key = bool(os.environ.get("GEMINI_API_KEY"))
        return [
            {
                "name": "nano-banana-pro",
                "eligible": has_key,
                "primaryEnv": "GEMINI_API_KEY",
                "missing": {
                    "bins": [],
                    "env": [] if has_key else ["GEMINI_API_KEY"],
                    "os": [],
                },
                "install": {},
            }
        ]


def test_configure_skills_uses_saved_config_env_before_prompt(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.agent.skills.SkillsLoader", _FakeEnvAwareSkillsLoader)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    wizard = SetupWizard()
    wizard.config.skills = {
        "nano-banana-pro": {
            "env": {
                "GEMINI_API_KEY": "from-config",
            }
        }
    }
    monkeypatch.setattr(wizard, "_install_builtin_skills_with_progress", lambda: False)

    def _fake_confirm(message, *args, **kwargs):
        if "Configure skills now?" in message:
            return True
        if "Set GEMINI_API_KEY" in message:
            raise AssertionError("Skill env prompt should not appear when config already has the key")
        return False

    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", _fake_confirm)

    wizard._configure_skills()

    assert os.environ.get("GEMINI_API_KEY") == "from-config"


def test_builtin_skills_source_path_points_to_package_skills():
    wizard = SetupWizard()

    skills_src = wizard._builtin_skills_source_path()

    assert skills_src.name == "skills"
    assert (skills_src / "README.md").exists()


class _FakeEnvOnlySkillsLoader:
    def __init__(self, *_args, **_kwargs):
        pass

    def list_skills(self, filter_unavailable=False):
        _ = filter_unavailable
        return [
            {
                "name": "goplaces",
                "eligible": False,
                "primaryEnv": "GOOGLE_PLACES_API_KEY",
                "missing": {
                    "bins": [],
                    "env": ["GOOGLE_PLACES_API_KEY"],
                    "os": [],
                },
                "install": {},
            },
            {
                "name": "local-places",
                "eligible": False,
                "primaryEnv": "GOOGLE_PLACES_API_KEY",
                "missing": {
                    "bins": [],
                    "env": ["GOOGLE_PLACES_API_KEY"],
                    "os": [],
                },
                "install": {},
            },
            {
                "name": "notion",
                "eligible": False,
                "primaryEnv": "NOTION_API_KEY",
                "missing": {
                    "bins": [],
                    "env": ["NOTION_API_KEY"],
                    "os": [],
                },
                "install": {},
            },
        ]


class _FakeMultiEnvSkillsLoader:
    def __init__(self, *_args, **_kwargs):
        pass

    def list_skills(self, filter_unavailable=False):
        _ = filter_unavailable
        return [
            {
                "name": "trello",
                "eligible": False,
                "primaryEnv": "TRELLO_API_KEY",
                "missing": {
                    "bins": [],
                    "env": ["TRELLO_API_KEY", "TRELLO_TOKEN"],
                    "os": [],
                },
                "install": {},
            }
        ]


def test_configure_skills_skip_env_selection_does_not_prompt_key_inputs(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.agent.skills.SkillsLoader", _FakeEnvOnlySkillsLoader)

    wizard = SetupWizard()
    monkeypatch.setattr(wizard, "_install_builtin_skills_with_progress", lambda: False)

    monkeypatch.setattr(
        "kabot.cli.wizard.skills_prompts.skills_checkbox",
        lambda *args, **kwargs: ["skip"],
    )

    def _fake_confirm(message, *args, **kwargs):
        if "Configure skills now" in message:
            return True
        if "Set " in message:
            raise AssertionError("Env key prompt should not appear when env selection is skipped")
        return False

    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", _fake_confirm)
    monkeypatch.setattr(
        "kabot.cli.setup_wizard.Prompt.ask",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Prompt.ask should not be called")),
    )

    wizard._configure_skills()


def test_configure_skills_env_prompts_only_selected_skills(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.agent.skills.SkillsLoader", _FakeEnvOnlySkillsLoader)

    wizard = SetupWizard()
    monkeypatch.setattr(wizard, "_install_builtin_skills_with_progress", lambda: False)

    monkeypatch.setattr(
        "kabot.cli.wizard.skills_prompts.skills_checkbox",
        lambda *args, **kwargs: ["notion"],
    )

    def _fake_confirm(message, *args, **kwargs):
        if "Configure skills now" in message:
            return True
        if "Set GOOGLE_PLACES_API_KEY" in message:
            raise AssertionError("GOOGLE_PLACES_API_KEY should not be prompted when not selected")
        if "Set NOTION_API_KEY" in message:
            return True
        return False

    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", _fake_confirm)
    monkeypatch.setattr("kabot.cli.setup_wizard.Prompt.ask", lambda *args, **kwargs: "notion-key")

    wizard._configure_skills()

    assert wizard.config.skills["entries"]["notion"]["env"]["NOTION_API_KEY"] == "notion-key"
    assert "goplaces" not in wizard.config.skills["entries"]
    assert "local-places" not in wizard.config.skills["entries"]


def test_configure_skills_prompts_all_missing_env_keys_for_selected_skill(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.agent.skills.SkillsLoader", _FakeMultiEnvSkillsLoader)

    wizard = SetupWizard()
    monkeypatch.setattr(wizard, "_install_builtin_skills_with_progress", lambda: False)

    monkeypatch.setattr(
        "kabot.cli.wizard.skills_prompts.skills_checkbox",
        lambda *args, **kwargs: ["trello"],
    )

    confirm_messages = []

    def _fake_confirm(message, *args, **kwargs):
        confirm_messages.append(message)
        if "Configure skills now" in message:
            return True
        if "Set TRELLO_API_KEY" in message:
            return True
        if "Set TRELLO_TOKEN" in message:
            return True
        return False

    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", _fake_confirm)

    prompt_values = iter(["trello-key", "trello-token"])
    monkeypatch.setattr("kabot.cli.setup_wizard.Prompt.ask", lambda *args, **kwargs: next(prompt_values))

    wizard._configure_skills()

    assert wizard.config.skills["entries"]["trello"]["env"]["TRELLO_API_KEY"] == "trello-key"
    assert wizard.config.skills["entries"]["trello"]["env"]["TRELLO_TOKEN"] == "trello-token"
    assert any("Set TRELLO_API_KEY" in msg for msg in confirm_messages)
    assert any("Set TRELLO_TOKEN" in msg for msg in confirm_messages)


def test_configure_skills_same_env_key_prompted_once_for_multiple_selected_skills(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.agent.skills.SkillsLoader", _FakeEnvOnlySkillsLoader)

    wizard = SetupWizard()
    monkeypatch.setattr(wizard, "_install_builtin_skills_with_progress", lambda: False)

    monkeypatch.setattr(
        "kabot.cli.wizard.skills_prompts.skills_checkbox",
        lambda *args, **kwargs: ["goplaces", "local-places"],
    )

    def _fake_confirm(message, *args, **kwargs):
        if "Configure skills now" in message:
            return True
        if "Set GOOGLE_PLACES_API_KEY" in message:
            return True
        if "Set NOTION_API_KEY" in message:
            raise AssertionError("NOTION_API_KEY should not be prompted when not selected")
        return False

    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", _fake_confirm)

    prompt_calls = []

    def _fake_prompt(message, *args, **kwargs):
        prompt_calls.append(message)
        return "shared-gplaces-key"

    monkeypatch.setattr("kabot.cli.setup_wizard.Prompt.ask", _fake_prompt)

    wizard._configure_skills()

    assert len(prompt_calls) == 1
    assert wizard.config.skills["entries"]["goplaces"]["env"]["GOOGLE_PLACES_API_KEY"] == "shared-gplaces-key"
    assert wizard.config.skills["entries"]["local-places"]["env"]["GOOGLE_PLACES_API_KEY"] == "shared-gplaces-key"


def test_configure_skills_one_shot_git_install_onboarding(monkeypatch, tmp_path):
    from kabot.cli.skill_repo_installer import InstalledSkill

    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.agent.skills.SkillsLoader", _FakeSkillsLoader)
    monkeypatch.setattr("kabot.cli.wizard.sections.tools_gateway_skills._is_interactive_tty", lambda: True)
    monkeypatch.setattr(
        "kabot.cli.wizard.sections.tools_gateway_skills._collect_skill_env_requirements",
        lambda _config, _skill_key: ["FAL_KEY"],
    )
    monkeypatch.setattr("kabot.cli.skill_repo_installer.list_skill_candidate_details_from_git", lambda repo_url, ref: [])

    installed_dir = tmp_path / "repo-install" / "clawra-selfie"
    installed_dir.mkdir(parents=True, exist_ok=True)
    (installed_dir / "SKILL.md").write_text("# Clawra\n", encoding="utf-8")
    (installed_dir / "soul-injection.md").write_text(
        "## Clawra Selfie Capability\n\nUse clawra-selfie when user asks for selfies.",
        encoding="utf-8",
    )

    def _fake_install_skill_from_git(*, repo_url, target_dir, ref, subdir, skill_name, overwrite):
        _ = target_dir, ref, subdir, skill_name, overwrite
        return InstalledSkill(
            repo_url=repo_url,
            selected_dir=Path("skill"),
            installed_dir=installed_dir,
            skill_name="clawra-selfie",
            skill_key="clawra-selfie",
        )

    monkeypatch.setattr("kabot.cli.skill_repo_installer.install_skill_from_git", _fake_install_skill_from_git)

    wizard = SetupWizard()
    monkeypatch.setattr(wizard, "_install_builtin_skills_with_progress", lambda: False)

    monkeypatch.setattr(
        "kabot.cli.wizard.skills_prompts.skills_checkbox",
        lambda *args, **kwargs: ["skip"],
    )

    def _fake_confirm(message, *args, **kwargs):
        if "Configure skills now" in message:
            return True
        if "Install external skill from git now" in message:
            return True
        if "Install another external skill from git" in message:
            return False
        if "Set FAL_KEY for clawra-selfie" in message:
            return True
        if "Inject persona snippet into SOUL.md" in message:
            return True
        return False

    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", _fake_confirm)

    prompt_values = iter(
        [
            "https://example.com/clawra.git",  # repo
            "",  # ref
            "",  # subdir
            "",  # name override
            "workspace",  # target
            "fal_live_key",  # FAL_KEY
        ]
    )
    monkeypatch.setattr("kabot.cli.setup_wizard.Prompt.ask", lambda *args, **kwargs: next(prompt_values))

    wizard._configure_skills()

    entries = wizard.config.skills["entries"]["clawra-selfie"]
    assert entries["enabled"] is True
    assert entries["env"]["FAL_KEY"] == "fal_live_key"

    soul_path = wizard.config.workspace_path / "SOUL.md"
    assert soul_path.exists()
    soul_text = soul_path.read_text(encoding="utf-8")
    assert "Clawra Selfie Capability" in soul_text


def test_configure_skills_one_shot_git_install_injects_agents_with_preview(monkeypatch, tmp_path):
    from kabot.cli.skill_repo_installer import InstalledSkill

    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.agent.skills.SkillsLoader", _FakeSkillsLoader)
    monkeypatch.setattr("kabot.cli.wizard.sections.tools_gateway_skills._is_interactive_tty", lambda: True)
    monkeypatch.setattr(
        "kabot.cli.wizard.sections.tools_gateway_skills._collect_skill_env_requirements",
        lambda _config, _skill_key: [],
    )
    monkeypatch.setattr("kabot.cli.skill_repo_installer.list_skill_candidate_details_from_git", lambda repo_url, ref: [])

    installed_dir = tmp_path / "repo-install" / "ops-skill"
    installed_dir.mkdir(parents=True, exist_ok=True)
    (installed_dir / "SKILL.md").write_text("# Ops Skill\n", encoding="utf-8")
    (installed_dir / "agents-injection.md").write_text(
        "## Ops Capability\n\nWhen user asks for ops workflows, prioritize ops-skill.",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "kabot.cli.skill_repo_installer.install_skill_from_git",
        lambda **kwargs: InstalledSkill(
            repo_url=str(kwargs.get("repo_url") or ""),
            selected_dir=Path("skill"),
            installed_dir=installed_dir,
            skill_name="ops-skill",
            skill_key="ops-skill",
        ),
    )

    wizard = SetupWizard()
    monkeypatch.setattr(wizard, "_install_builtin_skills_with_progress", lambda: False)
    monkeypatch.setattr(
        "kabot.cli.wizard.skills_prompts.skills_checkbox",
        lambda *args, **kwargs: ["skip"],
    )

    def _fake_confirm(message, *args, **kwargs):
        if "Configure skills now" in message:
            return True
        if "Install external skill from git now" in message:
            return True
        if "Install another external skill from git" in message:
            return False
        if "Preview persona snippets before apply" in message:
            return True
        if "Inject persona snippet into SOUL.md" in message:
            return False
        if "Inject persona snippet into AGENTS.md" in message:
            return True
        return False

    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", _fake_confirm)
    prompt_values = iter(
        [
            "https://example.com/ops-skill.git",  # repo
            "",  # ref
            "",  # subdir
            "",  # name
            "workspace",  # target
        ]
    )
    monkeypatch.setattr("kabot.cli.setup_wizard.Prompt.ask", lambda *args, **kwargs: next(prompt_values))

    wizard._configure_skills()

    agents_path = wizard.config.workspace_path / "AGENTS.md"
    assert agents_path.exists()
    agents_text = agents_path.read_text(encoding="utf-8")
    assert "Ops Capability" in agents_text


def test_configure_skills_one_shot_git_install_handles_multi_skill_candidates(monkeypatch, tmp_path):
    from kabot.cli.skill_repo_installer import InstalledSkill

    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.agent.skills.SkillsLoader", _FakeSkillsLoader)
    monkeypatch.setattr("kabot.cli.wizard.sections.tools_gateway_skills._is_interactive_tty", lambda: True)
    monkeypatch.setattr(
        "kabot.cli.wizard.sections.tools_gateway_skills._collect_skill_env_requirements",
        lambda _config, _skill_key: [],
    )
    monkeypatch.setattr("kabot.cli.skill_repo_installer.list_skill_candidate_details_from_git", lambda repo_url, ref: [])

    installed_dir = tmp_path / "repo-install" / "skill-b"
    installed_dir.mkdir(parents=True, exist_ok=True)
    (installed_dir / "SKILL.md").write_text("# Skill B\n", encoding="utf-8")

    calls: list[dict] = []

    def _fake_install_skill_from_git(**kwargs):
        calls.append(dict(kwargs))
        if len(calls) == 1:
            raise ValueError(
                "Multiple skill folders found in repo. Use --subdir to choose one. "
                "Candidates: skill-a, skill-b"
            )
        return InstalledSkill(
            repo_url=str(kwargs.get("repo_url") or ""),
            selected_dir=Path(str(kwargs.get("subdir") or "skill-b")),
            installed_dir=installed_dir,
            skill_name="skill-b",
            skill_key="skill-b",
        )

    monkeypatch.setattr("kabot.cli.skill_repo_installer.install_skill_from_git", _fake_install_skill_from_git)

    def _fake_select(message, choices, default=None):
        _ = choices, default
        if "Multiple skills found in repo" in message:
            return "skill-b"
        return "back"

    monkeypatch.setattr("kabot.cli.wizard.sections.tools_gateway_skills.ClackUI.clack_select", _fake_select)

    wizard = SetupWizard()
    monkeypatch.setattr(wizard, "_install_builtin_skills_with_progress", lambda: False)
    monkeypatch.setattr(
        "kabot.cli.wizard.skills_prompts.skills_checkbox",
        lambda *args, **kwargs: ["skip"],
    )

    def _fake_confirm(message, *args, **kwargs):
        if "Configure skills now" in message:
            return True
        if "Install external skill from git now" in message:
            return True
        if "Install another external skill from git" in message:
            return False
        if "Inject persona snippet into SOUL.md" in message:
            return False
        return False

    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", _fake_confirm)
    prompt_values = iter(
        [
            "https://example.com/multi.git",  # repo
            "",  # ref
            "",  # subdir
            "",  # name
            "workspace",  # target
        ]
    )
    monkeypatch.setattr("kabot.cli.setup_wizard.Prompt.ask", lambda *args, **kwargs: next(prompt_values))

    wizard._configure_skills()

    assert len(calls) == 2
    assert calls[0].get("subdir") in {None, ""}
    assert calls[1].get("subdir") == "skill-b"


def test_configure_skills_one_shot_git_install_uses_preclone_discovery(monkeypatch, tmp_path):
    from kabot.cli.skill_repo_installer import InstalledSkill

    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.agent.skills.SkillsLoader", _FakeSkillsLoader)
    monkeypatch.setattr("kabot.cli.wizard.sections.tools_gateway_skills._is_interactive_tty", lambda: True)
    monkeypatch.setattr(
        "kabot.cli.wizard.sections.tools_gateway_skills._collect_skill_env_requirements",
        lambda _config, _skill_key: [],
    )

    installed_dir = tmp_path / "repo-install" / "skill-b"
    installed_dir.mkdir(parents=True, exist_ok=True)
    (installed_dir / "SKILL.md").write_text("# Skill B\n", encoding="utf-8")

    monkeypatch.setattr(
        "kabot.cli.skill_repo_installer.list_skill_candidate_details_from_git",
        lambda repo_url, ref: [
            {"subdir": "skill-a", "name": "Skill A", "description": "First", "score": 10},
            {"subdir": "skill-b", "name": "Skill B", "description": "Second", "score": 99},
        ],
    )

    calls: list[dict] = []

    def _fake_install_skill_from_git(**kwargs):
        calls.append(dict(kwargs))
        return InstalledSkill(
            repo_url=str(kwargs.get("repo_url") or ""),
            selected_dir=Path(str(kwargs.get("subdir") or "skill-b")),
            installed_dir=installed_dir,
            skill_name="skill-b",
            skill_key="skill-b",
        )

    monkeypatch.setattr("kabot.cli.skill_repo_installer.install_skill_from_git", _fake_install_skill_from_git)

    def _fake_select(message, choices, default=None):
        _ = choices, default
        if "Multiple skills found in repo" in message:
            return "skill-b"
        return "back"

    monkeypatch.setattr("kabot.cli.wizard.sections.tools_gateway_skills.ClackUI.clack_select", _fake_select)

    wizard = SetupWizard()
    monkeypatch.setattr(wizard, "_install_builtin_skills_with_progress", lambda: False)
    monkeypatch.setattr(
        "kabot.cli.wizard.skills_prompts.skills_checkbox",
        lambda *args, **kwargs: ["skip"],
    )

    def _fake_confirm(message, *args, **kwargs):
        if "Configure skills now" in message:
            return True
        if "Install external skill from git now" in message:
            return True
        if "Install another external skill from git" in message:
            return False
        if "Inject persona snippet into SOUL.md" in message:
            return False
        return False

    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", _fake_confirm)
    prompt_values = iter(
        [
            "https://example.com/multi.git",  # repo
            "",  # ref
            "",  # subdir
            "",  # name
            "workspace",  # target
        ]
    )
    monkeypatch.setattr("kabot.cli.setup_wizard.Prompt.ask", lambda *args, **kwargs: next(prompt_values))

    wizard._configure_skills()

    assert len(calls) == 1
    assert calls[0].get("subdir") == "skill-b"


def test_prompt_skill_candidate_subdir_uses_metadata_default(monkeypatch):
    from kabot.cli.wizard.sections import tools_gateway_skills as section_mod

    captured = {"default": None, "choices": None}

    def _fake_select(message, choices, default=None):
        _ = message
        captured["default"] = default
        captured["choices"] = choices
        return "skills/alpha"

    monkeypatch.setattr(
        "kabot.cli.wizard.sections.tools_gateway_skills.ClackUI.clack_select",
        _fake_select,
    )

    selected = section_mod._prompt_skill_candidate_subdir(
        [
            {"subdir": "skills/alpha", "name": "Alpha", "description": "Primary", "score": 100},
            {"subdir": "nested/beta", "name": "Beta", "description": "Secondary", "score": 10},
        ],
        None,
    )

    assert selected == "skills/alpha"
    assert captured["default"] == "skills/alpha"
    first_choice = captured["choices"][0]
    title = getattr(first_choice, "title", str(first_choice))
    assert "Alpha" in str(title)


def test_build_agents_persona_template_includes_skill_identity():
    from kabot.cli.wizard.sections import tools_gateway_skills as section_mod

    snippet = section_mod._build_agents_persona_template(
        skill_name="clawra-selfie",
        skill_key="clawra-selfie",
        mode="strict",
        capability_summary="Selfie generation and media replies",
    )

    assert "Strict Routing Guardrails" in snippet
    assert "`clawra-selfie`" in snippet
    assert "Selfie generation and media replies" in snippet


def test_choose_agents_persona_snippet_supports_template_assistant(monkeypatch, tmp_path):
    from kabot.cli.wizard.sections import tools_gateway_skills as section_mod

    installed_dir = tmp_path / "skill"
    installed_dir.mkdir(parents=True, exist_ok=True)
    (installed_dir / "SKILL.md").write_text(
        "---\nname: ops-skill\ndescription: Automate ops workflows quickly\n---\n",
        encoding="utf-8",
    )

    def _fake_confirm(message, *args, **kwargs):
        _ = args, kwargs
        return "Use AGENTS template assistant" in message

    monkeypatch.setattr("kabot.cli.wizard.sections.tools_gateway_skills.Confirm.ask", _fake_confirm)
    monkeypatch.setattr(
        "kabot.cli.wizard.sections.tools_gateway_skills.ClackUI.clack_select",
        lambda *args, **kwargs: "strict",
    )

    snippet = section_mod._choose_agents_persona_snippet(
        installed_dir=installed_dir,
        skill_name="ops-skill",
        skill_key="ops-skill",
        default_snippet="fallback",
    )

    assert "Strict Routing Guardrails" in snippet
    assert "Automate ops workflows quickly" in snippet
    assert "`ops-skill`" in snippet
