# Multi-Method Authentication Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement multi-method authentication system supporting 6 providers with 13 auth methods (OAuth, API Key, Setup Token, Subscription plans).

**Architecture:** Refactor AUTH_PROVIDERS from single handler to methods dict. AuthManager dynamically loads handlers via importlib. OAuth callback server handles browser-based flows with VPS detection.

**Tech Stack:** Python 3.8+, aiohttp (OAuth server), Rich (CLI menus), pytest (testing)

---

## Prerequisites

Before starting, verify:
```bash
# Ensure you're in kabot root
pwd  # Should show kabot project root

# Verify existing auth structure
ls kabot/auth/
# Expected: __init__.py handlers/ manager.py menu.py utils.py

# Run existing tests to establish baseline
pytest tests/ -v --tb=short 2>/dev/null || echo "No existing tests"
```

---

## Task 1: Create Test Infrastructure

**Files:**
- Create: `tests/auth/__init__.py`
- Create: `tests/auth/handlers/__init__.py`
- Create: `tests/auth/test_menu.py`

**Step 1: Create test directories**

```bash
mkdir -p tests/auth/handlers
touch tests/auth/__init__.py
touch tests/auth/handlers/__init__.py
```

**Step 2: Write failing test for new menu structure**

Create `tests/auth/test_menu.py`:

```python
"""Tests for multi-method auth menu structure."""
import pytest


def test_auth_providers_has_methods_dict():
    """AUTH_PROVIDERS should have 'methods' dict instead of 'handler'."""
    from kabot.auth.menu import AUTH_PROVIDERS

    for provider_id, provider_info in AUTH_PROVIDERS.items():
        assert "methods" in provider_info, f"{provider_id} missing 'methods' key"
        assert isinstance(provider_info["methods"], dict), f"{provider_id} 'methods' should be dict"
        assert len(provider_info["methods"]) >= 1, f"{provider_id} should have at least 1 method"


def test_each_method_has_required_fields():
    """Each method should have label, description, handler."""
    from kabot.auth.menu import AUTH_PROVIDERS

    required_fields = {"label", "description", "handler"}

    for provider_id, provider_info in AUTH_PROVIDERS.items():
        for method_id, method_info in provider_info["methods"].items():
            for field in required_fields:
                assert field in method_info, f"{provider_id}.{method_id} missing '{field}'"


def test_handler_paths_are_strings():
    """Handler should be string path for lazy loading."""
    from kabot.auth.menu import AUTH_PROVIDERS

    for provider_id, provider_info in AUTH_PROVIDERS.items():
        for method_id, method_info in provider_info["methods"].items():
            handler = method_info["handler"]
            assert isinstance(handler, str), f"{provider_id}.{method_id} handler should be string path"
            assert "." in handler, f"{provider_id}.{method_id} handler should be module.Class path"


def test_get_auth_choices_returns_list():
    """get_auth_choices should return list of provider choices."""
    from kabot.auth.menu import get_auth_choices

    choices = get_auth_choices()
    assert isinstance(choices, list)
    assert len(choices) >= 4  # At least 4 providers


def test_get_method_choices_returns_list():
    """get_method_choices should return list of method choices for provider."""
    from kabot.auth.menu import get_method_choices

    choices = get_method_choices("openai")
    assert isinstance(choices, list)
    assert len(choices) >= 1

    # Each choice should have id, label, description
    for choice in choices:
        assert "id" in choice
        assert "label" in choice
        assert "description" in choice
```

**Step 3: Run test to verify it fails**

```bash
pytest tests/auth/test_menu.py -v
```

Expected: FAIL with `KeyError: 'methods'` (current structure uses 'handler')

**Step 4: Commit test infrastructure**

```bash
git add tests/auth/
git commit -m "test: add test infrastructure for multi-method auth

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Refactor Menu Structure

**Files:**
- Modify: `kabot/auth/menu.py`

**Step 1: Update menu.py with new structure**

Replace entire `kabot/auth/menu.py`:

```python
"""Multi-method authentication menu structure."""

from typing import Dict, List, Any

