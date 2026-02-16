## Task 8: Create Kimi Code Handler

**Files:**
- Create: `kabot/auth/handlers/kimi_code.py`
- Create: `tests/auth/handlers/test_kimi_code.py`

**Step 1: Write failing test**

Create `tests/auth/handlers/test_kimi_code.py`:

```python
"""Tests for Kimi Code subscription handler."""
import pytest
from unittest.mock import patch


def test_kimi_code_handler_exists():
    """KimiCodeHandler class should exist."""
    from kabot.auth.handlers.kimi_code import KimiCodeHandler
    assert KimiCodeHandler is not None


def test_kimi_code_handler_has_name():
    """KimiCodeHandler should have name property."""
    from kabot.auth.handlers.kimi_code import KimiCodeHandler
    handler = KimiCodeHandler()
    assert handler.name == "Kimi Code (Subscription)"


@patch('kabot.auth.handlers.kimi_code.secure_input')
@patch('kabot.auth.handlers.kimi_code.os.environ.get')
def test_authenticate_uses_code_api_base(mock_env, mock_input):
    """authenticate() should use Kimi Code specific API base."""
    mock_env.return_value = None
    mock_input.return_value = "kimi-code-key-123"

    from kabot.auth.handlers.kimi_code import KimiCodeHandler
    handler = KimiCodeHandler()
    result = handler.authenticate()

    # Kimi Code uses different API base for coding features
    assert result["providers"]["kimi"]["api_base"] == "https://api.moonshot.cn/v1"
    assert result["providers"]["kimi"]["subscription_type"] == "kimi_code"
```

**Step 2: Create handler**

Create `kabot/auth/handlers/kimi_code.py`:

```python
"""Kimi Code subscription authentication handler."""

from typing import Dict, Any
import os
from rich.prompt import Prompt
from rich.console import Console
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

console = Console()


class KimiCodeHandler(AuthHandler):
    """Handler for Kimi Code subscription authentication."""

    API_BASE = "https://api.moonshot.cn/v1"

    @property
    def name(self) -> str:
        return "Kimi Code (Subscription)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute Kimi Code subscription authentication flow."""
        console.print("\n[bold]Kimi Code Subscription Setup[/bold]")
        console.print("This requires a Kimi Code subscription plan.")
        console.print("Get your subscription key from: https://platform.moonshot.cn/console/api-keys\n")

        # Check env var first
        env_key = os.environ.get("KIMI_CODE_API_KEY")
        if env_key:
            use_env = Prompt.ask(
                f"Found KIMI_CODE_API_KEY in environment ({env_key[:8]}...). Use this?",
                choices=["y", "n"],
                default="y"
            )
            if use_env == "y":
                return {
                    "providers": {
                        "kimi": {
                            "api_key": env_key,
                            "api_base": self.API_BASE,
                            "subscription_type": "kimi_code"
                        }
                    }
                }

        # Manual input
        api_key = secure_input("Enter Kimi Code API Key")

        if not api_key:
            return None

        return {
            "providers": {
                "kimi": {
                    "api_key": api_key,
                    "api_base": self.API_BASE,
                    "subscription_type": "kimi_code"
                }
            }
        }
```

**Step 3: Run tests and commit**

```bash
pytest tests/auth/handlers/test_kimi_code.py -v
git add kabot/auth/handlers/kimi_code.py tests/auth/handlers/test_kimi_code.py
git commit -m "feat: add KimiCodeHandler for Kimi Code subscription auth

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 9: Create MiniMax Key Handler

**Files:**
- Create: `kabot/auth/handlers/minimax_key.py`
- Create: `tests/auth/handlers/test_minimax_key.py`

**Step 1: Write failing test**

Create `tests/auth/handlers/test_minimax_key.py`:

```python
"""Tests for MiniMax API Key handler."""
import pytest
from unittest.mock import patch


def test_minimax_key_handler_exists():
    """MiniMaxKeyHandler class should exist."""
    from kabot.auth.handlers.minimax_key import MiniMaxKeyHandler
    assert MiniMaxKeyHandler is not None


def test_minimax_key_handler_has_name():
    """MiniMaxKeyHandler should have name property."""
    from kabot.auth.handlers.minimax_key import MiniMaxKeyHandler
    handler = MiniMaxKeyHandler()
    assert handler.name == "MiniMax (API Key)"


