# Kabot Full Model Parity 0.5.7 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Menyamakan katalog model/provider Kabot dengan katalog statis Kabot + model refs dokumentasi provider agar user bisa login, memilih model, dan fallback lintas provider tanpa gap daftar model.

**Architecture:** Parity dilakukan pada tiga layer: (1) schema+registry provider untuk resolusi runtime, (2) katalog model+status+alias untuk UX model picker, (3) auth/setup wizard untuk onboarding provider tambahan. Verifikasi dilakukan lewat suite test terfokus provider/auth/config/wizard.

**Tech Stack:** Python (Pydantic, pytest), PowerShell tooling, existing Kabot provider/auth architecture.

---

### Task 1: Lengkapi provider schema dan registry runtime

**Files:**
- Modify: `kabot/config/schema.py`
- Modify: `kabot/providers/registry.py`
- Test: `tests/providers/test_registry.py`
- Test: `tests/config/test_agent_config.py`

**Step 1: Write failing test expectations for new parity providers**

Tambahkan expected provider names untuk provider parity tambahan (synthetic/cloudflare-ai-gateway/vercel-ai-gateway).

**Step 2: Run targeted tests to verify failure**

Run: `pytest tests/providers/test_registry.py tests/config/test_agent_config.py -q`
Expected: FAIL karena provider belum ada di schema/registry.

**Step 3: Implement minimal provider wiring**

Tambahkan field `ProvidersConfig` + `ProviderSpec` untuk provider parity baru dengan base URL/default behavior yang sesuai Kabot docs/source.

**Step 4: Re-run tests**

Run: `pytest tests/providers/test_registry.py tests/config/test_agent_config.py -q`
Expected: PASS untuk kasus provider registry/schema.

### Task 2: Lengkapi auth menu/manager/wizard mapping

**Files:**
- Modify: `kabot/auth/handlers/simple.py`
- Modify: `kabot/auth/menu.py`
- Modify: `kabot/auth/manager.py`
- Modify: `kabot/cli/setup_wizard.py`
- Test: `tests/auth/test_menu.py`
- Test: `tests/auth/test_manager.py`
- Test: `tests/cli/test_setup_wizard_default_model.py`

**Step 1: Add failing tests for new providers in auth surfaces**

Tambah assertion provider baru muncul di auth menu + manager listing.

**Step 2: Run tests and confirm failure**

Run: `pytest tests/auth/test_menu.py tests/auth/test_manager.py tests/cli/test_setup_wizard_default_model.py -q`
Expected: FAIL pada provider baru.

**Step 3: Implement handlers + alias/mapping updates**

Tambahkan handler API key untuk provider parity baru; update alias mapping dan wizard provider mapping.

**Step 4: Re-run tests**

Run: `pytest tests/auth/test_menu.py tests/auth/test_manager.py tests/cli/test_setup_wizard_default_model.py -q`
Expected: PASS.

### Task 3: Lengkapi static catalog model parity Kabot

**Files:**
- Modify: `kabot/providers/catalog.py`
- Modify: `kabot/providers/model_status.py`
- Test: `tests/providers/test_registry.py`
- Test: `tests/providers/test_model_status.py`

**Step 1: Add failing test coverage for missing model refs**

Tambahkan assertion beberapa model yang sebelumnya missing (together/venice/opencode/kilocode/volcengine-plan/byteplus-plan/synthetic).

**Step 2: Run tests to verify fail state**

Run: `pytest tests/providers/test_registry.py tests/providers/test_model_status.py -q`
Expected: FAIL karena model belum terdaftar.

**Step 3: Implement full model additions**

Tambahkan seluruh model refs parity dari Kabot static catalogs (Together, Venice, HuggingFace static list, Kilo, OpenCode, Volc/BytePlus coding, Moonshot, MiniMax variants, Synthetic, dll) dan update alias penting.

**Step 4: Re-run tests**

Run: `pytest tests/providers/test_registry.py tests/providers/test_model_status.py -q`
Expected: PASS.

### Task 4: Update docs parity (no push)

**Files:**
- Modify: `HOW-TO-USE.md`
- Modify: `CHANGELOG.md`

**Step 1: Add concise parity notes**

Dokumentasikan provider/model parity yang ditambahkan + cara pakai model baru/custom model.

**Step 2: Lint sanity (if available) or manual consistency check**

Run: `rg -n "0.5.7|synthetic|cloudflare-ai-gateway|vercel-ai-gateway|volcengine-plan|byteplus-plan" HOW-TO-USE.md CHANGELOG.md`
Expected: Semua entri dokumentasi ada.

### Task 5: Final verification batch

**Files:**
- Modify if needed: per test failures

**Step 1: Run final targeted suite**

Run: `pytest tests/providers/test_registry.py tests/providers/test_model_status.py tests/auth/test_menu.py tests/auth/test_manager.py tests/cli/test_setup_wizard_default_model.py tests/config/test_agent_config.py -q`
Expected: PASS.

**Step 2: Summarize resulting parity and known limits**

Sajikan ringkasan model/provider yang sekarang sudah match Kabot, serta batasan yang memang depend discovery dinamis provider (mis. HuggingFace dynamic catalog).