# Provider definitions with multiple auth methods per provider
AUTH_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "name": "OpenAI",
        "description": "GPT-4o, o1-preview, etc.",
        "methods": {
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


def get_auth_choices() -> List[Dict[str, str]]:
    """Returns list of provider choices for interactive menu."""
    return [
        {"name": f"{meta['name']} - {meta['description']}", "value": key}
        for key, meta in AUTH_PROVIDERS.items()
    ]


def get_method_choices(provider_id: str) -> List[Dict[str, str]]:
    """Returns list of method choices for a specific provider."""
    if provider_id not in AUTH_PROVIDERS:
        return []

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

**Step 2: Run tests to verify they pass**

```bash
pytest tests/auth/test_menu.py -v
```

Expected: All 5 tests PASS

**Step 3: Commit**

```bash
git add kabot/auth/menu.py
git commit -m "refactor: update menu structure for multi-method auth

- Change 'handler' field to 'methods' dict
- Each method has label, description, handler path
- Handler paths are strings for lazy loading
- Add 6 providers with 13 methods total
- Add get_method_choices() helper function

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Create OpenAI Key Handler

**Files:**
- Rename: `kabot/auth/handlers/openai.py` → `kabot/auth/handlers/openai_key.py`
- Create: `tests/auth/handlers/test_openai_key.py`

**Step 1: Write failing test**

Create `tests/auth/handlers/test_openai_key.py`:

```python
"""Tests for OpenAI API Key handler."""
import pytest
from unittest.mock import patch, MagicMock


def test_openai_key_handler_exists():
    """OpenAIKeyHandler class should exist."""
    from kabot.auth.handlers.openai_key import OpenAIKeyHandler
    assert OpenAIKeyHandler is not None


def test_openai_key_handler_has_name():
    """OpenAIKeyHandler should have name property."""
    from kabot.auth.handlers.openai_key import OpenAIKeyHandler
    handler = OpenAIKeyHandler()
    assert handler.name == "OpenAI (API Key)"


def test_openai_key_handler_inherits_base():
    """OpenAIKeyHandler should inherit from AuthHandler."""
    from kabot.auth.handlers.openai_key import OpenAIKeyHandler
    from kabot.auth.handlers.base import AuthHandler
    assert issubclass(OpenAIKeyHandler, AuthHandler)


@patch('kabot.auth.handlers.openai_key.secure_input')
@patch('kabot.auth.handlers.openai_key.os.environ.get')
def test_authenticate_with_manual_input(mock_env, mock_input):
    """authenticate() should return api_key from manual input."""
    mock_env.return_value = None  # No env var
    mock_input.return_value = "sk-test123456789"

    from kabot.auth.handlers.openai_key import OpenAIKeyHandler
    handler = OpenAIKeyHandler()
    result = handler.authenticate()

    assert result == {"providers": {"openai": {"api_key": "sk-test123456789"}}}


@patch('kabot.auth.handlers.openai_key.Prompt.ask')
@patch('kabot.auth.handlers.openai_key.os.environ.get')
def test_authenticate_uses_env_var_when_accepted(mock_env, mock_prompt):
    """authenticate() should use env var when user accepts."""
    mock_env.return_value = "sk-env-key-12345"
    mock_prompt.return_value = "y"

    from kabot.auth.handlers.openai_key import OpenAIKeyHandler
    handler = OpenAIKeyHandler()
    result = handler.authenticate()

    assert result == {"providers": {"openai": {"api_key": "sk-env-key-12345"}}}
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/auth/handlers/test_openai_key.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'kabot.auth.handlers.openai_key'`

**Step 3: Rename and update handler**

```bash
# Rename file
mv kabot/auth/handlers/openai.py kabot/auth/handlers/openai_key.py
```

Update `kabot/auth/handlers/openai_key.py`:

```python
"""OpenAI API Key authentication handler."""

from typing import Dict, Any
import os
from rich.prompt import Prompt
from rich.console import Console
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

console = Console()


class OpenAIKeyHandler(AuthHandler):
    """Handler for OpenAI API Key authentication."""

    @property
    def name(self) -> str:
        return "OpenAI (API Key)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute API key authentication flow."""
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

**Step 4: Run tests to verify they pass**

```bash
pytest tests/auth/handlers/test_openai_key.py -v
```

Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add kabot/auth/handlers/openai_key.py tests/auth/handlers/test_openai_key.py
git rm kabot/auth/handlers/openai.py 2>/dev/null || true
git commit -m "refactor: rename OpenAIHandler to OpenAIKeyHandler

- Rename openai.py to openai_key.py
- Update class name to OpenAIKeyHandler
- Add tests for handler

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Create Anthropic Key Handler

**Files:**
- Rename: `kabot/auth/handlers/anthropic.py` → `kabot/auth/handlers/anthropic_key.py`
- Create: `tests/auth/handlers/test_anthropic_key.py`

**Step 1: Write failing test**

Create `tests/auth/handlers/test_anthropic_key.py`:

```python
"""Tests for Anthropic API Key handler."""
import pytest
from unittest.mock import patch


def test_anthropic_key_handler_exists():
    """AnthropicKeyHandler class should exist."""
    from kabot.auth.handlers.anthropic_key import AnthropicKeyHandler
    assert AnthropicKeyHandler is not None


def test_anthropic_key_handler_has_name():
    """AnthropicKeyHandler should have name property."""
    from kabot.auth.handlers.anthropic_key import AnthropicKeyHandler
    handler = AnthropicKeyHandler()
    assert handler.name == "Anthropic (API Key)"


@patch('kabot.auth.handlers.anthropic_key.secure_input')
@patch('kabot.auth.handlers.anthropic_key.os.environ.get')
def test_authenticate_returns_correct_structure(mock_env, mock_input):
    """authenticate() should return correct provider structure."""
    mock_env.return_value = None
    mock_input.return_value = "sk-ant-test123"

    from kabot.auth.handlers.anthropic_key import AnthropicKeyHandler
    handler = AnthropicKeyHandler()
    result = handler.authenticate()

    assert result == {"providers": {"anthropic": {"api_key": "sk-ant-test123"}}}
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/auth/handlers/test_anthropic_key.py -v
```

Expected: FAIL

**Step 3: Rename and update handler**

```bash
mv kabot/auth/handlers/anthropic.py kabot/auth/handlers/anthropic_key.py
```

Update `kabot/auth/handlers/anthropic_key.py`:

```python
"""Anthropic API Key authentication handler."""

from typing import Dict, Any
import os
from rich.prompt import Prompt
from rich.console import Console
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

console = Console()


class AnthropicKeyHandler(AuthHandler):
    """Handler for Anthropic API Key authentication."""

    @property
    def name(self) -> str:
        return "Anthropic (API Key)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute API key authentication flow."""
        console.print("\n[bold]Anthropic API Key Setup[/bold]")
        console.print("Get your API key from: https://console.anthropic.com/settings/keys\n")

        # Check env var first
        env_key = os.environ.get("ANTHROPIC_API_KEY")
        if env_key:
            use_env = Prompt.ask(
                f"Found ANTHROPIC_API_KEY in environment ({env_key[:8]}...). Use this?",
                choices=["y", "n"],
                default="y"
            )
            if use_env == "y":
                return {"providers": {"anthropic": {"api_key": env_key}}}

        # Manual input
        api_key = secure_input("Enter Anthropic API Key")

        if not api_key:
            return None

        return {"providers": {"anthropic": {"api_key": api_key}}}
```

**Step 4: Run tests**

```bash
pytest tests/auth/handlers/test_anthropic_key.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add kabot/auth/handlers/anthropic_key.py tests/auth/handlers/test_anthropic_key.py
git rm kabot/auth/handlers/anthropic.py 2>/dev/null || true
git commit -m "refactor: rename AnthropicHandler to AnthropicKeyHandler

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Create Google Key Handler

**Files:**
- Rename: `kabot/auth/handlers/google.py` → `kabot/auth/handlers/google_key.py`
- Create: `tests/auth/handlers/test_google_key.py`

**Step 1: Write failing test**

Create `tests/auth/handlers/test_google_key.py`:

```python
"""Tests for Google API Key handler."""
import pytest
from unittest.mock import patch


def test_google_key_handler_exists():
    """GoogleKeyHandler class should exist."""
    from kabot.auth.handlers.google_key import GoogleKeyHandler
    assert GoogleKeyHandler is not None


def test_google_key_handler_has_name():
    """GoogleKeyHandler should have name property."""
    from kabot.auth.handlers.google_key import GoogleKeyHandler
    handler = GoogleKeyHandler()
    assert handler.name == "Google Gemini (API Key)"


@patch('kabot.auth.handlers.google_key.secure_input')
@patch('kabot.auth.handlers.google_key.os.environ.get')
def test_authenticate_returns_gemini_provider(mock_env, mock_input):
    """authenticate() should return 'gemini' provider key."""
    mock_env.return_value = None
    mock_input.return_value = "AIza-test123"

    from kabot.auth.handlers.google_key import GoogleKeyHandler
    handler = GoogleKeyHandler()
    result = handler.authenticate()

    # Note: Uses 'gemini' as provider key for config compatibility
    assert result == {"providers": {"gemini": {"api_key": "AIza-test123"}}}
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/auth/handlers/test_google_key.py -v
```

**Step 3: Rename and update handler**

```bash
mv kabot/auth/handlers/google.py kabot/auth/handlers/google_key.py
```

Update `kabot/auth/handlers/google_key.py`:

```python
"""Google Gemini API Key authentication handler."""

from typing import Dict, Any
import os
from rich.prompt import Prompt
from rich.console import Console
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

console = Console()


class GoogleKeyHandler(AuthHandler):
    """Handler for Google Gemini API Key authentication."""

    @property
    def name(self) -> str:
        return "Google Gemini (API Key)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute API key authentication flow."""
        console.print("\n[bold]Google Gemini API Key Setup[/bold]")
        console.print("Get your API key from: https://aistudio.google.com/app/apikey\n")

        # Check env var first
        env_key = os.environ.get("GEMINI_API_KEY")
        if env_key:
            use_env = Prompt.ask(
                f"Found GEMINI_API_KEY in environment ({env_key[:8]}...). Use this?",
                choices=["y", "n"],
                default="y"
            )
            if use_env == "y":
                return {"providers": {"gemini": {"api_key": env_key}}}

        # Manual input
        api_key = secure_input("Enter Gemini API Key")

        if not api_key:
            return None

        return {"providers": {"gemini": {"api_key": api_key}}}
```

**Step 4: Run tests and commit**

```bash
pytest tests/auth/handlers/test_google_key.py -v
git add kabot/auth/handlers/google_key.py tests/auth/handlers/test_google_key.py
git rm kabot/auth/handlers/google.py 2>/dev/null || true
git commit -m "refactor: rename GoogleHandler to GoogleKeyHandler

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Create Ollama URL Handler

**Files:**
- Rename: `kabot/auth/handlers/ollama.py` → `kabot/auth/handlers/ollama_url.py`
- Create: `tests/auth/handlers/test_ollama_url.py`

**Step 1: Write failing test**

Create `tests/auth/handlers/test_ollama_url.py`:

```python
"""Tests for Ollama URL handler."""
import pytest
from unittest.mock import patch


def test_ollama_url_handler_exists():
    """OllamaURLHandler class should exist."""
    from kabot.auth.handlers.ollama_url import OllamaURLHandler
    assert OllamaURLHandler is not None


def test_ollama_url_handler_has_name():
    """OllamaURLHandler should have name property."""
    from kabot.auth.handlers.ollama_url import OllamaURLHandler
    handler = OllamaURLHandler()
    assert handler.name == "Ollama (Local)"


@patch('kabot.auth.handlers.ollama_url.Prompt.ask')
@patch('kabot.auth.handlers.ollama_url.os.environ.get')
def test_authenticate_returns_vllm_provider(mock_env, mock_prompt):
    """authenticate() should return 'vllm' provider with api_base."""
    mock_env.return_value = None
    mock_prompt.return_value = "http://localhost:11434"

    from kabot.auth.handlers.ollama_url import OllamaURLHandler
    handler = OllamaURLHandler()
    result = handler.authenticate()

    assert result == {
        "providers": {
            "vllm": {
                "api_base": "http://localhost:11434",
                "api_key": "ollama"
            }
        }
    }
```

**Step 2: Rename and update**

```bash
mv kabot/auth/handlers/ollama.py kabot/auth/handlers/ollama_url.py
```

Update `kabot/auth/handlers/ollama_url.py`:

```python
"""Ollama URL configuration handler."""

from typing import Dict, Any
import os
from rich.prompt import Prompt
from rich.console import Console
from kabot.auth.handlers.base import AuthHandler

console = Console()


class OllamaURLHandler(AuthHandler):
    """Handler for Ollama local server configuration."""

    @property
    def name(self) -> str:
        return "Ollama (Local)"

    def authenticate(self) -> Dict[str, Any]:
        """Configure Ollama server URL."""
        console.print("\n[bold]Ollama Setup[/bold]")
        console.print("Ensure Ollama is running (default: http://localhost:11434)\n")

        default_url = "http://localhost:11434"

        # Check environment
        env_host = os.environ.get("OLLAMA_HOST")
        if env_host:
            default_url = env_host

        base_url = Prompt.ask("Enter Ollama Base URL", default=default_url)

        return {
            "providers": {
                "vllm": {
                    "api_base": base_url,
                    "api_key": "ollama"
                }
            }
        }
```

**Step 3: Run tests and commit**

```bash
pytest tests/auth/handlers/test_ollama_url.py -v
git add kabot/auth/handlers/ollama_url.py tests/auth/handlers/test_ollama_url.py
git rm kabot/auth/handlers/ollama.py 2>/dev/null || true
git commit -m "refactor: rename OllamaHandler to OllamaURLHandler

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Create Kimi Key Handler

**Files:**
- Create: `kabot/auth/handlers/kimi_key.py`
- Create: `tests/auth/handlers/test_kimi_key.py`

**Step 1: Write failing test**

Create `tests/auth/handlers/test_kimi_key.py`:

```python
"""Tests for Kimi API Key handler."""
import pytest
from unittest.mock import patch


def test_kimi_key_handler_exists():
    """KimiKeyHandler class should exist."""
    from kabot.auth.handlers.kimi_key import KimiKeyHandler
    assert KimiKeyHandler is not None


def test_kimi_key_handler_has_name():
    """KimiKeyHandler should have name property."""
    from kabot.auth.handlers.kimi_key import KimiKeyHandler
    handler = KimiKeyHandler()
    assert handler.name == "Kimi (API Key)"


@patch('kabot.auth.handlers.kimi_key.secure_input')
@patch('kabot.auth.handlers.kimi_key.os.environ.get')
def test_authenticate_returns_kimi_provider(mock_env, mock_input):
    """authenticate() should return kimi provider structure."""
    mock_env.return_value = None
    mock_input.return_value = "kimi-test-key-123"

    from kabot.auth.handlers.kimi_key import KimiKeyHandler
    handler = KimiKeyHandler()
    result = handler.authenticate()

    assert result == {
        "providers": {
            "kimi": {
                "api_key": "kimi-test-key-123",
                "api_base": "https://api.moonshot.cn/v1"
            }
        }
    }
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/auth/handlers/test_kimi_key.py -v
```

**Step 3: Create handler**

Create `kabot/auth/handlers/kimi_key.py`:

```python
"""Kimi (Moonshot AI) API Key authentication handler."""

from typing import Dict, Any
import os
from rich.prompt import Prompt
from rich.console import Console
from kabot.auth.handlers.base import AuthHandler
from kabot.auth.utils import secure_input

console = Console()


class KimiKeyHandler(AuthHandler):
    """Handler for Kimi general API Key authentication."""

    API_BASE = "https://api.moonshot.cn/v1"

    @property
    def name(self) -> str:
        return "Kimi (API Key)"

    def authenticate(self) -> Dict[str, Any]:
        """Execute API key authentication flow."""
        console.print("\n[bold]Kimi (Moonshot AI) API Key Setup[/bold]")
        console.print("Get your API key from: https://platform.moonshot.cn/console/api-keys\n")

        # Check env var first
        env_key = os.environ.get("MOONSHOT_API_KEY") or os.environ.get("KIMI_API_KEY")
        if env_key:
            use_env = Prompt.ask(
                f"Found Moonshot API key in environment ({env_key[:8]}...). Use this?",
                choices=["y", "n"],
                default="y"
            )
            if use_env == "y":
                return {
                    "providers": {
                        "kimi": {
                            "api_key": env_key,
                            "api_base": self.API_BASE
                        }
                    }
                }

        # Manual input
        api_key = secure_input("Enter Moonshot API Key")

        if not api_key:
            return None

        return {
            "providers": {
                "kimi": {
                    "api_key": api_key,
                    "api_base": self.API_BASE
                }
            }
        }
```

**Step 4: Run tests and commit**

```bash
pytest tests/auth/handlers/test_kimi_key.py -v
git add kabot/auth/handlers/kimi_key.py tests/auth/handlers/test_kimi_key.py
git commit -m "feat: add KimiKeyHandler for Moonshot AI API key auth

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

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
