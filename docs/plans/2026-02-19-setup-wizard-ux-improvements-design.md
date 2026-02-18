# Setup Wizard UX Improvements Design

**Date:** 2026-02-19
**Goal:** Make Kabot setup wizard beginner-friendly with clear model selection guidance
**Approach:** Alias-first interface with progressive disclosure and real-time validation

---

## Problem Statement

Users are confused during model selection in `kabot config`:

1. **Format confusion**: Trying "gpt-5.3-codex" instead of "openai-codex/gpt-5.3-codex"
2. **No hints**: No examples or format guidance when entering manually
3. **Catalog vs Working**: Models in catalog may not work (e.g., openai-codex provider unsupported)
4. **No aliases shown**: Users don't know shortcuts like "codex", "sonnet", "gemini" exist

**Current Experience:**
```
? Select default model
  > openai/gpt-4o (GPT-4o) ★
  > openai/gpt-4o-mini (GPT-4o Mini) ★
  > Enter model ID manually

Enter Model ID: gpt-5.3-codex
❌ Error: No API key configured
```

**Desired Experience:**
```
? Select default model (or use alias)

Popular Aliases:
  > codex       - OpenAI GPT-5.1 Codex (Advanced Coding)
  > sonnet      - Claude 3.5 Sonnet (Latest, 200K context)
  > gemini      - Google Gemini 1.5 Pro (2M context)

  Browse All Models
  Enter Model ID or Alias Manually

Enter Model ID or Alias: codex
✓ Resolved to: openai/gpt-5.1-codex
```

---

## Architecture

### Design Philosophy: Beginner-First with Power User Escape Hatches

**Principle 1: Aliases as Primary Interface**
- Show popular aliases first (codex, sonnet, gemini, gpt4o)
- Full model IDs are secondary (for advanced users)
- Inspired by OpenClaw's alias-first approach

**Principle 2: Progressive Disclosure**
- Simple view by default
- "Browse All Models" for exploration
- Manual entry for power users

**Principle 3: Real-Time Validation**
- Validate format before saving
- Check LiteLLM compatibility
- Show warnings for catalog-only models
- Suggest alternatives for invalid input

**Principle 4: Clear Feedback**
- Status indicators: ✓ (working) ⚠ (catalog) ✗ (unsupported)
- Helpful error messages with suggestions
- Examples and format hints everywhere

---

## Components

### 1. Enhanced Model Picker (Primary Interface)

**Location:** `kabot/cli/setup_wizard.py:_model_picker()`

**New Flow:**
```
┌─ Model Selection ────────────────────────────────────────┐
│                                                          │
│ Select default model (or use alias)                     │
│                                                          │
│ Popular Aliases:                                         │
│ > codex       - OpenAI GPT-5.1 Codex (Advanced Coding)  │
│   sonnet      - Claude 3.5 Sonnet (Latest, 200K)        │
│   gemini      - Google Gemini 1.5 Pro (2M context)      │
│   gpt4o       - OpenAI GPT-4o (Multi-modal)             │
│                                                          │
│   Browse All Models (by provider)                       │
│   Enter Model ID or Alias Manually                      │
│   Keep Current (openai/gpt-4o)                          │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**Implementation:**
- Add "Popular Aliases" section at top
- Show 4-6 most common aliases with descriptions
- Keep "Browse All Models" and "Manual Entry" options
- Add "Keep Current" option

### 2. Manual Entry with Smart Hints

**Location:** `kabot/cli/setup_wizard.py:_model_picker()` manual entry branch

**New Interface:**
```
Enter Model ID or Alias

Format: provider/model-name  OR  alias
Examples:
  • openai/gpt-4o
  • anthropic/claude-3-5-sonnet-20241022
  • codex (alias for openai/gpt-5.1-codex)

Available aliases: codex, sonnet, gemini, gpt4o, o1, kimi
Type 'help' to see all aliases

Your input: _
```

**Validation Flow:**
1. User enters input
2. Check if it's an alias → resolve to full ID
3. Check format: must be `provider/model-name`
4. Validate provider support in LiteLLM
5. Show status indicator
6. Confirm if warnings exist

**Error Handling:**
```
❌ Invalid format: "gpt-5.3-codex"
   Expected: provider/model-name
   Did you mean: openai/gpt-5.1-codex (alias: codex)?