@patch('kabot.auth.handlers.minimax_key.secure_input')
@patch('kabot.auth.handlers.minimax_key.os.environ.get')
def test_authenticate_returns_minimax_provider(mock_env, mock_input):
    """authenticate() should return minimax provider structure."""
    mock_env.return_value = None
    mock_input.return_value = "minimax-test-key-123"

    from kabot.auth.handlers.minimax_key import MiniMaxKeyHandler
    handler = MiniMaxKeyHandler()
    result = handler.authenticate()

    assert result == {
        "providers": {
            "minimax": {
                "api_key": "minimax-test-key-123",
                "api_base": "https://api.minimax.chat/v1"
            }
        }
    }
```

**Step 2: Create handler**

Create `kabot/auth/handlers/minimax_key.py`:

```python
"""MiniMax API Key authentication handler."""

from typing import Dict, Any
import os
from rich.prompt import Prompt
from rich.console import Console
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

console = Console()


class MiniMaxKeyHandler(AuthHandler):
    """Handler for MiniMax general API Key authentication (pay-as-you-go)."""

    API_BASE = "https://api.minimax.chat/v1"

    @property
    def name(self) -> str:
        return "MiniMax (API Key)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute API key authentication flow."""
        console.print("\n[bold]MiniMax API Key Setup[/bold]")
        console.print("Get your API key from: https://platform.minimax.io/dashboard\n")

        # Check env var first
        env_key = os.environ.get("MINIMAX_API_KEY")
        if env_key:
            use_env = Prompt.ask(
                f"Found MINIMAX_API_KEY in environment ({env_key[:8]}...). Use this?",
                choices=["y", "n"],
                default="y"
            )
            if use_env == "y":
                return {
                    "providers": {
                        "minimax": {
                            "api_key": env_key,
                            "api_base": self.API_BASE
                        }
                    }
                }

        # Manual input
        api_key = secure_input("Enter MiniMax API Key")

        if not api_key:
            return None

        return {
            "providers": {
                "minimax": {
                    "api_key": api_key,
                    "api_base": self.API_BASE
                }
            }
        }
```

**Step 3: Run tests and commit**

```bash
pytest tests/auth/handlers/test_minimax_key.py -v
git add kabot/auth/handlers/minimax_key.py tests/auth/handlers/test_minimax_key.py
git commit -m "feat: add MiniMaxKeyHandler for MiniMax API key auth

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 10: Create MiniMax Coding Handler

**Files:**
- Create: `kabot/auth/handlers/minimax_coding.py`
- Create: `tests/auth/handlers/test_minimax_coding.py`

**Step 1: Write failing test**

Create `tests/auth/handlers/test_minimax_coding.py`:

```python
"""Tests for MiniMax Coding Plan handler."""
import pytest
from unittest.mock import patch


def test_minimax_coding_handler_exists():
    """MiniMaxCodingHandler class should exist."""
    from kabot.auth.handlers.minimax_coding import MiniMaxCodingHandler
    assert MiniMaxCodingHandler is not None


def test_minimax_coding_handler_has_name():
    """MiniMaxCodingHandler should have name property."""
    from kabot.auth.handlers.minimax_coding import MiniMaxCodingHandler
    handler = MiniMaxCodingHandler()
    assert handler.name == "MiniMax Coding Plan (Subscription)"


@patch('kabot.auth.handlers.minimax_coding.secure_input')
@patch('kabot.auth.handlers.minimax_coding.os.environ.get')
def test_authenticate_includes_subscription_type(mock_env, mock_input):
    """authenticate() should include subscription_type field."""
    mock_env.return_value = None
    mock_input.return_value = "minimax-coding-key-123"

    from kabot.auth.handlers.minimax_coding import MiniMaxCodingHandler
    handler = MiniMaxCodingHandler()
    result = handler.authenticate()

    assert result["providers"]["minimax"]["subscription_type"] == "coding_plan"
```

**Step 2: Create handler**

Create `kabot/auth/handlers/minimax_coding.py`:

