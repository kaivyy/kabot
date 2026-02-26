# Kabot Kabot Provider Catalog Parity (v0.5.7) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Kabot provider/model setup significantly more complete (Kabot-aligned) so users can input API/auth once in setup wizard, choose from a rich model list, and still manually input custom models.

**Architecture:** Introduce a centralized Kabot-derived provider/model catalog in Kabot, wire it into registry/auth/setup flows, and preserve runtime compatibility by treating additional OpenAI-compatible endpoints as gateway providers with safe default bases. Keep manual model entry unchanged and add runtime auto-fallback enrichment from configured credentials.

**Tech Stack:** Python 3, Pydantic config schema, Rich/questionary setup wizard, pytest.

---

### Task 1: Add failing tests for expanded provider catalog + setup-chain behavior

**Files:**
- Modify: `tests/providers/test_registry.py`
- Modify: `tests/auth/test_menu.py`
- Modify: `tests/auth/test_manager.py`
- Modify: `tests/cli/test_setup_wizard_default_model.py`
- Modify: `tests/providers/test_model_status.py`

**Step 1: Write the failing tests**

```python
def test_catalog_contains_kabot_parity_models():
    registry = ModelRegistry()
    registry.clear()
    registry.load_catalog()
    assert registry.get_model("together/moonshotai/Kimi-K2.5") is not None
    assert registry.get_model("venice/claude-opus-45") is not None
    assert registry.get_model("qianfan/deepseek-v3.2") is not None
```

```python
def test_setup_wizard_auto_chain_includes_new_provider_credentials():
    wizard = SetupWizard()
    wizard.config.providers.together.api_key = "tok"
    wizard.config.providers.venice.api_key = "tok"
    changed = wizard._apply_auto_default_model_chain()
    assert changed is True
```

**Step 2: Run tests to verify they fail**

Run:
```bash
pytest tests/providers/test_registry.py tests/auth/test_menu.py tests/auth/test_manager.py tests/cli/test_setup_wizard_default_model.py tests/providers/test_model_status.py -q
```
Expected: FAIL on missing provider entries/models.

**Step 3: Minimal implementation placeholder**

```python
# no-op placeholder; real implementation in Tasks 2-3
```

**Step 4: Re-run tests (still expected fail before Task 2/3)**

Run:
```bash
pytest tests/providers/test_registry.py tests/auth/test_menu.py tests/auth/test_manager.py tests/cli/test_setup_wizard_default_model.py tests/providers/test_model_status.py -q
```
Expected: FAIL with explicit missing catalog/provider assertions.

**Step 5: Commit**

```bash
git add tests/providers/test_registry.py tests/auth/test_menu.py tests/auth/test_manager.py tests/cli/test_setup_wizard_default_model.py tests/providers/test_model_status.py
git commit -m "test: add failing tests for kabot-aligned provider catalog"
```

### Task 2: Implement provider/model catalog expansion and registry/schema parity

**Files:**
- Modify: `kabot/providers/catalog.py`
- Modify: `kabot/providers/registry.py`
- Modify: `kabot/providers/model_status.py`
- Modify: `kabot/config/schema.py`

**Step 1: Write (or extend) failing assertions where needed**

```python
assert "together" in [p.name for p in PROVIDERS]
assert config.providers.together is not None
```

**Step 2: Run targeted tests to verify failures**

Run:
```bash
pytest tests/providers/test_registry.py tests/providers/test_model_status.py tests/config/test_agent_config.py -q
```
Expected: FAIL if providers/models not wired.

**Step 3: Write minimal implementation**

```python
ProviderSpec(name="together", ... is_gateway=True, strip_model_prefix=True)
ProviderSpec(name="venice", ...)
ProviderSpec(name="huggingface", ...)
ProviderSpec(name="qianfan", ...)
ProviderSpec(name="nvidia", ...)
ProviderSpec(name="xai", ...)
ProviderSpec(name="cerebras", ...)
ProviderSpec(name="opencode", ...)
ProviderSpec(name="xiaomi", ...)
ProviderSpec(name="volcengine", ...)
ProviderSpec(name="byteplus", ...)
```

```python
class ProvidersConfig(BaseModel):
    together: ProviderConfig = Field(default_factory=ProviderConfig)
    venice: ProviderConfig = Field(default_factory=ProviderConfig)
    huggingface: ProviderConfig = Field(default_factory=ProviderConfig)
    qianfan: ProviderConfig = Field(default_factory=ProviderConfig)
    nvidia: ProviderConfig = Field(default_factory=ProviderConfig)
```

```python
ModelMetadata(id="venice/claude-opus-45", ...)
ModelMetadata(id="together/meta-llama/Llama-4-Scout-17B-16E-Instruct", ...)
ModelMetadata(id="qianfan/deepseek-v3.2", ...)
```

