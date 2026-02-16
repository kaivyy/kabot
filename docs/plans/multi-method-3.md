## Task 12: Update CLI Commands

**Files:**
- Modify: `kabot/cli/commands.py`
- Create: `tests/cli/test_auth_commands.py`

**Step 1: Write failing tests**

Create `tests/cli/__init__.py` and `tests/cli/test_auth_commands.py`:

```bash
mkdir -p tests/cli
touch tests/cli/__init__.py
```

Create `tests/cli/test_auth_commands.py`:

```python
"""Tests for auth CLI commands."""
import pytest
from typer.testing import CliRunner
from unittest.mock import patch


@pytest.fixture
def runner():
    return CliRunner()


def test_auth_login_command_exists(runner):
    """auth login command should exist."""
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "login", "--help"])
    assert result.exit_code == 0
    assert "Login to a provider" in result.output


def test_auth_methods_command_exists(runner):
    """auth methods command should exist."""
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "methods", "--help"])
    assert result.exit_code == 0


def test_auth_login_accepts_method_option(runner):
    """auth login should accept --method option."""
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "login", "--help"])
    assert "--method" in result.output or "-m" in result.output


def test_auth_methods_with_valid_provider(runner):
    """auth methods should show methods for valid provider."""
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "methods", "openai"])
    assert result.exit_code == 0
    assert "API Key" in result.output


def test_auth_methods_with_invalid_provider(runner):
    """auth methods should error for invalid provider."""
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "methods", "invalid_provider"])
    assert result.exit_code == 1
    assert "not found" in result.output
```

**Step 2: Update commands.py**

Find and update the auth commands section in `kabot/cli/commands.py`:

```python
# ============================================================================
# Auth Commands
# ============================================================================

auth_app = typer.Typer(help="Manage authentication")
app.add_typer(auth_app, name="auth")


@auth_app.command("list")
def auth_list():
    """List supported authentication providers."""
    from kabot.auth.manager import AuthManager
    from kabot.auth.menu import AUTH_PROVIDERS
    from rich.table import Table

    table = Table(title="Supported Providers")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Methods", style="yellow")

    for pid, meta in AUTH_PROVIDERS.items():
        methods = ", ".join(meta["methods"].keys())
        table.add_row(pid, meta["name"], methods)

    console.print(table)


@auth_app.command("login")
def auth_login(
    provider: str = typer.Argument(None, help="Provider ID (e.g., openai, anthropic)"),
    method: str = typer.Option(None, "--method", "-m", help="Auth method (e.g., oauth, api_key)"),
):
    """Login to a provider with optional method selection."""
    from kabot.auth.manager import AuthManager
    from kabot.auth.menu import get_auth_choices, AUTH_PROVIDERS
    from rich.prompt import Prompt

    manager = AuthManager()

    # If no provider, show provider selection
    if not provider:
        choices = get_auth_choices()
        console.print("\n[bold]Select a provider to configure:[/bold]\n")

        for idx, choice in enumerate(choices, 1):
            console.print(f"  [{idx}] {choice['name']}")

        console.print()
        try:
            choice_idx = Prompt.ask(
                "Select option",
                choices=[str(i) for i in range(1, len(choices)+1)]
            )
            provider = choices[int(choice_idx)-1]['value']
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    # Execute login with optional method
    success = manager.login(provider, method_id=method)

    if success:
        console.print(f"\n[green]✓ Successfully configured {provider}![/green]")
    else:
        console.print(f"\n[red]✗ Authentication failed[/red]")
        raise typer.Exit(1)


@auth_app.command("methods")
def auth_methods(
    provider: str = typer.Argument(..., help="Provider ID"),
):
    """List available authentication methods for a provider."""
    from kabot.auth.menu import AUTH_PROVIDERS
    from rich.table import Table

    if provider not in AUTH_PROVIDERS:
        console.print(f"[red]Provider '{provider}' not found[/red]")
        console.print("\nAvailable providers:")
        for pid in AUTH_PROVIDERS.keys():
            console.print(f"  - {pid}")
        raise typer.Exit(1)

    provider_info = AUTH_PROVIDERS[provider]
    methods = provider_info["methods"]

    table = Table(title=f"{provider_info['name']} - Authentication Methods")
    table.add_column("Method ID", style="cyan")
    table.add_column("Label", style="green")
    table.add_column("Description", style="dim")

    for method_id, method_info in methods.items():
        table.add_row(
            method_id,
            method_info["label"],
            method_info["description"]
        )

    console.print("\n")
    console.print(table)
    console.print("\n")
    console.print(f"[dim]Usage: kabot auth login {provider} --method <method_id>[/dim]")


@auth_app.command("status")
def auth_status():
    """Show authentication status."""
    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    manager.get_status()
```

**Step 3: Run tests**