⚠️  Model "openai-codex/gpt-5.3-codex" is not supported
   This provider is not available in LiteLLM.

   Recommended alternatives:
   • openai/gpt-4o (alias: gpt4o)
   • openai/gpt-5.1-codex (alias: codex)

   Continue anyway? [y/N]
```

### 3. Model Browser (Secondary Interface)

**Location:** `kabot/cli/setup_wizard.py:_model_browser()`

**New Component:**
```
┌─ Model Browser ─────────────────────────────────────────┐
│ Filter: [openai ▼]                    Search: [____]    │
├──────────────────────────────────────────────────────────┤
│ Model ID                    Alias    Status   Context   │
├──────────────────────────────────────────────────────────┤
│ openai/gpt-4o              gpt4o    ✓ Ready  128K      │
│ openai/gpt-4o-mini         gpt4m    ✓ Ready  128K      │
│ openai/o1-preview          o1       ✓ Ready  128K      │
│ openai/gpt-5.1-codex       codex    ⚠ Catalog 128K     │
│ openai-codex/gpt-5.3-codex codex-pro ✗ Not Supported   │
└──────────────────────────────────────────────────────────┘

Legend:
✓ Ready - Tested and working with LiteLLM
⚠ Catalog - In catalog but not verified
✗ Not Supported - Provider not supported by LiteLLM

Use ↑↓ to navigate, Enter to select, Esc to cancel
```

**Features:**
- Filter by provider dropdown
- Search by model name
- Status indicators for each model
- Context window display
- Alias display

### 4. Alias Help Screen

**Location:** `kabot/cli/setup_wizard.py:_show_alias_help()`

**Triggered by:** Typing 'help' in manual entry

**Display:**
```
┌─ Available Model Aliases ───────────────────────────────┐
│                                                          │
│ OpenAI:                                                  │
│   codex      → openai/gpt-5.1-codex                     │
│   gpt4o      → openai/gpt-4o                            │
│   gpt4m      → openai/gpt-4o-mini                       │
│   o1         → openai/o1-preview                        │
│                                                          │
│ Anthropic:                                               │
│   sonnet     → anthropic/claude-3-5-sonnet-20241022     │
│   opus       → anthropic/claude-3-opus-20240229         │
│   haiku      → anthropic/claude-3-5-haiku-20241022      │
│                                                          │
│ Google:                                                  │
│   gemini     → google/gemini-1.5-pro                    │
│   flash      → google/gemini-1.5-flash                  │
│                                                          │
│ Others:                                                  │
│   kimi       → moonshot/kimi-k2.5                       │
│   minimax    → minimax/MiniMax-M2.1                     │
│                                                          │
│ Press any key to continue...                            │
└──────────────────────────────────────────────────────────┘
```

### 5. Model Status Database

**Location:** `kabot/providers/model_status.py` (new file)

**Purpose:** Track which models are confirmed working vs catalog-only

**Structure:**
```python
# Models confirmed working with LiteLLM
WORKING_MODELS = {
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "openai/o1-preview",
    "openai/o1-mini",
    "anthropic/claude-3-5-sonnet-20241022",
    "anthropic/claude-3-opus-20240229",
    "google/gemini-1.5-pro",
    "google/gemini-1.5-flash",
    "groq/llama3-70b-8192",
    # ... more
}

# Models in catalog but not verified
CATALOG_ONLY = {
    "openai/gpt-5.1-codex",
    "anthropic/claude-opus-4-6",
    "anthropic/claude-sonnet-4-5",
    # ... more
}

# Known unsupported providers
UNSUPPORTED_PROVIDERS = {
    "openai-codex",  # Not supported by LiteLLM
    "kimi-coding",   # Custom provider
    "google-gemini-cli",  # CLI-only
    # ... more
}

def get_model_status(model_id: str) -> str:
    """Return 'working', 'catalog', or 'unsupported'."""
    if model_id in WORKING_MODELS:
        return "working"

    provider = model_id.split("/")[0]
    if provider in UNSUPPORTED_PROVIDERS:
        return "unsupported"

    if model_id in CATALOG_ONLY:
        return "catalog"

    return "unknown"
```

### 6. Model Validator

**Location:** `kabot/cli/model_validator.py` (new file)

**Purpose:** Real-time validation of model IDs

**Functions:**
```python
def validate_model_id(model_id: str) -> ValidationResult:
    """Validate model ID format and compatibility."""

def resolve_alias(alias: str) -> Optional[str]:
    """Resolve alias to full model ID."""

def suggest_alternatives(invalid_id: str) -> List[str]:
    """Suggest valid alternatives for invalid input."""

