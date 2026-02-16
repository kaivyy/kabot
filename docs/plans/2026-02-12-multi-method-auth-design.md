# Multi-Method Authentication System Design

**Date**: 2026-02-12
**Status**: Approved
**Author**: Design Session
**Scope**: Add multi-method authentication support to Kabot (OAuth, Device Flow, Setup Token, API Key)

---

## 📋 Executive Summary

### Problem Statement

Kabot currently supports only **one authentication method per provider** (API Key). This limits flexibility and prevents users from using:
- OAuth flows (better security, subscription-based access)
- Device flows (for headless/VPS environments)
- Setup tokens (provider-specific alternatives)
- Subscription-based coding plans (Kimi Code, MiniMax Coding)

### Solution

Implement a **multi-method authentication system** inspired by OpenClaw's architecture, supporting:
- **6 providers** (OpenAI, Anthropic, Google, Ollama, Kimi, MiniMax)
- **13 authentication methods** total
- **Backward compatibility** with existing single-method handlers
- **VPS-aware** OAuth flows (auto-detects SSH/remote environments)

### Success Criteria

- ✅ All 6 providers working with all methods
- ✅ OAuth works on local and VPS
- ✅ 85%+ test coverage
- ✅ Zero regressions in existing auth flow
- ✅ Backward compatible with v0.x

---

## 🎯 Scope

### In Scope

**Core Infrastructure:**
- Menu structure refactor (support multiple methods per provider)
- AuthManager refactor (dynamic handler loading, method selection)
- OAuth callback server (async, VPS-aware)
- CLI integration (`--method` flag, `auth methods` command)

**Providers & Methods (6 providers, 13 methods):**

1. **OpenAI** (2 methods)
   - API Key (`sk-...`)
   - OAuth (ChatGPT subscription)

2. **Anthropic** (2 methods)
   - API Key (`sk-ant-...`)
   - Setup Token (from `claude setup-token`)

3. **Google** (2 methods)
   - API Key (`AIza...`)
   - OAuth (Google account)

4. **Ollama** (1 method)
   - Local URL config (no auth)

5. **Kimi/Moonshot** (2 methods)
   - API Key (general)
   - Kimi Code API Key (subscription, coding-specialized)

6. **MiniMax** (2 methods)
   - General API Key (token-based)
   - Coding Plan Key (subscription, unlimited)

**Testing:**
- Unit tests for all handlers
- Integration tests for AuthManager
- OAuth callback server tests
- CLI command tests
- 85%+ code coverage

**Documentation:**
- README updates
- Authentication guide
- Migration guide
- CLI help text

### Out of Scope

- Device Flow (GitHub Copilot style) - Future work
- Additional providers beyond the 6 listed
- OAuth for providers without official OAuth support
- Web UI for authentication management
- Multi-account support (multiple API keys per provider)

---

## 🏗️ Architecture

### Current Architecture (v0.x)

```
User runs: kabot auth login openai
    ↓
AuthManager.login(provider_id)
    ↓
Load single handler: AUTH_PROVIDERS[provider_id]["handler"]
    ↓
Handler.authenticate() → Returns API key
    ↓
Save to config
```

**Limitation**: Only one handler per provider, always API key.

### New Architecture (v1.x)

```
User runs: kabot auth login openai [--method oauth]
    ↓
AuthManager.login(provider_id, method_id=None)
    ↓
If method_id is None:
    Show method selection menu
    User selects: [1] API Key or [2] OAuth
    ↓
Load handler dynamically:
    AUTH_PROVIDERS[provider_id]["methods"][method_id]["handler"]
    ↓
Handler.authenticate() → Returns credentials
    ↓
Save to config
```

**Benefits**:
- ✅ Multiple methods per provider
- ✅ Interactive or direct selection
- ✅ Extensible (easy to add new methods)
- ✅ Backward compatible (single-method providers auto-skip menu)

---

## 📦 Component Design

