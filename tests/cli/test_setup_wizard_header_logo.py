from kabot.cli.wizard.ui import ClackUI


def test_header_renders_injected_block_logo(monkeypatch):
    rendered = []

    def _capture(*args, **kwargs):
        if args:
            rendered.append(str(args[0]))

    monkeypatch.setattr("kabot.cli.wizard.ui.console.print", _capture)

    ClackUI.header()

    assert any("\u2588\u2588" in line for line in rendered)
    assert all("##+" not in line for line in rendered)
