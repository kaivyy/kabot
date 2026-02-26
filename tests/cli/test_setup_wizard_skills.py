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
