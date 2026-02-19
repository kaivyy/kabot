# OpenAI Codex OAuth Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add OpenAI Codex OAuth as a first‑class provider in kabot while preserving existing OpenAI API‑key flows and enforcing the selected fallback order.

**Architecture:** Introduce an `openai-codex` provider in the registry and model status, route OAuth credentials to this provider, and update default model selection to the agreed primary→fallback order. Keep OAuth refresh behavior in the existing refresh service.

**Tech Stack:** Python, LiteLLM, Pydantic config, Rich CLI, pytest.

---

### Task 1: Add `openai-codex` provider spec

**Files:**
- Modify: `kabot/providers/registry.py`

**Step 1: Write the failing test**

Create a new test in `tests/providers/test_registry.py` that expects `find_by_name("openai-codex")` to return a provider spec and that `find_by_model("openai-codex/gpt-5.3-codex")` resolves to the same provider.

```python
def test_openai_codex_provider_registered():
    from kabot.providers.registry import find_by_name, find_by_model

    spec = find_by_name("openai-codex")
    assert spec is not None
    assert spec.name == "openai-codex"

    model_spec = find_by_model("openai-codex/gpt-5.3-codex")
    assert model_spec is not None
    assert model_spec.name == "openai-codex"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/providers/test_registry.py::test_openai_codex_provider_registered -v`
Expected: FAIL (spec is None).

**Step 3: Write minimal implementation**

Update `kabot/providers/registry.py` `PROVIDERS` to include:
- name: `openai-codex`
- keywords: `("openai-codex", "codex")`
- env_key: `OPENAI_CODEX_API_KEY` (or reuse `OPENAI_API_KEY` if you decide to share)
- display_name: `OpenAI Codex`
- litellm_prefix: `openai-codex`
- skip_prefixes: `( "openai-codex/", )`

**Step 4: Run test to verify it passes**

Run: `pytest tests/providers/test_registry.py::test_openai_codex_provider_registered -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/providers/registry.py tests/providers/test_registry.py
git commit -m "feat(providers): register openai-codex provider"
```

---

### Task 2: Update model status for `openai-codex`

**Files:**
- Modify: `kabot/providers/model_status.py`
- Test: `tests/providers/test_model_status.py`

**Step 1: Write the failing test**

Add a test ensuring `openai-codex/gpt-5.3-codex` is **not** `unsupported`.

```python
def test_openai_codex_status_supported_or_catalog():
    from kabot.providers.model_status import get_model_status

    status = get_model_status("openai-codex/gpt-5.3-codex")
    assert status in {"catalog", "working"}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/providers/test_model_status.py::test_openai_codex_status_supported_or_catalog -v`
Expected: FAIL (status == "unsupported").

**Step 3: Write minimal implementation**

- Remove `openai-codex` from `UNSUPPORTED_PROVIDERS`.
- Add `openai-codex/gpt-5.3-codex` to `CATALOG_ONLY` (or `WORKING_MODELS` if validated).

**Step 4: Run test to verify it passes**

Run: `pytest tests/providers/test_model_status.py::test_openai_codex_status_supported_or_catalog -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/providers/model_status.py tests/providers/test_model_status.py
git commit -m "fix(model-status): mark openai-codex as supported"
```

---

### Task 3: Route OpenAI OAuth credentials to `openai-codex`

**Files:**
- Modify: `kabot/auth/handlers/openai_oauth.py`
- Modify: `kabot/auth/menu.py`
- Modify: `kabot/auth/manager.py`
- Test: `tests/auth/test_openai_oauth_routing.py` (new)

**Step 1: Write the failing test**

Create a test that simulates OAuth handler output and asserts the credentials are saved under `providers.openai-codex` (not `providers.openai`).

```python
def test_openai_oauth_saves_to_openai_codex(tmp_path, monkeypatch):
    from kabot.auth.manager import AuthManager

    # Mock handler output
    auth_data = {
        "providers": {
            "openai-codex": {
                "oauth_token": "tok",
                "refresh_token": "ref",
                "token_type": "oauth",
                "expires_at": 1234567890,
            }
        }
    }

    manager = AuthManager()
    assert manager._save_credentials(auth_data)

    # Reload config and validate provider placement
    from kabot.config.loader import load_config
    cfg = load_config()
    assert cfg.providers.openai_codex.profiles
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/auth/test_openai_oauth_routing.py::test_openai_oauth_saves_to_openai_codex -v`
Expected: FAIL (provider openai_codex missing).

