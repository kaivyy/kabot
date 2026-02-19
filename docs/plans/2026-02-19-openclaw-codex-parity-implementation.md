# OpenClaw Codex Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align kabot with OpenClaw code for OpenAI Codex OAuth, including model normalization, spark catalog fallback, and default model behavior, then port changes to main.

**Architecture:** Add a lightweight model-normalization helper in kabot config resolution so `openai/gpt-5.3-codex*` routes to `openai-codex` for credential lookup. Extend the model catalog/status to include `gpt-5.3-codex-spark`, and ensure `agents.defaults.model` supports `str | AgentModelConfig` without breaking summaries or provider matching. Update docs/tests accordingly and apply the same changes to main.

**Tech Stack:** Python, Pydantic config, pytest, Rich CLI.

---

### Task 1: Add model normalization + model type handling

**Files:**
- Modify: `kabot/config/schema.py`
- Modify: `kabot/cli/setup_wizard.py`
- Test: `tests/config/test_agent_config.py`

**Step 1: Write the failing tests**

Add to `tests/config/test_agent_config.py`:

```python
from kabot.config.schema import (
    Config,
    AgentsConfig,
    AgentDefaults,
    AgentModelConfig,
    ProvidersConfig,
    ProviderConfig,
    AuthProfile,
)


def test_provider_normalizes_openai_gpt53_codex_to_codex():
    cfg = Config(
        agents=AgentsConfig(defaults=AgentDefaults(model="openai/gpt-5.3-codex")),
        providers=ProvidersConfig(
            openai=ProviderConfig(api_key="sk-openai"),
            openai_codex=ProviderConfig(
                profiles={"default": AuthProfile(name="default", oauth_token="tok", token_type="oauth")},
                active_profile="default",
            ),
        ),
    )
    assert cfg.get_provider_name("openai/gpt-5.3-codex") == "openai-codex"


def test_provider_does_not_normalize_openai_gpt52_codex():
    cfg = Config(
        agents=AgentsConfig(defaults=AgentDefaults(model="openai/gpt-5.2-codex")),
        providers=ProvidersConfig(
            openai=ProviderConfig(api_key="sk-openai"),
            openai_codex=ProviderConfig(
                profiles={"default": AuthProfile(name="default", oauth_token="tok", token_type="oauth")},
                active_profile="default",
            ),
        ),
    )
    assert cfg.get_provider_name("openai/gpt-5.2-codex") == "openai"


def test_defaults_model_object_uses_primary_for_matching():
    cfg = Config(
        agents=AgentsConfig(
            defaults=AgentDefaults(
                model=AgentModelConfig(
                    primary="openai/gpt-5.3-codex",
                    fallbacks=["openai/gpt-5.2-codex"],
                )
            )
        ),
        providers=ProvidersConfig(
            openai=ProviderConfig(api_key="sk-openai"),
            openai_codex=ProviderConfig(
                profiles={"default": AuthProfile(name="default", oauth_token="tok", token_type="oauth")},
                active_profile="default",
            ),
        ),
    )
    assert cfg.get_provider_name() == "openai-codex"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/config/test_agent_config.py::test_provider_normalizes_openai_gpt53_codex_to_codex -v`
Expected: FAIL (provider resolves to openai / error due to model type).

**Step 3: Write minimal implementation**

Update `kabot/config/schema.py`:

```python
class AgentDefaults(BaseModel):
    # before: model: str = ...
    model: str | AgentModelConfig = "anthropic/claude-opus-4-5"


def _normalize_model_for_provider(model: str) -> str:
    if model.startswith("openai/gpt-5.3-codex"):
        return model.replace("openai/", "openai-codex/", 1)
    if model.startswith("gpt-5.3-codex"):
        return f"openai-codex/{model}"
    return model


def _primary_model_value(value: str | AgentModelConfig | None) -> str | None:
    if isinstance(value, AgentModelConfig):
        return value.primary
    return value

# In Config._match_provider:
model_value = _primary_model_value(model or self.agents.defaults.model) or ""
model_lower = _normalize_model_for_provider(model_value).lower()

# when resolving provider config names:
config_key = spec.name.replace("-", "_")

# In Config._provider_name_for:
if model:
    normalized = _normalize_model_for_provider(model)
    if "/" in normalized:
        return normalized.split("/")[0]
```