### 1. Menu Structure (`kabot/auth/menu.py`)

**Current Structure:**
```python
AUTH_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "description": "GPT-4o, o1-preview, etc.",
        "handler": OpenAIHandler  # Single handler
    }
}
```

**New Structure:**
```python
AUTH_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "description": "GPT-4o, o1-preview, etc.",
        "methods": {  # Multiple methods
            "api_key": {
                "label": "API Key (Manual)",
                "description": "Standard API key (sk-...)",
                "handler": "kabot.auth.handlers.openai_key.OpenAIKeyHandler"
            },
            "oauth": {
                "label": "Browser Login (OAuth)",
                "description": "ChatGPT subscription login",
                "handler": "kabot.auth.handlers.openai_oauth.OpenAIOAuthHandler"
            }
        }
    },
    "anthropic": {
        "name": "Anthropic",
        "description": "Claude 3.5 Sonnet, Opus, etc.",
        "methods": {
            "api_key": {
                "label": "API Key (Manual)",
                "description": "Standard API key (sk-ant-...)",
                "handler": "kabot.auth.handlers.anthropic_key.AnthropicKeyHandler"
            },
            "setup_token": {
                "label": "Setup Token",
                "description": "From 'claude setup-token' command",
                "handler": "kabot.auth.handlers.anthropic_token.AnthropicTokenHandler"
            }
        }
    },
    "google": {
        "name": "Google Gemini",
        "description": "Gemini 1.5 Pro, Flash",
        "methods": {
            "api_key": {
                "label": "API Key (Manual)",
                "description": "Standard API key (AIza...)",
                "handler": "kabot.auth.handlers.google_key.GoogleKeyHandler"
            },
            "oauth": {
                "label": "Browser Login (OAuth)",
                "description": "Google account login",
                "handler": "kabot.auth.handlers.google_oauth.GoogleOAuthHandler"
            }
        }
    },
    "ollama": {
        "name": "Ollama",
        "description": "Local models (Llama 3, Mistral)",
        "methods": {
            "url": {
                "label": "Local URL",
                "description": "Configure local Ollama server",
                "handler": "kabot.auth.handlers.ollama_url.OllamaURLHandler"
            }
        }
    },
    "kimi": {
        "name": "Kimi (Moonshot AI)",
        "description": "Kimi K1, K2.5 - Long context",
        "methods": {
            "api_key": {
                "label": "API Key (General)",
                "description": "Standard Moonshot API key",
                "handler": "kabot.auth.handlers.kimi_key.KimiKeyHandler"
            },
            "kimi_code": {
                "label": "Kimi Code (Subscription)",
                "description": "Coding-specialized subscription plan",
                "handler": "kabot.auth.handlers.kimi_code.KimiCodeHandler"
            }
        }
    },
    "minimax": {
        "name": "MiniMax",
        "description": "MiniMax M2, M2.1 models",
        "methods": {
            "api_key": {
                "label": "API Key (Pay-as-you-go)",
                "description": "Token-based billing",
                "handler": "kabot.auth.handlers.minimax_key.MiniMaxKeyHandler"
            },
            "coding_plan": {
                "label": "Coding Plan (Subscription)",
                "description": "Unlimited monthly subscription",
                "handler": "kabot.auth.handlers.minimax_coding.MiniMaxCodingHandler"
            }
        }
    }
}
```

**Key Changes:**
- `handler` field → `methods` dict
- Each method has: `label`, `description`, `handler` (as string path)
- Handler path as string for lazy loading (avoid circular imports)

**Helper Functions:**
```python
def get_auth_choices():
    """Returns list of provider choices for interactive menu."""
    return [
        {"name": f"{meta['name']} - {meta['description']}", "value": key}
        for key, meta in AUTH_PROVIDERS.items()
    ]

def get_method_choices(provider_id: str):
    """Returns list of method choices for a specific provider."""
    methods = AUTH_PROVIDERS[provider_id]["methods"]
    return [
        {
            "id": method_id,
            "label": method_info["label"],
            "description": method_info["description"]
        }
        for method_id, method_info in methods.items()
    ]
```

