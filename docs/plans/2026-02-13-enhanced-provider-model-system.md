# Enhanced Provider & Model System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform Kabot's model management into a mature, plugin-based system supporting extensive metadata, dynamic scanning, and aliases (OpenClaw-style).

**Architecture:** 
1. **Model Metadata Schema**: Define strict types for model properties (cost, context, capabilities).
2. **Hybrid Registry**: A centralized registry combining a static catalog (high-quality metadata) and a dynamic cache (SQLite) for scanned models.
3. **Provider Plugins**: Modular handlers in `kabot/providers/plugins/` that register models and auth logic.
4. **Smart Resolver**: Logic to handle Aliases (`gpt4`), Short Names (`gpt-4o`), and Full IDs.

**Tech Stack:** Python 3.11+, Pydantic, SQLite, LiteLLM.

---

## Task 1: Model Metadata & Registry Foundation

**Files:**
- Create: `kabot/providers/models.py` (Metadata schemas)
- Modify: `kabot/providers/registry.py` (Central logic)
- Test: `tests/providers/test_registry.py`

**Step 1: Define ModelMetadata Schema**
```python
from pydantic import BaseModel
from typing import List, Optional

class ModelPricing(BaseModel):
    input_1m: float = 0.0
    output_1m: float = 0.0

class ModelMetadata(BaseModel):
    id: str
    name: str
    provider: str
    context_window: int
    pricing: ModelPricing
    capabilities: List[str] = [] # vision, tool_use, reasoning
    is_premium: bool = False # From static catalog
```

**Step 2: Implement Registry core**
Update `ModelRegistry` to store and search these objects.

**Step 3: Create tests**
Verify metadata storage and retrieval.

---

## Task 2: Static Catalog & Plugin System

**Files:**
- Create: `kabot/providers/catalog.py` (The "Source of Truth")
- Create: `kabot/providers/plugins/__init__.py`
- Create: `kabot/providers/plugins/openai.py` (Example plugin)

**Step 1: Populate Static Catalog**
Add metadata for `gpt-4o`, `claude-3-5-sonnet`, `kimi-k2.5`, etc.

**Step 2: Implement Plugin Loading**
Logic to scan `kabot/providers/plugins/` and register provider-specific metadata.

**Step 3: Integrate with Auth**
Ensure when a user logins, the plugin can "patch" the config with recommended models.

---

## Task 3: Dynamic Model Scanning (`models scan`)

**Files:**
- Modify: `kabot/cli/commands.py` (Add `models scan`)
- Create: `kabot/providers/scanner.py`

**Step 1: Implement Scanner logic**
Logic to call `/v1/models` for registered providers and normalize output into `ModelMetadata`.

**Step 2: SQLite Storage**
Save scanned models to a `models` table in Kabot's database to persist between runs.

**Step 3: Test CLI command**
Mock a provider API and verify `kabot models scan` populates the DB.

---

## Task 4: Smart Resolver & Aliases

**Files:**
- Modify: `kabot/providers/registry.py`
- Modify: `kabot/config/schema.py` (User custom aliases)

**Step 1: Implement Alias Logic**
Priority: User Custom Alias -> Plugin Default Alias -> Short Name -> Full ID.

**Step 2: Update AgentLoop to use Resolver**
Ensure `AgentLoop` resolves `sonnet` to the full ID before calling LiteLLM.

**Step 3: Verify Resolution**
Tests for `resolve("gpt4")` -> `openai/gpt-4o`.

---

## Task 5: Final Polish & Semi-Auto Config

**Step 1: Add Model Picker to Login**
Modify `kabot auth login` to show a list of models from the plugin after success.

**Step 2: Implementation of `kabot models list`**
Show a beautiful Rich table with prices, context window, and status (configured/not).

**Step 3: Documentation**
Update `docs/models/` with the new system details.
