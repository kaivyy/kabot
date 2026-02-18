# Setup Wizard UX Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Kabot setup wizard beginner-friendly with alias-first model selection, real-time validation, and clear guidance

**Architecture:** Add model status tracking, alias resolution, and smart validation to existing setup wizard. Progressive disclosure: aliases → browser → manual entry.

**Tech Stack:** Python 3.11+, questionary, rich, existing Kabot infrastructure

---

## Phase 1: Core Improvements (Priority Tasks)

### Task 1: Create Model Status Database

**Files:**
- Create: `kabot/providers/model_status.py`
- Test: `tests/providers/test_model_status.py`

**Step 1: Write failing test**

```python
# tests/providers/test_model_status.py
def test_get_model_status_working():
    from kabot.providers.model_status import get_model_status
    assert get_model_status("openai/gpt-4o") == "working"

def test_get_model_status_catalog():
    from kabot.providers.model_status import get_model_status
    assert get_model_status("openai/gpt-5.1-codex") == "catalog"

def test_get_model_status_unsupported():
    from kabot.providers.model_status import get_model_status
    assert get_model_status("openai-codex/gpt-5.3-codex") == "unsupported"
```

**Step 2: Run test**

Run: `pytest tests/providers/test_model_status.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement model status database**

```python
# kabot/providers/model_status.py
"""Model status tracking for setup wizard."""

WORKING_MODELS = {
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "openai/o1-preview",
    "openai/o1-mini",
    "anthropic/claude-3-5-sonnet-20241022",
    "anthropic/claude-3-5-haiku-20241022",
    "anthropic/claude-3-opus-20240229",
    "google/gemini-1.5-pro",
    "google/gemini-1.5-flash",
    "groq/llama3-70b-8192",
    "groq/mixtral-8x7b-32768",
}

CATALOG_ONLY = {
    "openai/gpt-5.1-codex",
    "anthropic/claude-opus-4-6",
    "anthropic/claude-sonnet-4-5",
    "google-gemini-cli/gemini-3-pro-preview",
    "moonshot/kimi-k2.5",
    "minimax/MiniMax-M2.1",
}

UNSUPPORTED_PROVIDERS = {
    "openai-codex",
    "kimi-coding",
    "google-gemini-cli",
    "qwen-portal",
}

def get_model_status(model_id: str) -> str:
    """Return 'working', 'catalog', 'unsupported', or 'unknown'."""
    if model_id in WORKING_MODELS:
        return "working"

    provider = model_id.split("/")[0] if "/" in model_id else model_id
    if provider in UNSUPPORTED_PROVIDERS:
        return "unsupported"

    if model_id in CATALOG_ONLY:
        return "catalog"

    return "unknown"

def get_status_indicator(status: str) -> str:
    """Return visual indicator for status."""
    indicators = {
        "working": "✓",
        "catalog": "⚠",
        "unsupported": "✗",
        "unknown": "?",
    }
    return indicators.get(status, "?")
```

**Step 4: Run test**

Run: `pytest tests/providers/test_model_status.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/providers/model_status.py tests/providers/test_model_status.py
git commit -m "feat(providers): add model status tracking database"
```

---

### Task 2: Create Model Validator

**Files:**
- Create: `kabot/cli/model_validator.py`
- Test: `tests/cli/test_model_validator.py`

**Step 1: Write failing tests**

```python
# tests/cli/test_model_validator.py
def test_validate_format_valid():
    from kabot.cli.model_validator import validate_format
    assert validate_format("openai/gpt-4o") == True

def test_validate_format_invalid():
    from kabot.cli.model_validator import validate_format
    assert validate_format("gpt-4o") == False

def test_resolve_alias():
    from kabot.cli.model_validator import resolve_alias
    assert resolve_alias("codex") == "openai/gpt-5.1-codex"
    assert resolve_alias("sonnet") == "anthropic/claude-3-5-sonnet-20241022"
    assert resolve_alias("invalid") is None
```

**Step 2: Run test**

Run: `pytest tests/cli/test_model_validator.py -v`
Expected: FAIL

**Step 3: Implement validator**

```python
# kabot/cli/model_validator.py
"""Model ID validation and alias resolution."""
from typing import Optional
from kabot.providers.registry import ModelRegistry

def validate_format(model_id: str) -> bool:
    """Check if model ID follows provider/model-name format."""
    return "/" in model_id and len(model_id.split("/")) == 2

def resolve_alias(alias: str) -> Optional[str]:
    """Resolve alias to full model ID."""
    registry = ModelRegistry()
    return registry.resolve_alias(alias)

