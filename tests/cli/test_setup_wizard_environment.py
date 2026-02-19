from kabot.cli import setup_wizard
from kabot.cli.setup_wizard import SetupWizard
from kabot.utils.environment import RuntimeEnvironment


def _runtime(**overrides) -> RuntimeEnvironment:
    data = {
        "platform": "linux",
        "is_windows": False,
        "is_macos": False,
        "is_linux": True,
        "is_wsl": False,
        "is_termux": False,
        "is_vps": False,
        "is_headless": False,
        "is_ci": False,
        "has_display": True,
    }
    data.update(overrides)
    return RuntimeEnvironment(**data)


def test_suggest_gateway_mode_prefers_remote_for_headless(monkeypatch):
    wizard = SetupWizard()
    monkeypatch.setattr(
        setup_wizard,
        "detect_runtime_environment",
        lambda: _runtime(is_vps=True, is_headless=True, has_display=False),
    )
    assert wizard._suggest_gateway_mode() == "remote"


def test_suggest_gateway_mode_prefers_local_for_desktop(monkeypatch):
    wizard = SetupWizard()
    monkeypatch.setattr(
        setup_wizard,
        "detect_runtime_environment",
        lambda: _runtime(platform="darwin", is_macos=True),
    )
    assert wizard._suggest_gateway_mode() == "local"