**Step 4: Run tests to verify pass**

Run:
```bash
pytest tests/providers/test_registry.py tests/providers/test_model_status.py tests/config/test_agent_config.py -q
```
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/providers/catalog.py kabot/providers/registry.py kabot/providers/model_status.py kabot/config/schema.py
git commit -m "feat: expand provider registry and static model catalog"
```

### Task 3: Implement auth + setup wizard UX parity for broader provider login and easy model picking

**Files:**
- Modify: `kabot/auth/handlers/simple.py`
- Modify: `kabot/auth/menu.py`
- Modify: `kabot/auth/manager.py`
- Modify: `kabot/cli/setup_wizard.py`

**Step 1: Add failing tests/adjustments first**

```python
assert "together" in AUTH_PROVIDERS
assert "venice" in AUTH_PROVIDERS
assert "huggingface" in AUTH_PROVIDERS
```

**Step 2: Run tests to verify fail**

Run:
```bash
pytest tests/auth/test_menu.py tests/auth/test_manager.py tests/cli/test_setup_wizard_default_model.py -q
```
Expected: FAIL on missing auth providers or chain behavior.

**Step 3: Minimal implementation**

```python
class TogetherKeyHandler(SimpleKeyHandler): ...
class VeniceKeyHandler(SimpleKeyHandler): ...
class HuggingFaceKeyHandler(SimpleKeyHandler): ...
class QianfanKeyHandler(SimpleKeyHandler): ...
class NvidiaKeyHandler(SimpleKeyHandler): ...
```

```python
AUTH_PROVIDERS.update({...})
_PROVIDER_ALIASES.update({...})
provider_mapping.update({...})
```

```python
# setup_wizard.py
provider_models = [
    ...,
    (self.config.providers.together, "together/moonshotai/Kimi-K2.5"),
    (self.config.providers.venice, "venice/llama-3.3-70b"),
]
```

**Step 4: Run tests to verify pass**

Run:
```bash
pytest tests/auth/test_menu.py tests/auth/test_manager.py tests/cli/test_setup_wizard_default_model.py -q
```
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/auth/handlers/simple.py kabot/auth/menu.py kabot/auth/manager.py kabot/cli/setup_wizard.py
git commit -m "feat: extend auth and setup wizard for richer provider onboarding"
```

### Task 4: Documentation update for v0.5.7 (HOW-TO-USE + CHANGELOG)

**Files:**
- Modify: `HOW-TO-USE.md`
- Modify: `CHANGELOG.md`

**Step 1: Write failing docs checks (manual checklist)**

```text
- HOW-TO-USE includes expanded provider list and setup-wizard flow
- HOW-TO-USE explicitly keeps manual model input option
- CHANGELOG has 0.5.7 with Added/Changed/Fixed
```

**Step 2: Manual verification of checklist (pre-edit)**

Run:
```bash
rg -n "0\.5\.7|Provider Login|manual model|Kabot" HOW-TO-USE.md CHANGELOG.md
```
Expected: Missing 0.5.7 and incomplete provider guidance.

**Step 3: Write minimal implementation**

```markdown
## [0.5.7] - 2026-02-24
### Added
- Kabot-aligned provider/model catalog expansion ...
```

```markdown
### Model/Auth (Simple setup)
1. Login provider
2. Auto model chain generated
3. Optional manual override model input
```

**Step 4: Verify doc entries exist**

Run:
```bash
rg -n "0\.5\.7|together|venice|huggingface|manual model" HOW-TO-USE.md CHANGELOG.md
```
Expected: Matches found for all new sections.

**Step 5: Commit**

```bash
git add HOW-TO-USE.md CHANGELOG.md
git commit -m "docs: add v0.5.7 provider catalog and setup wizard usage updates"
```

### Task 5: Full verification for touched scope

**Files:**
- Test: `tests/providers/test_registry.py`
- Test: `tests/providers/test_model_status.py`
- Test: `tests/auth/test_menu.py`
- Test: `tests/auth/test_manager.py`
- Test: `tests/cli/test_setup_wizard_default_model.py`
- Test: `tests/config/test_agent_config.py`

**Step 1: Run final targeted suite**

Run:
```bash
pytest tests/providers/test_registry.py tests/providers/test_model_status.py tests/auth/test_menu.py tests/auth/test_manager.py tests/cli/test_setup_wizard_default_model.py tests/config/test_agent_config.py -q
```
Expected: PASS.

**Step 2: Sanity check working tree and docs**

Run:
```bash
git status --short
```
Expected: only intended modified files.

**Step 3: Commit final verification checkpoint**

```bash
git add -A
git commit -m "test: verify kabot-aligned provider catalog and wizard behavior"
```

**Step 4: No push**

```bash
# Intentionally do not run git push
```

**Step 5: Report**

```text
Implementation complete locally, verification attached, no push performed.
```