def suggest_alternatives(invalid_input: str) -> list[str]:
    """Suggest valid alternatives for invalid input."""
    registry = ModelRegistry()
    suggestions = []

    # Check if it's close to an alias
    all_aliases = registry.get_all_aliases()
    for alias_name, model_id in all_aliases.items():
        if alias_name in invalid_input.lower() or invalid_input.lower() in alias_name:
            suggestions.append(f"{model_id} (alias: {alias_name})")

    # Check if it's a model name without provider
    if "/" not in invalid_input:
        for model in registry.list_models():
            if invalid_input.lower() in model.id.lower():
                suggestions.append(model.id)

    return suggestions[:3]  # Return top 3
```

**Step 4: Run test**

Run: `pytest tests/cli/test_model_validator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/cli/model_validator.py tests/cli/test_model_validator.py
git commit -m "feat(cli): add model validator with alias resolution"
```

---

### Task 3: Add Popular Aliases to Model Picker

**Files:**
- Modify: `kabot/cli/setup_wizard.py:459-497` (_model_picker method)
- Test: Manual testing (interactive UI)

**Step 1: Read current implementation**

Run: `cat kabot/cli/setup_wizard.py | grep -A 40 "def _model_picker"`

**Step 2: Modify _model_picker to show aliases first**

```python
# kabot/cli/setup_wizard.py:459
def _model_picker(self, provider_id: Optional[str] = None):
    from kabot.cli.model_validator import resolve_alias
    from kabot.providers.model_status import get_model_status, get_status_indicator

    # Popular aliases section
    popular_aliases = [
        ("codex", "OpenAI GPT-5.1 Codex (Advanced Coding)"),
        ("sonnet", "Claude 3.5 Sonnet (Latest, 200K context)"),
        ("gemini", "Google Gemini 1.5 Pro (2M context)"),
        ("gpt4o", "OpenAI GPT-4o (Multi-modal)"),
    ]

    m_choices = [
        questionary.Choice(f"Keep current ({self.config.agents.defaults.model})", value="keep"),
    ]

    # Add popular aliases
    for alias, description in popular_aliases:
        model_id = resolve_alias(alias)
        if model_id:
            status = get_model_status(model_id)
            indicator = get_status_indicator(status)
            m_choices.append(
                questionary.Choice(f"{alias:10} - {description} {indicator}", value=f"alias:{alias}")
            )

    # Add browse and manual options
    m_choices.extend([
        questionary.Choice("Browse All Models (by provider)", value="browse"),
        questionary.Choice("Enter Model ID or Alias Manually", value="manual"),
    ])

    selected = ClackUI.clack_select("Select default model (or use alias)", choices=m_choices)

    if selected == "keep" or selected is None:
        return
    elif selected == "browse":
        self._model_browser()
    elif selected == "manual":
        self._manual_model_entry()
    elif selected.startswith("alias:"):
        alias = selected.split(":")[1]
        model_id = resolve_alias(alias)
        if model_id:
            self._confirm_and_set_model(model_id)
```

**Step 3: Test manually**

Run: `python -m kabot config`
Navigate to Model/Auth section
Expected: See popular aliases at top

**Step 4: Commit**

```bash
git add kabot/cli/setup_wizard.py
git commit -m "feat(cli): add popular aliases to model picker"
```

---

### Task 4: Implement Manual Entry with Hints

**Files:**
- Modify: `kabot/cli/setup_wizard.py` (add _manual_model_entry method)

**Step 1: Add manual entry method**

```python
# kabot/cli/setup_wizard.py (add new method)
def _manual_model_entry(self):
    """Manual model entry with format hints and validation."""
    from kabot.cli.model_validator import validate_format, resolve_alias, suggest_alternatives
    from kabot.providers.model_status import get_model_status, get_status_indicator

    console.print("│")
    console.print("│  [bold]Enter Model ID or Alias[/bold]")
    console.print("│")
    console.print("│  Format: [cyan]provider/model-name[/cyan]  OR  [cyan]alias[/cyan]")
    console.print("│  Examples:")
    console.print("│    • openai/gpt-4o")
    console.print("│    • anthropic/claude-3-5-sonnet-20241022")
    console.print("│    • codex (alias for openai/gpt-5.1-codex)")
    console.print("│")
    console.print("│  Available aliases: codex, sonnet, gemini, gpt4o, o1, kimi")
    console.print("│  Type 'help' to see all aliases")
    console.print("│")

    while True:
        user_input = Prompt.ask("│  Your input").strip()

        if user_input == "help":
            self._show_alias_help()
            continue

        if not user_input:
            console.print("│  [yellow]Cancelled[/yellow]")
            return

        # Try alias resolution first
        model_id = resolve_alias(user_input)
        if model_id:
            console.print(f"│  [green]✓ Resolved alias '{user_input}' to: {model_id}[/green]")
            self._confirm_and_set_model(model_id)
            return

        # Validate format
        if not validate_format(user_input):
            console.print(f"│  [red]❌ Invalid format: \"{user_input}\"[/red]")
            console.print("│  [dim]Expected: provider/model-name[/dim]")
            console.print("│")

            suggestions = suggest_alternatives(user_input)
            if suggestions:
                console.print("│  [yellow]Did you mean one of these?[/yellow]")
                for suggestion in suggestions:
                    console.print(f"│    • {suggestion}")
                console.print("│")
            continue

        # Valid format, check status and confirm
        self._confirm_and_set_model(user_input)
        return

