import questionary

from kabot.cli.setup_wizard import ClackUI


class _TtyStream:
    def isatty(self):
        return True


def test_clack_select_selection_style_highlights_selected(monkeypatch):
    captured = {}

    class _Prompt:
        def ask(self):
            return "simple"

    def _fake_select(message, choices, default=None, style=None):
        captured["style"] = style
        return _Prompt()

    monkeypatch.setattr("kabot.cli.wizard.ui.sys.stdin", _TtyStream())
    monkeypatch.setattr("kabot.cli.wizard.ui.sys.stdout", _TtyStream())
    monkeypatch.setattr("kabot.cli.wizard.ui.console.print", lambda *args, **kwargs: None)
    monkeypatch.setattr("kabot.cli.wizard.ui.questionary.select", _fake_select)

    result = ClackUI.clack_select(
        "Setup mode",
        choices=[questionary.Choice("Simple", value="simple")],
        default="simple",
    )

    assert result == "simple"
    rules = dict(captured["style"].style_rules)
    assert "selected" in rules
    assert "cyan" in rules["selected"].lower()
    assert "blue" not in rules["selected"].lower()
    assert "text" in rules
    assert "white" in rules["text"].lower()
    assert "highlighted" in rules
    assert "cyan" in rules["highlighted"].lower()


def test_clack_select_auto_adds_back_option(monkeypatch):
    captured = {}

    class _Prompt:
        def ask(self):
            return "simple"

    def _fake_select(message, choices, default=None, style=None):
        captured["choices"] = choices
        return _Prompt()

    monkeypatch.setattr("kabot.cli.wizard.ui.sys.stdin", _TtyStream())
    monkeypatch.setattr("kabot.cli.wizard.ui.sys.stdout", _TtyStream())
    monkeypatch.setattr("kabot.cli.wizard.ui.console.print", lambda *args, **kwargs: None)
    monkeypatch.setattr("kabot.cli.wizard.ui.questionary.select", _fake_select)

    result = ClackUI.clack_select(
        "Setup mode",
        choices=[questionary.Choice("Simple", value="simple")],
        default="simple",
    )

    assert result == "simple"
    values = [choice.value for choice in captured["choices"]]
    assert "__back__" in values


def test_clack_select_returns_none_when_back_selected(monkeypatch):
    class _Prompt:
        def ask(self):
            return "__back__"

    def _fake_select(message, choices, default=None, style=None):
        return _Prompt()

    monkeypatch.setattr("kabot.cli.wizard.ui.sys.stdin", _TtyStream())
    monkeypatch.setattr("kabot.cli.wizard.ui.sys.stdout", _TtyStream())
    monkeypatch.setattr("kabot.cli.wizard.ui.console.print", lambda *args, **kwargs: None)
    monkeypatch.setattr("kabot.cli.wizard.ui.questionary.select", _fake_select)

    result = ClackUI.clack_select(
        "Setup mode",
        choices=[questionary.Choice("Simple", value="simple")],
        default="simple",
    )

    assert result is None


def test_clack_select_non_tty_uses_default_without_questionary(monkeypatch):
    class _FakeStream:
        def isatty(self):
            return False

    monkeypatch.setattr("kabot.cli.wizard.ui.sys.stdin", _FakeStream())
    monkeypatch.setattr("kabot.cli.wizard.ui.sys.stdout", _FakeStream())
    monkeypatch.setattr(
        "kabot.cli.wizard.ui.questionary.select",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("questionary.select must not be called")),
    )
    monkeypatch.setattr("kabot.cli.wizard.ui.console.print", lambda *args, **kwargs: None)

    result = ClackUI.clack_select(
        "Setup mode",
        choices=[questionary.Choice("Simple", value="simple")],
        default="simple",
    )

    assert result == "simple"