```bash
pytest tests/cli/test_auth_commands.py -v
```

Expected: All tests PASS

**Step 4: Commit**

```bash
git add kabot/cli/commands.py tests/cli/
git commit -m "feat: update auth CLI commands for multi-method support

- Add --method/-m option to auth login
- Add auth methods command to show available methods
- Update auth list to show methods per provider
- Add usage hint in auth methods output

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 13: Update Handlers __init__.py

**Files:**
- Modify: `kabot/auth/handlers/__init__.py`

**Step 1: Update __init__.py to export all handlers**

Update `kabot/auth/handlers/__init__.py`:

```python
"""Authentication handlers for multiple providers and methods."""

from kabot.auth.handlers.base import AuthHandler
from kabot.auth.handlers.openai_key import OpenAIKeyHandler
from kabot.auth.handlers.anthropic_key import AnthropicKeyHandler
from kabot.auth.handlers.google_key import GoogleKeyHandler
from kabot.auth.handlers.ollama_url import OllamaURLHandler
from kabot.auth.handlers.kimi_key import KimiKeyHandler
from kabot.auth.handlers.kimi_code import KimiCodeHandler
from kabot.auth.handlers.minimax_key import MiniMaxKeyHandler
from kabot.auth.handlers.minimax_coding import MiniMaxCodingHandler

__all__ = [
    "AuthHandler",
    "OpenAIKeyHandler",
    "AnthropicKeyHandler",
    "GoogleKeyHandler",
    "OllamaURLHandler",
    "KimiKeyHandler",
    "KimiCodeHandler",
    "MiniMaxKeyHandler",
    "MiniMaxCodingHandler",
]
```

**Step 2: Commit**

```bash
git add kabot/auth/handlers/__init__.py
git commit -m "chore: update handlers __init__.py with all new handlers

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 14: Run Full Test Suite

**Step 1: Run all auth tests**

```bash
pytest tests/auth/ -v --tb=short
```

Expected: All tests PASS

**Step 2: Run with coverage**

```bash
pytest tests/auth/ --cov=kabot.auth --cov-report=term-missing
```

Expected: 85%+ coverage

**Step 3: Commit if any fixes needed**

```bash
git add -A
git commit -m "test: ensure all auth tests pass

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 15: Integration Test

**Step 1: Test CLI manually**

```bash
# Test auth list
python -m kabot.cli.commands auth list

# Test auth methods
python -m kabot.cli.commands auth methods openai
python -m kabot.cli.commands auth methods kimi
python -m kabot.cli.commands auth methods minimax

# Test auth status
python -m kabot.cli.commands auth status
```

**Step 2: Verify output looks correct**

Expected output for `auth methods openai`:
```
┌──────────────────────────────────────────────────────────────┐
│                  OpenAI - Authentication Methods             │
├────────────┬────────────────────────┬────────────────────────┤
│ Method ID  │ Label                  │ Description            │
├────────────┼────────────────────────┼────────────────────────┤
│ api_key    │ API Key (Manual)       │ Standard API key (sk-…)│
│ oauth      │ Browser Login (OAuth)  │ ChatGPT subscription   │
└────────────┴────────────────────────┴────────────────────────┘

Usage: kabot auth login openai --method <method_id>
```

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete multi-method authentication system

Implemented:
- 6 providers (OpenAI, Anthropic, Google, Ollama, Kimi, MiniMax)
- 11 authentication methods total
- Dynamic handler loading via importlib
- Method selection menu for providers with multiple methods
- CLI integration with --method flag
- Backward compatible with single-method providers

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Summary

**Total Tasks**: 15
**Estimated Time**: 3-4 hours
**Test Coverage Target**: 85%+

**Files Created/Modified**:
- `kabot/auth/menu.py` (modified)
- `kabot/auth/manager.py` (modified)
- `kabot/auth/handlers/openai_key.py` (renamed from openai.py)
- `kabot/auth/handlers/anthropic_key.py` (renamed from anthropic.py)
- `kabot/auth/handlers/google_key.py` (renamed from google.py)
- `kabot/auth/handlers/ollama_url.py` (renamed from ollama.py)
- `kabot/auth/handlers/kimi_key.py` (new)
- `kabot/auth/handlers/kimi_code.py` (new)
- `kabot/auth/handlers/minimax_key.py` (new)
- `kabot/auth/handlers/minimax_coding.py` (new)
- `kabot/auth/handlers/__init__.py` (modified)
- `kabot/cli/commands.py` (modified)
- `tests/auth/test_menu.py` (new)
- `tests/auth/test_manager.py` (new)
- `tests/auth/handlers/test_*.py` (8 new files)
- `tests/cli/test_auth_commands.py` (new)

**Next Phase**: OAuth handlers and callback server (Tasks 16-20 in future sprint)
