from pathlib import Path
import os

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
                "install": {"cmd": "echo install-demo"},
            }
        ]


class _FakeCheckboxPrompt:
    def __init__(self, values):
        self._values = values

    def ask(self):
        return self._values


def test_configure_skills_skip_plus_skill_still_installs_selected(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    monkeypatch.setattr("kabot.agent.skills.SkillsLoader", _FakeSkillsLoader)

    wizard = SetupWizard()
    monkeypatch.setattr(wizard, "_install_builtin_skills_with_progress", lambda: False)

    monkeypatch.setattr(
        "kabot.cli.setup_wizard.questionary.checkbox",
        lambda *args, **kwargs: _FakeCheckboxPrompt(["skip", "demo-skill"]),
    )
    monkeypatch.setattr("kabot.cli.setup_wizard.Confirm.ask", lambda *args, **kwargs: True)

    install_cmds = []

    class _Result:
        returncode = 0
        stderr = ""
        stdout = ""

    def _fake_run(cmd, **_kwargs):
        install_cmds.append(cmd)
        return _Result()

    monkeypatch.setattr("subprocess.run", _fake_run)

    wizard._configure_skills()

    assert install_cmds == ["echo install-demo"]


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