def format_validation_error(error: ValidationError) -> str:
    """Format user-friendly error message."""
```

---

## Data Flow

```
User Input
    ↓
Is it an alias? → Yes → Resolve to full ID
    ↓ No
Format validation (provider/model-name)
    ↓
Provider support check
    ↓
Model status lookup (working/catalog/unsupported)
    ↓
Display status indicator
    ↓
Confirmation (if warnings)
    ↓
Save to config
```

---

## User Experience Examples

### Example 1: Beginner Using Alias

```
? Select default model (or use alias)

Popular Aliases:
> codex       - OpenAI GPT-5.1 Codex (Advanced Coding)
  sonnet      - Claude 3.5 Sonnet (Latest, 200K context)
  gemini      - Google Gemini 1.5 Pro (2M context)

[User selects "codex"]

✓ Selected: openai/gpt-5.1-codex
⚠ Note: This model is in catalog but not verified to work.
  If you encounter issues, try: openai/gpt-4o (alias: gpt4o)

Continue? [Y/n] y
✓ Model set to openai/gpt-5.1-codex
```

### Example 2: Power User Manual Entry

```
? Select default model (or use alias)
  [User selects "Enter Model ID or Alias Manually"]

Enter Model ID or Alias

Format: provider/model-name  OR  alias
Examples:
  • openai/gpt-4o
  • codex (alias)

Your input: gpt-5.3-codex

❌ Invalid format: "gpt-5.3-codex"
   Expected: provider/model-name

   Did you mean one of these?
   • openai/gpt-5.1-codex (alias: codex)
   • openai/gpt-4o (alias: gpt4o)

Your input: openai/gpt-4o

✓ Valid model ID
✓ Status: Ready (tested and working)
✓ Model set to openai/gpt-4o
```

### Example 3: Advanced User Browsing

```
? Select default model (or use alias)
  [User selects "Browse All Models"]

┌─ Model Browser ─────────────────────────────────────────┐
│ Filter: [all providers ▼]                               │
├──────────────────────────────────────────────────────────┤
│ Model ID                    Alias    Status   Context   │
├──────────────────────────────────────────────────────────┤
│ openai/gpt-4o              gpt4o    ✓ Ready  128K      │
│ anthropic/claude-3-5-sonnet sonnet   ✓ Ready  200K      │
│ google/gemini-1.5-pro      gemini   ✓ Ready  2M        │
│ openai/gpt-5.1-codex       codex    ⚠ Catalog 128K     │
└──────────────────────────────────────────────────────────┘

[User selects openai/gpt-4o]

✓ Model set to openai/gpt-4o
```

---

## Implementation Priority

### Phase 1: Core Improvements (High Priority)
1. Add popular aliases section to model picker
2. Implement manual entry with format hints
3. Add alias resolution logic
4. Create model status database
5. Implement basic validation

### Phase 2: Enhanced Features (Medium Priority)
6. Create model browser with status indicators
7. Add alias help screen
8. Implement smart error messages with suggestions
9. Add search/filter in browser

### Phase 3: Polish (Low Priority)
10. Add model status auto-detection
11. Implement model testing utility
12. Add usage examples for each model
13. Create model recommendation system

---

## Testing Strategy

### Unit Tests
- Alias resolution
- Format validation
- Status lookup
- Error message formatting

### Integration Tests
- Full model selection flow
- Manual entry with validation
- Browser navigation
- Error handling

### User Testing
- Beginner users: Can they select a model without confusion?
- Power users: Can they quickly enter custom models?
- Error recovery: Do error messages help them fix issues?

---

## Success Metrics

1. **Reduced confusion**: Users successfully select working models on first try
2. **Faster setup**: Average time to select model decreases
3. **Fewer errors**: Reduced "No API key" or "Model not found" errors
4. **Better discovery**: Users learn about aliases and alternatives

---

## Future Enhancements

1. **Model recommendations**: Suggest models based on use case
2. **Cost calculator**: Show pricing for each model
3. **Performance metrics**: Display speed/quality ratings
4. **Auto-detection**: Test models and update status automatically
5. **Model comparison**: Side-by-side comparison of models
6. **Favorites**: Save frequently used models

---

## References

- OpenClaw model reference: `docs/models/openclaw-model-reference.md`
- Current catalog: `kabot/providers/catalog.py`
- Setup wizard: `kabot/cli/setup_wizard.py`
- Auth menu: `kabot/auth/menu.py`