```python
"""MiniMax Coding Plan subscription authentication handler."""

from typing import Dict, Any
import os
from rich.prompt import Prompt
from rich.console import Console
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

console = Console()


class MiniMaxCodingHandler(AuthHandler):
    """Handler for MiniMax Coding Plan subscription authentication."""

    API_BASE = "https://api.minimax.chat/v1"

    @property
    def name(self) -> str:
        return "MiniMax Coding Plan (Subscription)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute Coding Plan subscription authentication flow."""
        console.print("\n[bold]MiniMax Coding Plan Setup[/bold]")
        console.print("This requires a MiniMax Coding Plan subscription (unlimited usage).")
        console.print("Get your Coding Plan key from: https://platform.minimax.io/dashboard\n")

        # Check env var first
        env_key = os.environ.get("MINIMAX_CODING_API_KEY")
        if env_key:
            use_env = Prompt.ask(
                f"Found MINIMAX_CODING_API_KEY in environment ({env_key[:8]}...). Use this?",
                choices=["y", "n"],
                default="y"
            )
            if use_env == "y":
                return {
                    "providers": {
                        "minimax": {
                            "api_key": env_key,
                            "api_base": self.API_BASE,
                            "subscription_type": "coding_plan"
                        }
                    }
                }

        # Manual input
        api_key = secure_input("Enter MiniMax Coding Plan API Key")

        if not api_key:
            return None

        return {
            "providers": {
                "minimax": {
                    "api_key": api_key,
                    "api_base": self.API_BASE,
                    "subscription_type": "coding_plan"
                }
            }
        }
```

**Step 3: Run tests and commit**

```bash
pytest tests/auth/handlers/test_minimax_coding.py -v
git add kabot/auth/handlers/minimax_coding.py tests/auth/handlers/test_minimax_coding.py
git commit -m "feat: add MiniMaxCodingHandler for Coding Plan subscription auth

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 11: Refactor AuthManager

**Files:**
- Modify: `kabot/auth/manager.py`
- Create: `tests/auth/test_manager.py`

**Step 1: Write failing tests**

Create `tests/auth/test_manager.py`:

```python
"""Tests for AuthManager with multi-method support."""
import pytest
from unittest.mock import patch, MagicMock


def test_auth_manager_exists():
    """AuthManager class should exist."""
    from kabot.auth.manager import AuthManager
    assert AuthManager is not None


def test_list_providers_returns_list():
    """list_providers should return list of provider IDs."""
    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    providers = manager.list_providers()
    assert isinstance(providers, list)
    assert "openai" in providers
    assert "anthropic" in providers


def test_load_handler_dynamically():
    """_load_handler should load handler class from string path."""
    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    handler = manager._load_handler("openai", "api_key")
    assert handler is not None
    assert handler.name == "OpenAI (API Key)"


def test_login_with_invalid_provider():
    """login with invalid provider should return False."""
    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    result = manager.login("invalid_provider")
    assert result is False


def test_login_with_invalid_method():
    """login with invalid method should return False."""
    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    result = manager.login("openai", method_id="invalid_method")
    assert result is False


@patch('kabot.auth.manager.AuthManager._load_handler')
@patch('kabot.auth.manager.AuthManager._save_credentials')
def test_login_with_method_specified(mock_save, mock_load):
    """login with method_id should skip menu and use specified method."""
    mock_handler = MagicMock()
    mock_handler.authenticate.return_value = {"providers": {"openai": {"api_key": "test"}}}
    mock_load.return_value = mock_handler
    mock_save.return_value = True

    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    result = manager.login("openai", method_id="api_key")

    mock_load.assert_called_once_with("openai", "api_key")
    assert result is True


@patch('kabot.auth.manager.AuthManager._load_handler')
def test_login_handles_keyboard_interrupt(mock_load):
    """login should handle KeyboardInterrupt gracefully."""
    mock_handler = MagicMock()
    mock_handler.authenticate.side_effect = KeyboardInterrupt()
    mock_load.return_value = mock_handler

    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    result = manager.login("openai", method_id="api_key")

    assert result is False
```

**Step 2: Run tests to verify some fail**

```bash
pytest tests/auth/test_manager.py -v
```

**Step 3: Update AuthManager**

Update `kabot/auth/manager.py`:

```python
"""Authentication manager with multi-method support."""

