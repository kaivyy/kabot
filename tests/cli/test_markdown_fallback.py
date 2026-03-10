from rich.text import Text


def test_print_agent_response_falls_back_to_plain_text_when_markdown_crashes(monkeypatch):
    import kabot.cli.commands as commands

    captured: list[object] = []

    def _fake_print(*args, **kwargs):
        captured.append(args[0] if args else None)

    def _fake_panel(body, **kwargs):
        return {"body": body, **kwargs}

    def _boom(_value):
        raise RuntimeError("markdown parser exploded")

    monkeypatch.setattr(commands.console, "print", _fake_print)
    monkeypatch.setattr(commands, "Panel", _fake_panel)
    monkeypatch.setattr(commands, "Markdown", _boom)

    commands._print_agent_response("**halo**", render_markdown=True)

    panel_payload = next(item for item in reversed(captured) if item is not None)

    assert isinstance(panel_payload["body"], Text)