---

### 2. AuthManager (`kabot/auth/manager.py`)

**Updated `login()` Method:**

```python
def login(self, provider_id: str, method_id: str = None) -> bool:
    """
    Execute login flow with method selection.

    Args:
        provider_id: Provider (e.g., "openai")
        method_id: Optional method (e.g., "oauth"). If None, show menu.

    Returns:
        True if authentication successful, False otherwise
    """
    # 1. Validate provider
    if provider_id not in AUTH_PROVIDERS:
        console.print(f"[red]Provider '{provider_id}' not found[/red]")
        return False

    provider = AUTH_PROVIDERS[provider_id]

    # 2. Method selection (if multiple methods available)
    if method_id is None:
        methods = provider["methods"]

        # If only 1 method, use it directly (no menu)
        if len(methods) == 1:
            method_id = list(methods.keys())[0]
            console.print(f"[dim]Using {methods[method_id]['label']}[/dim]")
        else:
            # Show method selection menu
            method_id = self._prompt_method_selection(provider_id, methods)
            if not method_id:
                return False

    # 3. Validate method
    if method_id not in provider["methods"]:
        console.print(f"[red]Method '{method_id}' not found for {provider_id}[/red]")
        return False

    # 4. Load handler dynamically
    try:
        handler = self._load_handler(provider_id, method_id)
    except Exception as e:
        console.print(f"[red]Failed to load handler: {e}[/red]")
        return False

    # 5. Execute authentication
    try:
        auth_data = handler.authenticate()
    except KeyboardInterrupt:
        console.print("\n[yellow]Authentication cancelled.[/yellow]")
        return False
    except TimeoutError:
        console.print("\n[red]Authentication timed out.[/red]")
        return False
    except Exception as e:
        console.print(f"\n[red]Authentication failed: {e}[/red]")
        return False

    if not auth_data:
        console.print("[yellow]No credentials provided.[/yellow]")
        return False

    # 6. Validate auth data
    if not self._validate_auth_data(auth_data):
        console.print("[red]Invalid authentication data format.[/red]")
        return False

    # 7. Save credentials
    return self._save_credentials(auth_data)
```

**New Helper Methods:**

```python
def _load_handler(self, provider_id: str, method_id: str):
    """Dynamically load handler class from string path."""
    import importlib

    provider = AUTH_PROVIDERS[provider_id]
    method = provider["methods"][method_id]
    handler_path = method["handler"]

    # Parse "kabot.auth.handlers.openai_key.OpenAIKeyHandler"
    module_path, class_name = handler_path.rsplit(".", 1)

    module = importlib.import_module(module_path)
    handler_class = getattr(module, class_name)
    return handler_class()

def _prompt_method_selection(self, provider_id: str, methods: Dict) -> Optional[str]:
    """Show interactive method selection menu."""
    from rich.prompt import Prompt
    from rich.table import Table

    provider_name = AUTH_PROVIDERS[provider_id]["name"]

    # Build method selection table
    table = Table(title=f"{provider_name} Authentication")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Method", style="green")
    table.add_column("Description", style="dim")

    method_list = list(methods.items())
    for idx, (method_id, method_info) in enumerate(method_list, 1):
        table.add_row(
            str(idx),
            method_info["label"],
            method_info["description"]
        )

    console.print("\n")
    console.print(table)
    console.print("\n")

    # Prompt for selection
    choices = [str(i) for i in range(1, len(method_list) + 1)]
    selection = Prompt.ask("Select authentication method", choices=choices)

    selected_method_id = method_list[int(selection) - 1][0]
    return selected_method_id

def _validate_auth_data(self, auth_data: Dict[str, Any]) -> bool:
    """Validate auth data structure."""
    if not isinstance(auth_data, dict):
        return False

    if "providers" not in auth_data:
        return False

    # Check at least one provider has credentials
    for provider_data in auth_data["providers"].values():
        if "api_key" in provider_data or "oauth_token" in provider_data:
            return True

    return False
```