from typing import List, Optional, Dict, Any
import importlib
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from kabot.config.loader import load_config, save_config
from kabot.auth.menu import AUTH_PROVIDERS

console = Console()


class AuthManager:
    """Manages authentication for multiple providers with multiple methods."""

    def list_providers(self) -> List[str]:
        """Return a list of supported provider IDs."""
        return list(AUTH_PROVIDERS.keys())

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
            console.print(f"[bold red]Error:[/bold red] Provider '{provider_id}' not found.")
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
            console.print(f"[bold red]Error:[/bold red] Method '{method_id}' not found for {provider_id}.")
            return False

        # 4. Load handler dynamically
        try:
            handler = self._load_handler(provider_id, method_id)
        except Exception as e:
            console.print(f"[bold red]Error loading handler:[/bold red] {e}")
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
            console.print(f"\n[bold red]Authentication failed:[/bold red] {e}")
            return False

        if not auth_data:
            console.print("[yellow]No credentials provided.[/yellow]")
            return False

        # 6. Validate auth data
        if not self._validate_auth_data(auth_data):
            console.print("[bold red]Error:[/bold red] Invalid authentication data format.")
            return False

        # 7. Save credentials
        return self._save_credentials(auth_data)

    def _load_handler(self, provider_id: str, method_id: str):
        """Dynamically load handler class from string path."""
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
        try:
            selection = Prompt.ask("Select authentication method", choices=choices)
            selected_method_id = method_list[int(selection) - 1][0]
            return selected_method_id
        except (KeyboardInterrupt, EOFError):
            return None

    def _validate_auth_data(self, auth_data: Dict[str, Any]) -> bool:
        """Validate auth data structure."""
        if not isinstance(auth_data, dict):
            return False

        if "providers" not in auth_data:
            return False

        # Check at least one provider has credentials
        for provider_data in auth_data["providers"].values():
            if any(key in provider_data for key in ["api_key", "oauth_token", "api_base"]):
                return True

        return False

    def _save_credentials(self, auth_data: Dict[str, Any]) -> bool:
        """Save credentials to config."""
        try:
            current_config = load_config()

            if "providers" in auth_data:
                for prov_name, prov_data in auth_data["providers"].items():
                    # Get or create provider config
                    provider_config_obj = getattr(current_config.providers, prov_name, None)

                    if provider_config_obj is None:
                        console.print(f"[yellow]Warning: Provider '{prov_name}' not in config schema[/yellow]")
                        continue

                    # Update fields
                    for key, value in prov_data.items():
                        if hasattr(provider_config_obj, key):
                            setattr(provider_config_obj, key, value)

            save_config(current_config)
            return True

        except Exception as e:
            console.print(f"[bold red]Error saving config:[/bold red] {e}")
            return False

    def get_status(self):
        """Print the current status of configured providers."""
        config = load_config()

        table = Table(title="Auth Status")
        table.add_column("Provider", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Key Preview", style="dim")

        # Provider ID to config field mapping
        config_mapping = {
            "openai": "openai",
            "anthropic": "anthropic",
            "google": "gemini",
            "ollama": "vllm",
            "kimi": "kimi",
            "minimax": "minimax"
        }

        for pid, meta in AUTH_PROVIDERS.items():
            config_field = config_mapping.get(pid, pid)
            provider_cfg = getattr(config.providers, config_field, None)

            status = "[red]Not Configured[/red]"
            preview = ""

            if provider_cfg:
                api_key = getattr(provider_cfg, "api_key", None)
                if api_key:
                    status = "[green]Configured[/green]"
                    if len(api_key) > 8:
                        preview = f"{api_key[:4]}...{api_key[-4:]}"
                    else:
                        preview = "***"

            table.add_row(meta["name"], status, preview)

        console.print(table)
```

**Step 4: Run tests**

```bash
pytest tests/auth/test_manager.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add kabot/auth/manager.py tests/auth/test_manager.py
git commit -m "refactor: update AuthManager for multi-method authentication

- Add _load_handler for dynamic handler loading
- Add _prompt_method_selection for method menu
- Add _validate_auth_data for data validation
- Update login() to support method_id parameter
- Update get_status() with new provider mapping

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---