**Step 3: Write minimal implementation**

- Update `OpenAIOAuthHandler` to return `providers: {"openai-codex": {...}}` instead of `"openai"`.
- Update `auth/menu.py` to label OpenAI OAuth as Codex OAuth for clarity.
- Update config schema/provider naming if needed (`providers.openai_codex` field name).

**Step 4: Run test to verify it passes**

Run: `pytest tests/auth/test_openai_oauth_routing.py::test_openai_oauth_saves_to_openai_codex -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/auth/handlers/openai_oauth.py kabot/auth/menu.py kabot/auth/manager.py tests/auth/test_openai_oauth_routing.py
git commit -m "feat(auth): route OpenAI OAuth to openai-codex"
```

---

### Task 4: Default model + fallback order after OAuth login

**Files:**
- Modify: `kabot/cli/setup_wizard.py`
- Modify: `kabot/providers/catalog.py`
- Test: `tests/cli/test_setup_wizard_default_model.py` (new)

**Step 1: Write the failing test**

Add a test that simulates OAuth login completion and asserts the default model order:

```python
def test_oauth_codex_default_model_order():
    from kabot.config.loader import load_config

    cfg = load_config()
    # Placeholder check: after OAuth flow, defaults should be set
    assert cfg.agents.defaults.model["primary"] == "openai-codex/gpt-5.3-codex"
    assert cfg.agents.defaults.model["fallbacks"] == [
        "openai/gpt-5.2-codex",
        "openai/gpt-4o-mini",
    ]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_setup_wizard_default_model.py::test_oauth_codex_default_model_order -v`
Expected: FAIL.

**Step 3: Write minimal implementation**

- Update `setup_wizard.py` flow to set `defaults.model` to the specified primary + fallbacks after OAuth Codex login.
- Ensure catalog includes `openai/gpt-5.2-codex` and `openai/gpt-4o-mini` so validation succeeds.

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_setup_wizard_default_model.py::test_oauth_codex_default_model_order -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/cli/setup_wizard.py kabot/providers/catalog.py tests/cli/test_setup_wizard_default_model.py
git commit -m "feat(cli): set codex oauth default model order"
```

---

### Task 5: Smoke test with LiteLLM provider

**Files:**
- Modify: `kabot/_test_openai.py`

**Step 1: Write the failing test**

Add a small test entry that uses `openai-codex/gpt-5.3-codex` when OAuth profile is configured.

```python
async def test_codex_oauth_model():
    response = await provider.chat(
        messages=[{"role": "user", "content": "ping"}],
        model="openai-codex/gpt-5.3-codex",
    )
    assert response.content
```

**Step 2: Run test to verify it fails**

Run: `python _test_openai.py`
Expected: FAIL if provider not wired.

**Step 3: Write minimal implementation**

Update `_test_openai.py` to detect `openai-codex` profile and choose the codex model when present.

**Step 4: Run test to verify it passes**

Run: `python _test_openai.py`
Expected: PASS (assuming valid OAuth token).

**Step 5: Commit**

```bash
git add kabot/_test_openai.py
git commit -m "test: add codex oauth smoke path"
```

---

## Execution Notes
- Use **TDD**: write tests first, confirm fail, implement minimal fix, re-run tests.
- Keep commits small and per-task.
- If LiteLLM rejects `openai-codex`, treat that as a validation failure and fall back to `openai/*` path as per model order.

---

Plan complete and saved to `docs/plans/2026-02-19-openai-codex-oauth-parity-implementation.md`. Two execution options:

1. **Subagent-Driven (this session)** — I dispatch fresh subagent per task, review between tasks, fast iteration
2. **Parallel Session (separate)** — Open new session with executing-plans, batch execution with checkpoints

Which approach?
