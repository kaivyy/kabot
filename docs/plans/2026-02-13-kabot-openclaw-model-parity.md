# Kabot OpenClaw-Style Model & Provider System (v2.0)

**Date**: 2026-02-13
**Status**: Draft / Design
**Author**: Development Session
**Scope**: Deep integration of 25+ providers, 100+ models, Dynamic Scanning, and Smart Aliasing.

---

## 📋 Executive Summary

### Problem Statement
Current Kabot (v1.0.0) has a solid foundation for multi-method auth, but model management is still "static" and lacks the depth found in OpenClaw. Users cannot easily discover new models, see accurate pricing, or use short aliases for complex model IDs.

### Objective
Rebuild the Provider and Model system to support:
- **Modular Plugin Architecture**: Adding a provider is as easy as creating a folder.
- **Rich Metadata**: Every model knows its cost, context window, and special skills (Vision, Reasoning).
- **Hybrid Discovery**: Static "Premium" catalog + Dynamic "API Scan" results.
- **Smart Resolver**: Intelligent mapping of `sonnet` -> `anthropic/claude-3-5-sonnet-20240620`.

---

## 🏗️ Architecture Overview

### Current Architecture (LiteLLM-Direct)
```
User (config.json) -> LiteLLM -> API Provider
```
*Issue*: Kabot doesn't know *what* the model can do until it tries to call it.

### New Architecture (Plugin-Hybrid)
```
User (Alias/ID) -> Smart Resolver 
                       |-> User Custom Alias
                       |-> Central Registry (SQLite + Static Catalog)
                               |-> Provider Plugins (OpenAI, Kimi, etc.)
                               |-> Scanned Cache (via 'models scan')
                       |-> Fallback (LiteLLM)
                               |-> API Provider
```

---

## 📦 Component Design

### 1. Data Models (`kabot/providers/models.py`)
Every model is treated as a `ModelMetadata` object:
- `id`: Unique identifier (e.g., `openai/gpt-4o`)
- `short_name`: Display name (e.g., `GPT-4o`)
- `provider`: Parent provider ID.
- `context_window`: Integer (e.g., 128000)
- `max_output`: Integer (e.g., 4096)
- `pricing`: `{ "input": float, "output": float }` (USD per 1M tokens)
- `capabilities`: List of flags (`vision`, `tools`, `reasoning`, `json`)
- `is_premium`: Boolean (Is it part of our hand-curated static catalog?)

### 2. Provider Plugins (`kabot/providers/plugins/`)
Each folder contains:
- `__init__.py`: Registration logic.
- `manifest.py`: Static list of models (OpenClaw-style).
- `auth.py`: Existing auth handlers (already implemented in v1.0.0).

---

## 📅 Implementation Phases

### Phase 1: Foundation & Registry (Week 1)
- **Metadata Definitions**: Implement Pydantic models for Model properties.
- **SQLite Schema**: Add `models` table to `memory_db/metadata.db`.
- **Core Registry**: Implement `ModelRegistry` class to manage lookups across Static and Dynamic sources.

### Phase 2: Static Catalog & Initial Plugins (Week 1)
- **The "Big Catalog"**: Curate a massive list of models from OpenAI, Anthropic, Google, Kimi, and MiniMax.
- **Metadata Entry**: Add pricing and context info for `kimi-k2.5`, `gpt-4o`, `claude-3.5-sonnet`.
- **Plugin Loader**: Build the logic that scans `kabot/providers/plugins/` on startup.

### Phase 3: Dynamic Discovery (`models scan`) (Week 2)
- **Scanner Utility**: Implementation of `/v1/models` crawlers for each logged-in provider.
- **Normalization Engine**: Logic to convert various API responses into standard Kabot `ModelMetadata`.
- **Persistence**: Save scanned models to SQLite so they are available offline.

### Phase 4: Intelligence & Resolver (Week 2)
- **Alias Engine**: Allow users to define `alias: { "pro": "anthropic/claude-3-opus" }` in `config.json`.
- **Resolver Logic**:
    1. Check user aliases.
    2. Check plugin-defined short names.
    3. Fuzzy match against Registry.
    4. Pass to LiteLLM if all else fails.
- **Agent Integration**: Update `AgentLoop` to resolve models at the start of every session.

### Phase 5: UI & Experience (Week 3)
- **Beautiful Tables**: `kabot models list` using Rich with color-coded pricing and status.
- **Onboarding Wizard**: 
    - Success login -> "Scanning models..."
    - "I found 12 models. Do you want to set 'kimi-k2.5' as your default? (Y/n)"
- **Documentation**: Finalize `docs/models/` detailing every model's capability.

---

## 🛠️ CLI Command Specification

| Command | Action |
| :--- | :--- |
| `kabot models list` | Show all configured models + pricing. |
| `kabot models scan` | Call all provider APIs to refresh model list. |
| `kabot models set <name>` | Quickly set primary model (supports aliases). |
| `kabot models info <id>` | Show detailed metadata (context, cost, etc.). |

---

## 🧪 Testing & Success Criteria

### Success Metrics
- [ ] Support for 25+ providers via Hybrid Registry.
- [ ] Model resolution time < 50ms.
- [ ] 90%+ accuracy in pricing metadata.
- [ ] Zero regressions in existing `kabot agent` flow.

### Test Scenarios
- **Alias Test**: `resolve("sonnet")` returns full Anthropic ID.
- **Metadata Test**: Registry returns correct context window for `kimi-k2.5`.
- **Scan Test**: Adding a new model via LiteLLM is detected by `models scan`.