Update `kabot/cli/setup_wizard.py` summary rendering to handle `AgentModelConfig`:

```python
# In summary_box
model = c.agents.defaults.model
if hasattr(model, "primary"):
    fallbacks = ", ".join(getattr(model, "fallbacks", []) or [])
    lines.append(f"model: {model.primary} (fallbacks: {fallbacks})")
else:
    lines.append(f"model: {model}")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/config/test_agent_config.py::test_provider_normalizes_openai_gpt53_codex_to_codex -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/config/schema.py kabot/cli/setup_wizard.py tests/config/test_agent_config.py
git commit -m "feat(config): normalize gpt-5.3 codex provider"
```

---

### Task 2: Add Codex spark catalog + status

**Files:**
- Modify: `kabot/providers/catalog.py`
- Modify: `kabot/providers/model_status.py`
- Test: `tests/providers/test_model_status.py`

**Step 1: Write the failing test**

Add to `tests/providers/test_model_status.py`:

```python
def test_get_model_status_codex_spark_catalog():
    assert get_model_status("openai-codex/gpt-5.3-codex-spark") in {"catalog", "working"}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/providers/test_model_status.py::test_get_model_status_codex_spark_catalog -v`
Expected: FAIL (unsupported/unknown).

**Step 3: Write minimal implementation**

Update `kabot/providers/catalog.py` with a new entry adjacent to the existing codex model:

```python
ModelMetadata(
    id="openai-codex/gpt-5.3-codex-spark",
    name="GPT-5.3 Codex Spark",
    provider="openai-codex",
    context_window=128000,
    pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
    capabilities=["tools", "coding", "reasoning"],
    is_premium=True
),
```

Update `kabot/providers/model_status.py`:

```python
CATALOG_ONLY = {
    # ...
    "openai-codex/gpt-5.3-codex-spark",
}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/providers/test_model_status.py::test_get_model_status_codex_spark_catalog -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/providers/catalog.py kabot/providers/model_status.py tests/providers/test_model_status.py
git commit -m "feat(catalog): add codex spark model"
```

---

### Task 3: Docs parity with OpenClaw code

**Files:**
- Modify: any existing kabot docs that mention Codex/OpenAI defaults (search-driven)
- Modify: `docs/plans/2026-02-19-openai-codex-oauth-parity-design.md` (already updated)

**Step 1: Locate docs to update**

Run: `rg -n "openai|codex" docs`

**Step 2: Update docs**

- Set Codex OAuth default to `openai-codex/gpt-5.3-codex`.
- Note that `openai/gpt-5.3-codex` is normalized to `openai-codex` for OAuth credentials.

**Step 3: Commit**

```bash
git add docs
git commit -m "docs: align codex oauth defaults with OpenClaw"
```

---

### Task 4: Port changes from worktree to main

**Files:**
- Apply all changes from the `openai-codex-oauth` worktree to main:
  - `kabot/config/schema.py`
  - `kabot/cli/setup_wizard.py`
  - `kabot/providers/catalog.py`
  - `kabot/providers/model_status.py`
  - `tests/config/test_agent_config.py`
  - `tests/providers/test_model_status.py`
  - docs changes (if any)

**Step 1: Identify commits in worktree**

Run (in worktree): `git log --oneline -5`

**Step 2: Cherry-pick or re-apply**

- Cherry-pick commits onto main OR re-apply patches manually if preferred.

**Step 3: Verify on main**

Run targeted tests on main:
- `pytest tests/config/test_agent_config.py::test_provider_normalizes_openai_gpt53_codex_to_codex -v`
- `pytest tests/providers/test_model_status.py::test_get_model_status_codex_spark_catalog -v`

**Step 4: Commit (if re-applied manually)**

```bash
git add kabot/config/schema.py kabot/cli/setup_wizard.py kabot/providers/catalog.py kabot/providers/model_status.py tests/config/test_agent_config.py tests/providers/test_model_status.py docs
git commit -m "feat: align codex oauth parity with OpenClaw"
```

---

Plan complete and saved to `docs/plans/2026-02-19-openclaw-codex-parity-implementation.md`. Two execution options:

1. **Subagent-Driven (this session)** — I dispatch fresh subagent per task, review between tasks, fast iteration
2. **Parallel Session (separate)** — Open new session with executing-plans, batch execution with checkpoints

Which approach?