def _confirm_and_set_model(self, model_id: str):
    """Confirm model selection and set if approved."""
    from kabot.providers.model_status import get_model_status, get_status_indicator

    status = get_model_status(model_id)
    indicator = get_status_indicator(status)

    console.print(f"│  {indicator} Model: {model_id}")
    console.print(f"│  Status: {status}")

    if status == "unsupported":
        console.print("│  [red]⚠️  This provider is not supported by LiteLLM[/red]")
        console.print("│  [dim]The model may not work correctly[/dim]")
        if not Confirm.ask("│  Continue anyway?", default=False):
            return
    elif status == "catalog":
        console.print("│  [yellow]⚠️  This model is in catalog but not verified[/yellow]")
        console.print("│  [dim]If you encounter issues, try a working model[/dim]")

    self.config.agents.defaults.model = model_id
    console.print(f"│  [green]✓ Model set to {model_id}[/green]")
```

**Step 2: Test manually**

Run: `python -m kabot config`
Test: Enter invalid format, alias, full ID
Expected: See hints, validation, suggestions

**Step 3: Commit**

```bash
git add kabot/cli/setup_wizard.py
git commit -m "feat(cli): add manual entry with format hints and validation"
```

---

### Task 5: Add Alias Help Screen

**Files:**
- Modify: `kabot/cli/setup_wizard.py` (add _show_alias_help method)

**Step 1: Implement help screen**

```python
# kabot/cli/setup_wizard.py (add new method)
def _show_alias_help(self):
    """Show all available aliases."""
    from kabot.providers.registry import ModelRegistry

    registry = ModelRegistry()
    aliases = registry.get_all_aliases()

    # Group by provider
    grouped = {}
    for alias, model_id in aliases.items():
        provider = model_id.split("/")[0]
        if provider not in grouped:
            grouped[provider] = []
        grouped[provider].append((alias, model_id))

    console.print("│")
    console.print("│  [bold cyan]Available Model Aliases[/bold cyan]")
    console.print("│")

    for provider, items in sorted(grouped.items()):
        console.print(f"│  [bold]{provider.title()}:[/bold]")
        for alias, model_id in sorted(items):
            console.print(f"│    {alias:12} → {model_id}")
        console.print("│")

    console.print("│  [dim]Press Enter to continue...[/dim]")
    input()
```

**Step 2: Test manually**

Run: `python -m kabot config`
Type 'help' in manual entry
Expected: See grouped alias list

**Step 3: Commit**

```bash
git add kabot/cli/setup_wizard.py
git commit -m "feat(cli): add alias help screen"
```

---

## Phase 2: Enhanced Features (Brief Outline)

### Task 6: Model Browser with Status Indicators

Create `_model_browser()` method with Rich table showing:
- Model ID, Alias, Status indicator, Context window
- Filter by provider dropdown
- Status legend at bottom

### Task 7: Smart Error Messages

Enhance error handling in `_manual_model_entry()`:
- Fuzzy matching for typos
- Provider-specific suggestions
- Common mistake detection (missing provider prefix)

### Task 8: Integration Tests

Create `tests/cli/test_setup_wizard_integration.py`:
- Test full model selection flow
- Test alias resolution in wizard
- Test validation error handling

---

## Phase 3: Polish (Brief Outline)

### Task 9: Model Status Auto-Detection

Add utility to test models and update status database automatically.

### Task 10: Usage Examples

Add model-specific usage examples and recommendations.

---

## Testing Commands

```bash
# Run all tests
pytest tests/ -v

# Run specific test files
pytest tests/providers/test_model_status.py -v
pytest tests/cli/test_model_validator.py -v

# Manual testing
python -m kabot config
```

---

## Success Criteria

- ✓ Users see popular aliases first
- ✓ Manual entry shows format hints and examples
- ✓ Invalid input gets helpful suggestions
- ✓ Model status indicators show working vs catalog models
- ✓ Alias resolution works seamlessly
- ✓ All tests pass
