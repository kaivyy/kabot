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