---

### 3. Handler Architecture

**Base Handler** (`kabot/auth/handlers/base.py` - No Changes)

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class AuthHandler(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider display name"""
        pass

    @abstractmethod
    def authenticate(self) -> Dict[str, Any]:
        """Execute auth flow, return config dict"""
        pass

    def validate(self, credentials: Dict[str, Any]) -> bool:
        """Optional validation (can override)"""
        return True
```

**Handler File Structure:**

```
kabot/auth/handlers/
├── __init__.py
├── base.py                    # Base handler (existing)
├── utils.py                   # Utilities (existing)
├── openai_key.py             # New: OpenAI API Key
├── openai_oauth.py           # New: OpenAI OAuth
├── anthropic_key.py          # New: Anthropic API Key
├── anthropic_token.py        # New: Anthropic Setup Token
├── google_key.py             # New: Google API Key
├── google_oauth.py           # New: Google OAuth
├── ollama_url.py             # Rename: ollama.py → ollama_url.py
├── kimi_key.py               # New: Kimi API Key
├── kimi_code.py              # New: Kimi Code subscription
├── minimax_key.py            # New: MiniMax API Key
└── minimax_coding.py         # New: MiniMax Coding Plan
```

**Example Handler: OpenAI API Key**

```python
# kabot/auth/handlers/openai_key.py

from typing import Dict, Any
import os
from rich.prompt import Prompt
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

class OpenAIKeyHandler(AuthHandler):
    @property
    def name(self) -> str:
        return "OpenAI (API Key)"

    def authenticate(self) -> Dict[str, Any]:
        from rich.console import Console
        console = Console()

        console.print("\n[bold]OpenAI API Key Setup[/bold]")
        console.print("Get your API key from: https://platform.openai.com/api-keys\n")

        # Check env var first
        env_key = os.environ.get("OPENAI_API_KEY")
        if env_key:
            use_env = Prompt.ask(
                f"Found OPENAI_API_KEY in environment ({env_key[:8]}...). Use this?",
                choices=["y", "n"],
                default="y"
            )
            if use_env == "y":
                return {"providers": {"openai": {"api_key": env_key}}}

        # Manual input
        api_key = secure_input("Enter OpenAI API Key")

        if not api_key:
            return None

        return {"providers": {"openai": {"api_key": api_key}}}
```

**Example Handler: OpenAI OAuth**

```python
# kabot/auth/handlers/openai_oauth.py

from typing import Dict, Any
from rich.console import Console
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import is_vps, run_oauth_flow

console = Console()

class OpenAIOAuthHandler(AuthHandler):
    @property
    def name(self) -> str:
        return "OpenAI (OAuth)"

    def authenticate(self) -> Dict[str, Any]:
        console.print("\n[bold]OpenAI OAuth Setup[/bold]")
        console.print("This requires a ChatGPT subscription.\n")

        # OAuth configuration
        auth_url = self._build_auth_url()

        try:
            token = run_oauth_flow(auth_url, port=8765)
        except TimeoutError:
            console.print("[red]OAuth flow timed out.[/red]")
            return None

        if not token:
            return None

        return {"providers": {"openai": {"oauth_token": token}}}

    def _build_auth_url(self) -> str:
        """Build OpenAI OAuth authorization URL."""
        # TODO: Use actual OpenAI OAuth endpoints
        client_id = "kabot-openai"
        redirect_uri = "http://localhost:8765/callback"
        base_url = "https://auth.openai.com/authorize"

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid profile"
        }

        query = '&'.join(f"{k}={v}" for k, v in params.items())
        return f"{base_url}?{query}"
```

---

### 4. OAuth Callback Server (`kabot/auth/oauth_callback.py`)

**New File:**

```python
# kabot/auth/oauth_callback.py

import asyncio
from aiohttp import web
import secrets

class OAuthCallbackServer:
    """Local HTTP server to handle OAuth callbacks."""

    def __init__(self, port: int = 8765):
        self.port = port
        self.token = None
        self.state = secrets.token_urlsafe(32)
        self.app = web.Application()
        self.app.router.add_get('/callback', self.handle_callback)

    async def handle_callback(self, request):
        """Handle OAuth callback and extract token."""
        # Verify state to prevent CSRF
        received_state = request.query.get('state')
        if received_state != self.state:
            return web.Response(
                text="Invalid state parameter (CSRF protection)",
                status=400
            )

        # Extract token/code
        self.token = request.query.get('code') or request.query.get('token')

        # Return success page
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    text-align: center;
                    padding: 50px;
                    background: #f5f5f5;
                }
                .success {
                    background: white;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    max-width: 500px;
                    margin: 0 auto;
                }
                h1 { color: #22c55e; }
            </style>
        </head>
        <body>
            <div class="success">
                <h1>✓ Authentication Successful</h1>
                <p>You can close this window and return to the terminal.</p>
            </div>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')

    async def start_and_wait(self, timeout: int = 300):
        """Start server and wait for callback."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', self.port)
        await site.start()

        from rich.console import Console
        console = Console()
        console.print(f"[dim]Waiting for OAuth callback on port {self.port}...[/dim]")

        # Wait for token with timeout
        for _ in range(timeout):
            if self.token:
                await runner.cleanup()
                return self.token
            await asyncio.sleep(1)

        await runner.cleanup()
        raise TimeoutError("OAuth callback timed out after 5 minutes")

    def get_auth_url(self, base_url: str, params: dict) -> str:
        """Build OAuth authorization URL with state."""
        params['state'] = self.state
        query = '&'.join(f"{k}={v}" for k, v in params.items())
        return f"{base_url}?{query}"
```

---

### 5. Utilities (`kabot/auth/utils.py`)

**New Functions:**

```python
# kabot/auth/utils.py (ADDITIONS)

import asyncio
from typing import Optional

def run_oauth_flow(auth_url: str, port: int = 8765) -> str:
    """
    Run OAuth flow: open browser, start callback server, return token.

    Works in both local and VPS environments.

    Args:
        auth_url: OAuth authorization URL
        port: Local server port (default 8765)

    Returns:
        OAuth token/code

    Raises:
        TimeoutError: If OAuth flow times out
    """
    from kabot.auth.oauth_callback import OAuthCallbackServer
    from rich.console import Console
    import webbrowser

    console = Console()

    if is_vps():
        # VPS mode: Manual flow
        console.print("\n[yellow]VPS Environment Detected[/yellow]")
        console.print("\n[bold]Please open this URL in your browser:[/bold]")
        console.print(f"[cyan]{auth_url}[/cyan]\n")

        token = secure_input("Paste the authorization code/token")
        return token
    else:
        # Local mode: Automatic flow
        console.print("[dim]Opening browser for authentication...[/dim]")
        webbrowser.open(auth_url)

        # Start callback server
        server = OAuthCallbackServer(port=port)
        loop = asyncio.get_event_loop()
        token = loop.run_until_complete(server.start_and_wait())

        return token

def validate_api_key(key: str, pattern: str = None) -> bool:
    """
    Validate API key format.

    Args:
        key: API key to validate
        pattern: Optional regex pattern to match

    Returns:
        True if valid, False otherwise
    """
    if not key or len(key) < 10:
        return False

    if pattern:
        import re
        return bool(re.match(pattern, key))

    return True
```

---

### 6. CLI Integration (`kabot/cli/commands.py`)

**Updated `auth login` Command:**

```python
@auth_app.command("login")
def auth_login(
    provider: str = typer.Argument(None, help="Provider ID (e.g., openai, anthropic)"),
    method: str = typer.Option(None, "--method", "-m", help="Auth method (e.g., oauth, api_key)")
):
    """Login to a provider with optional method selection."""
    from kabot.auth.manager import AuthManager
    from kabot.auth.menu import get_auth_choices, AUTH_PROVIDERS
    from rich.prompt import Prompt

    manager = AuthManager()

    # If no provider, show provider selection
    if not provider:
        choices = get_auth_choices()
        console.print("\n[bold]Select a provider:[/bold]\n")

        for idx, choice in enumerate(choices, 1):
            console.print(f"  [{idx}] {choice['name']}")

        console.print()
        choice_idx = Prompt.ask(
            "Select option",
            choices=[str(i) for i in range(1, len(choices)+1)]
        )
        provider = choices[int(choice_idx)-1]['value']

    # Execute login with optional method
    success = manager.login(provider, method_id=method)

    if success:
        console.print(f"\n[green]✓ Successfully configured {provider}![/green]")
    else:
        console.print(f"\n[red]✗ Authentication failed[/red]")
        raise typer.Exit(1)
```

**New `auth methods` Command:**

```python
@auth_app.command("methods")
def auth_methods(
    provider: str = typer.Argument(..., help="Provider ID")
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
```

---

## 🧪 Testing Strategy

### Test Coverage Goals

- **Unit Tests**: 85%+ coverage
- **Integration Tests**: All critical flows
- **Total Tests**: ~55-65 tests

### Test Structure

```
tests/
├── auth/
│   ├── test_manager.py           # AuthManager tests (~10 tests)
│   ├── test_menu.py              # Menu structure tests (~5 tests)
│   ├── test_oauth_callback.py    # OAuth server tests (~5 tests)
│   ├── handlers/
│   │   ├── test_openai_key.py    # ~4 tests
│   │   ├── test_openai_oauth.py  # ~3 tests
│   │   ├── test_anthropic_key.py # ~4 tests
│   │   ├── test_anthropic_token.py # ~3 tests
│   │   ├── test_google_key.py    # ~4 tests
│   │   ├── test_google_oauth.py  # ~3 tests
│   │   ├── test_kimi_key.py      # ~4 tests
│   │   ├── test_kimi_code.py     # ~3 tests
│   │   ├── test_minimax_key.py   # ~4 tests
│   │   └── test_minimax_coding.py # ~3 tests
│   └── utils/
│       ├── test_vps_detection.py # ~5 tests
│       └── test_oauth_flow.py    # ~3 tests
└── cli/
    └── test_auth_commands.py     # ~5 tests
```

### Key Test Scenarios

**AuthManager:**
- ✅ Login with method specified
- ✅ Login without method (shows menu)
- ✅ Login with single-method provider (auto-skip menu)
- ✅ Invalid provider
- ✅ Invalid method
- ✅ Authentication cancelled (KeyboardInterrupt)
- ✅ Authentication timeout
- ✅ Auth data validation

**Handlers:**
- ✅ Env var detection and usage
- ✅ Manual input
- ✅ Invalid input handling
- ✅ OAuth flow (local mode)
- ✅ OAuth flow (VPS mode)

**OAuth Callback:**
- ✅ Successful callback
- ✅ Invalid state (CSRF protection)
- ✅ Timeout handling

**CLI:**
- ✅ `kabot auth login <provider>`
- ✅ `kabot auth login <provider> --method <method>`
- ✅ `kabot auth methods <provider>`
- ✅ Invalid provider/method

---

## 📚 Documentation

### Files to Update/Create

1. **README.md** - Add multi-method auth section with examples
2. **docs/authentication.md** (NEW) - Comprehensive auth guide
3. **docs/migration/multi-method-auth.md** (NEW) - Migration guide from v0.x
4. **CLI help text** - Update command descriptions

### Key Documentation Topics

- Multi-method authentication overview
- Provider-specific auth methods
- OAuth flow explanation (local vs VPS)
- Environment variable usage
- CLI command reference
- Migration guide for existing users
- Troubleshooting guide

---

## 📅 Implementation Timeline

### Phase 1: Foundation (Week 1)
- Menu structure refactor
- AuthManager refactor
- Testing infrastructure
- **Deliverable**: Core infrastructure ready

### Phase 2: OAuth Infrastructure (Week 2)
- OAuth callback server
- OAuth utilities
- OpenAI OAuth handler
- **Deliverable**: Working OAuth for OpenAI

### Phase 3: Core Providers (Week 2)
- Split existing handlers (OpenAI, Anthropic, Google, Ollama)
- Create new method handlers
- Integration testing
- **Deliverable**: All existing providers with multi-method

### Phase 4: New Providers (Week 3)
- Kimi handlers (API Key + Code)
- MiniMax handlers (API Key + Coding)
- Testing
- **Deliverable**: 6 providers, 13 methods complete

### Phase 5: Polish & Release (Week 4)
- CLI integration
- Documentation
- Final testing
- Release v1.0.0
- **Deliverable**: Production-ready release

**Total Timeline**: 4-5 weeks

---

## 🔄 Migration & Backward Compatibility

### Backward Compatibility

- ✅ **Zero breaking changes**
- ✅ Existing API key flows work unchanged
- ✅ Single-method providers auto-skip menu
- ✅ Config format unchanged

### Migration Path for Users

```bash
# Before (v0.x)
kabot auth login openai
# → Always API key

# After (v1.x)
kabot auth login openai
# → Shows method menu if multiple methods
# → Auto-uses API key if single method

# Direct method selection (new)
kabot auth login openai --method oauth
```

### Migration Checklist

- [ ] Update kabot: `pip install --upgrade kabot`
- [ ] Test existing auth: `kabot auth status`
- [ ] Try new methods: `kabot auth methods openai`
- [ ] Update automation scripts with `--method` flag if needed

---

## 📊 Success Metrics

### Functionality
- [ ] All 6 providers working with all methods
- [ ] OAuth works on local and VPS
- [ ] 85%+ test coverage
- [ ] Zero regressions

### Performance
- [ ] OAuth callback < 3 seconds (local)
- [ ] Method selection menu < 1 second
- [ ] Handler loading < 500ms

### User Experience
- [ ] Clear method descriptions
- [ ] VPS detection accuracy > 95%
- [ ] Setup wizard completion > 90%

### Adoption (30 days post-release)
- [ ] > 50% of new users use OAuth (where available)
- [ ] < 5 critical bugs
- [ ] > 100 successful OAuth authentications

---

## 🚨 Risks & Mitigations

### Risk 1: OAuth Callback Port Conflicts
**Risk**: Port 8765 might be in use
**Mitigation**: Auto-retry with random port 8766-8799
**Severity**: Low

### Risk 2: VPS Detection False Positives
**Risk**: Local detected as VPS (no browser)
**Mitigation**: Provide fallback option to paste URL
**Severity**: Low

### Risk 3: Provider OAuth Changes
**Risk**: Providers change OAuth endpoints
**Mitigation**: Document URLs, easy to update handlers
**Severity**: Medium

### Risk 4: Test Coverage Gaps
**Risk**: Edge cases not covered
**Mitigation**: Comprehensive test plan, manual testing
**Severity**: Medium

---

## 🎯 Future Enhancements (Out of Scope)

- Device Flow (GitHub Copilot style)
- Additional providers (DeepSeek, xAI, Groq)
- Web UI for auth management
- Multi-account support
- Auth status dashboard
- Token refresh automation

---

## ✅ Approval

**Design Approved**: 2026-02-12
**Next Steps**: Create implementation plan

**Implementation Plan**: See `docs/plans/2026-02-12-multi-method-auth-implementation.md`
