"""Rich/questionary UI primitives used by setup wizard."""

from __future__ import annotations

import os
import sys
from typing import Any

import questionary
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from kabot import __version__
from kabot.config.schema import Config

console = Console()

_INJECTED_BLOCK_LOGO = (
    " \\u2588\\u2588\\u2557  \\u2588\\u2588\\u2557 \\u2588\\u2588\\u2588\\u2588\\u2588\\u2557 "
    "\\u2588\\u2588\\u2588\\u2588\\u2588\\u2588\\u2557  \\u2588\\u2588\\u2588\\u2588\\u2588\\u2588\\u2557 "
    "\\u2588\\u2588\\u2588\\u2588\\u2588\\u2588\\u2588\\u2588\\u2557\n"
    " \\u2588\\u2588\\u2551 \\u2588\\u2588\\u2554\\u255d\\u2588\\u2588\\u2554\\u2550\\u2550\\u2588\\u2588\\u2557"
    "\\u2588\\u2588\\u2554\\u2550\\u2550\\u2588\\u2588\\u2557\\u2588\\u2588\\u2554\\u2550\\u2550\\u2550\\u2588\\u2588\\u2557"
    "\\u255a\\u2550\\u2550\\u2588\\u2588\\u2554\\u2550\\u2550\\u255d\n"
    " \\u2588\\u2588\\u2588\\u2588\\u2588\\u2554\\u255d \\u2588\\u2588\\u2588\\u2588\\u2588\\u2588\\u2588\\u2551"
    "\\u2588\\u2588\\u2588\\u2588\\u2588\\u2588\\u2554\\u255d\\u2588\\u2588\\u2551   \\u2588\\u2588\\u2551   \\u2588\\u2588\\u2551\n"
    " \\u2588\\u2588\\u2554\\u2550\\u2588\\u2588\\u2557 \\u2588\\u2588\\u2554\\u2550\\u2550\\u2588\\u2588\\u2551"
    "\\u2588\\u2588\\u2554\\u2550\\u2550\\u2588\\u2588\\u2557\\u2588\\u2588\\u2551   \\u2588\\u2588\\u2551   \\u2588\\u2588\\u2551\n"
    " \\u2588\\u2588\\u2551  \\u2588\\u2588\\u2557\\u2588\\u2588\\u2551  \\u2588\\u2588\\u2551"
    "\\u2588\\u2588\\u2588\\u2588\\u2588\\u2588\\u2554\\u255d\\u255a\\u2588\\u2588\\u2588\\u2588\\u2588\\u2588\\u2554\\u255d   \\u2588\\u2588\\u2551\n"
    " \\u255a\\u2550\\u255d  \\u255a\\u2550\\u255d\\u255a\\u2550\\u255d  \\u255a\\u2550\\u255d"
    "\\u255a\\u2550\\u2550\\u2550\\u2550\\u2550\\u255d  \\u255a\\u2550\\u2550\\u2550\\u2550\\u2550\\u255d    \\u255a\\u2550\\u255d"
)


def _force_utf8_console_for_block_logo() -> None:
    """Best-effort UTF-8 enforcement so injected block logo renders on Windows."""
    if os.name != "nt":
        return
    try:
        os.system("chcp 65001 >nul 2>nul")
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")
        except Exception:
            continue


def _build_injected_block_logo() -> str:
    """Decode ASCII escape payload into Unicode block logo at runtime."""
    return _INJECTED_BLOCK_LOGO.encode("ascii").decode("unicode_escape")


class ClackUI:
    """Helper to draw Kabot/Clack style UI components."""

    @staticmethod
    def header() -> None:
        _force_utf8_console_for_block_logo()
        logo = _build_injected_block_logo()
        console.print(f"[bold cyan]{logo}[/bold cyan]")
        console.print(f"   [bold]kabot {__version__}[/bold] - Light footprint, heavy punch.")
        console.print()

    @staticmethod
    def section_start(title: str) -> None:
        console.print(f"+  [bold cyan]{title}[/bold cyan]")

    @staticmethod
    def section_end() -> None:
        console.print("+")

    @staticmethod
    def summary_box(config: Config) -> None:
        c = config
        lines: list[str] = []

        model = c.agents.defaults.model
        if hasattr(model, "primary"):
            fallbacks = ", ".join(getattr(model, "fallbacks", []) or [])
            lines.append(f"model: {model.primary} (fallbacks: {fallbacks})")
        else:
            lines.append(f"model: {model}")

        mode = "local"
        lines.append(f"gateway.mode: {mode}")
        lines.append(f"gateway.port: {c.gateway.port}")

        bind = c.gateway.host or "loopback"
        if bind == "127.0.0.1" or bind == "localhost":
            bind = "loopback"
        elif bind == "0.0.0.0":
            bind = "all interfaces"
        lines.append(f"gateway.bind: {bind}")

        auth_status = "configured" if c.gateway.auth_token else "none"
        lines.append(f"gateway.auth: {auth_status}")

        active_channels: list[str] = []
        if c.channels.telegram.enabled:
            active_channels.append("telegram")
        if c.channels.whatsapp.enabled:
            active_channels.append("whatsapp")
        if c.channels.discord.enabled:
            active_channels.append("discord")
        if c.channels.slack.enabled:
            active_channels.append("slack")
        if c.channels.email.enabled:
            active_channels.append("email")
        if c.channels.dingtalk.enabled:
            active_channels.append("dingtalk")
        if c.channels.qq.enabled:
            active_channels.append("qq")
        if c.channels.feishu.enabled:
            active_channels.append("feishu")

        if active_channels:
            lines.append(f"channels: {', '.join(active_channels)}")

        tools: list[str] = []
        if (
            c.tools.web.search.api_key
            or c.tools.web.search.perplexity_api_key
            or c.tools.web.search.xai_api_key
            or c.tools.web.search.kimi_api_key
        ):
            tools.append("web_search")
        if c.tools.exec.docker.enabled:
            tools.append("docker_sandbox")
        if tools:
            lines.append(f"tools: {', '.join(tools)}")

        advanced_tools: list[str] = []
        if c.tools.web.fetch.firecrawl_api_key:
            advanced_tools.append("firecrawl")
        if c.tools.web.search.perplexity_api_key:
            advanced_tools.append("perplexity")
        if c.tools.web.search.kimi_api_key:
            advanced_tools.append("kimi")
        if c.tools.web.search.xai_api_key:
            advanced_tools.append("grok")
        if advanced_tools:
            lines.append(f"advanced: {', '.join(advanced_tools)}")

        ws_path = str(c.workspace_path)
        home = os.path.expanduser("~")
        if ws_path.startswith(home):
            ws_path = "~" + ws_path[len(home):]
        lines.append(f"workspace: {ws_path}")

        panel = Panel(
            "\n".join(lines),
            title="Existing config detected",
            title_align="left",
            border_style="dim",
            box=box.ROUNDED,
            padding=(1, 2),
        )

        console.print("|")
        grid = Table.grid(padding=(0, 1))
        grid.add_row(Text("* "), panel)
        console.print(grid)
        console.print("|")

    @staticmethod
    def clack_select(message: str, choices: list[Any], default: Any = None) -> Any:
        """A questionary select styled with Clack vertical lines.

        Adds a Back option automatically when the caller did not provide one.
        Selecting Back returns None so callers can reuse existing cancel paths.
        """
        normalized_choices = list(choices)
        has_back = False
        for choice in normalized_choices:
            value = getattr(choice, "value", None)
            title = str(getattr(choice, "title", "")).strip().lower()
            if value in {"back", "__back__"} or title == "back":
                has_back = True
                break
        if not has_back:
            normalized_choices.append(questionary.Choice("Back", value="__back__"))

        # Non-interactive environments (e.g. piped stdin / CI) cannot render
        # prompt_toolkit menus; fallback to provided default if available.
        stdin_tty = bool(getattr(sys.stdin, "isatty", lambda: False)())
        stdout_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
        if not (stdin_tty and stdout_tty):
            available_values = {getattr(choice, "value", None) for choice in normalized_choices}
            if default in available_values and default not in {None, "__back__", "back"}:
                return default
            for choice in normalized_choices:
                value = getattr(choice, "value", None)
                if value not in {None, "__back__", "back"}:
                    return value
            return None

        console.print("|")
        result = questionary.select(
            f"*  {message}",
            choices=normalized_choices,
            default=default,
            style=questionary.Style(
                [
                    ("qmark", "fg:cyan bold"),
                    ("question", "bold"),
                    ("pointer", "fg:cyan bold noinherit"),
                    ("text", "fg:white noinherit"),
                    ("highlighted", "fg:cyan bold noinherit"),
                    # Focused/default-selected option should stay cyan.
                    ("selected", "fg:cyan bold noinherit"),
                    ("answer", "fg:white bold noinherit"),
                ]
            ),
        ).ask()
        if result in {None, "__back__", "back"}:
            console.print("|  [yellow]Cancelled[/yellow]")
            return None
        return result
