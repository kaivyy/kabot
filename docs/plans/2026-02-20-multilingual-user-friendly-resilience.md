# Multilingual User-Friendly Resilience Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Kabot fully multilingual (no hardcoded Indonesian for user-facing system outputs) and resilient against OpenClaw-style complexity/tool-calling failures while staying lightweight.

**Architecture:** Introduce a centralized i18n layer (locale detection + catalog + formatter), route all deterministic fallback/system outputs through that layer, and consolidate multilingual intent lexicon so behavior is consistent across routing, enforcement, and cron NLP. Add strict tool-calling guardrails plus cron resource policies (dedup, limits, grouping) to keep UX reliable and runtime lightweight even with many bots/jobs.

**Tech Stack:** Python 3.13, pytest, existing Kabot agent loop modules, cron service core, setup wizard, rich/questionary CLI.

---

### Task 0: Preflight Workspace and Baseline Snapshot

**Files:**
- Create: `docs/plans/2026-02-20-multilingual-user-friendly-resilience.md` (this file)
- Modify: none
- Test: none

**Step 1: Confirm clean execution baseline**

```bash
git status --short
```

**Step 2: Capture baseline targeted tests**

Run: `pytest tests/agent/test_fallback_i18n.py tests/agent/test_tool_enforcement.py tests/agent/test_cron_fallback_nlp.py tests/tools/test_weather_tool.py -q`  
Expected: Current baseline passes (or known failures documented before code changes).

**Step 3: Record baseline observations in working notes**

```text
Baseline notes:
- Existing fallback_i18n has mixed language markers.
- Cron actions return hardcoded English strings.
- Multiple modules duplicate multilingual keywords.
```

**Step 4: Commit prep note (optional)**

```bash
git add docs/plans/2026-02-20-multilingual-user-friendly-resilience.md
git commit -m "docs: add multilingual resilience implementation plan"
```

### Task 1: Add Central i18n Core (Catalog + Locale Resolver)

**Files:**
- Create: `kabot/i18n/catalog.py`
- Create: `kabot/i18n/locale.py`
- Create: `kabot/i18n/__init__.py`
- Modify: `kabot/agent/fallback_i18n.py`
- Test: `tests/agent/test_fallback_i18n.py`
- Test: `tests/agent/test_i18n_locale.py`

**Step 1: Write the failing tests**

```python
from kabot.i18n.locale import detect_locale
from kabot.i18n.catalog import tr

def test_detect_locale_defaults_to_en():
    assert detect_locale("") == "en"

def test_detect_locale_for_malay():
    assert detect_locale("tolong set peringatan esok") == "ms"

def test_catalog_falls_back_to_english_key():
    assert "location" in tr("weather.need_location", locale="de")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_i18n_locale.py -q`  
Expected: FAIL with import/module errors for new i18n modules.

**Step 3: Write minimal implementation**

```python
# kabot/i18n/locale.py
from __future__ import annotations
import re

THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
CJK_RE = re.compile(r"[\u4E00-\u9FFF]")

def detect_locale(text: str | None) -> str:
    s = (text or "").strip().lower()
    if not s:
        return "en"
    if THAI_RE.search(s):
        return "th"
    if CJK_RE.search(s):
        return "zh"
    if any(k in s for k in ("jadual", "peringatan", "minit", "esok")):
        return "ms"
    if any(k in s for k in ("ingatkan", "jadwal", "pengingat", "besok")):
        return "id"
    return "en"
```

```python
# kabot/i18n/catalog.py
from __future__ import annotations
from kabot.i18n.locale import detect_locale

MESSAGES = {
    "en": {"weather.need_location": "I need a location to check weather."},
    "id": {"weather.need_location": "Saya butuh lokasi untuk cek cuaca."},
    "ms": {"weather.need_location": "Saya perlukan lokasi untuk semak cuaca."},
    "th": {"weather.need_location": "Please provide a location to check weather."},
    "zh": {"weather.need_location": "请提供要查询天气的地点。"},
}

def tr(key: str, *, locale: str | None = None, text: str | None = None, **kwargs: object) -> str:
    lang = locale or detect_locale(text)
    template = MESSAGES.get(lang, {}).get(key) or MESSAGES["en"].get(key) or key
    return template.format(**kwargs) if kwargs else template
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/agent/test_i18n_locale.py tests/agent/test_fallback_i18n.py -q`  
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/i18n kabot/agent/fallback_i18n.py tests/agent/test_i18n_locale.py tests/agent/test_fallback_i18n.py
git commit -m "feat(i18n): add centralized locale detection and translation catalog"
```

### Task 2: Replace Hardcoded Fallback Strings with i18n Keys

**Files:**
- Modify: `kabot/agent/fallback_i18n.py`
- Modify: `kabot/agent/loop_core/tool_enforcement.py`
- Test: `tests/agent/test_tool_enforcement.py`
- Test: `tests/agent/test_fallback_i18n.py`

**Step 1: Write the failing test**

```python
def test_tool_enforcement_uses_english_for_english_prompt(agent_loop):
    # "remove reminder" path should return EN fallback without Indonesian words.
    ...
    assert "provide `group_id`" in output.lower()
    assert "jadwal" not in output.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_tool_enforcement.py::test_tool_enforcement_uses_english_for_english_prompt -q`  
Expected: FAIL because old fallback text leaks non-target language.

**Step 3: Write minimal implementation**

```python
# tool_enforcement.py
from kabot.i18n.catalog import tr
...
if not location:
    return tr("weather.need_location", text=msg.content)
...
return tr("cron.remove.need_selector", text=msg.content)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_tool_enforcement.py tests/agent/test_fallback_i18n.py -q`  
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/agent/fallback_i18n.py kabot/agent/loop_core/tool_enforcement.py tests/agent/test_tool_enforcement.py tests/agent/test_fallback_i18n.py
git commit -m "refactor(i18n): route fallback/tool-enforcement messages through translation keys"
```

### Task 3: Unify Multilingual Intent Lexicon (Router + Cron NLP + Quality Runtime)

**Files:**
- Create: `kabot/agent/language/lexicon.py`
- Modify: `kabot/agent/cron_fallback_nlp.py`
- Modify: `kabot/agent/router.py`
- Modify: `kabot/agent/loop_core/quality_runtime.py`
- Test: `tests/agent/test_cron_fallback_nlp.py`
- Test: `tests/agent/test_tool_enforcement.py`
- Test: `tests/agent/test_router.py`
- Create: `tests/agent/test_multilingual_lexicon.py`

**Step 1: Write the failing tests**

```python
from kabot.agent.language.lexicon import REMINDER_TERMS, WEATHER_TERMS

def test_lexicon_has_non_indonesian_terms():
    assert "remind" in REMINDER_TERMS
    assert "提 醒".replace(" ", "") in REMINDER_TERMS
    assert "天气" in WEATHER_TERMS
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_multilingual_lexicon.py -q`  
Expected: FAIL (new module missing).

**Step 3: Write minimal implementation**

```python
# kabot/agent/language/lexicon.py
REMINDER_TERMS = (
    "remind", "reminder", "schedule", "alarm",
    "ingatkan", "pengingat", "jadwalkan",
    "peringatan", "jadual",
    "เตือน",
    "提醒", "日程", "闹钟",
)
WEATHER_TERMS = (
    "weather", "temperature", "forecast",
    "cuaca", "suhu",
    "ramalan",
    "อากาศ", "อุณหภูมิ",
    "天气", "气温", "温度", "预报",
)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/agent/test_multilingual_lexicon.py tests/agent/test_router.py tests/agent/test_cron_fallback_nlp.py -q`  
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/agent/language/lexicon.py kabot/agent/cron_fallback_nlp.py kabot/agent/router.py kabot/agent/loop_core/quality_runtime.py tests/agent/test_multilingual_lexicon.py tests/agent/test_router.py tests/agent/test_cron_fallback_nlp.py
git commit -m "refactor(language): centralize multilingual lexicon across router and fallback layers"
```

### Task 4: Make Cron Action Responses Fully Localized and Human-Friendly

**Files:**
- Modify: `kabot/agent/tools/cron_ops/actions.py`
- Modify: `kabot/agent/tools/cron.py`
- Modify: `kabot/i18n/catalog.py`
- Test: `tests/cron/test_cron_tool.py`
- Test: `tests/agent/test_tool_enforcement.py`

**Step 1: Write the failing tests**

```python
def test_cron_add_message_follows_user_language(cron_tool):
    cron_tool.set_context("telegram", "123")
    out = run_async(cron_tool.execute(action="add", message="drink water", every_seconds=3600, context_text="please remind me"))
    assert "Created job" in out
    assert "jadwal" not in out.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cron/test_cron_tool.py::test_cron_add_message_follows_user_language -q`  
Expected: FAIL because action handlers still return static strings.

**Step 3: Write minimal implementation**

```python
# actions.py
from kabot.i18n.catalog import tr

def _msg(key: str, text: str | None = None, **kwargs: object) -> str:
    return tr(key, text=text, **kwargs)

...
if not message:
    return _msg("cron.add.error_message_required", context_text)
...
return _msg("cron.add.created", context_text, name=job.name, job_id=job.id)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/cron/test_cron_tool.py tests/agent/test_tool_enforcement.py -q`  
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/agent/tools/cron_ops/actions.py kabot/agent/tools/cron.py kabot/i18n/catalog.py tests/cron/test_cron_tool.py tests/agent/test_tool_enforcement.py
git commit -m "feat(cron): localize cron action responses with user-language aware templates"
```

### Task 5: Strengthen Tool-Calling Reliability (Anti-Hallucination Guardrail)

**Files:**
- Create: `kabot/agent/loop_core/tool_runtime.py`
- Modify: `kabot/agent/loop_core/message_runtime.py`
- Modify: `kabot/agent/loop_core/tool_enforcement.py`
- Modify: `kabot/agent/loop_core/execution_runtime.py`
- Test: `tests/agent/test_tool_runtime_guards.py`
- Test: `tests/agent/test_tool_enforcement.py`

**Step 1: Write the failing tests**

```python
async def test_required_tool_query_never_returns_text_only_when_tool_available(agent_loop):
    # Simulate model returns plain text twice for weather query.
    # Expect deterministic fallback execution on final attempt.
    ...
    assert tool_execute_mock.await_count >= 1
    assert "cilacap" in final_output.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_tool_runtime_guards.py -q`  
Expected: FAIL (new runtime guard not implemented).

**Step 3: Write minimal implementation**

```python
# tool_runtime.py
async def enforce_required_tool(loop, required_tool: str, msg):
    # 1) If model produced tool call -> continue normal path.
    # 2) After retry budget exhausted -> run deterministic fallback directly.
    # 3) Return tool result string, never empty confirmation text.
    return await execute_required_tool_fallback(loop, required_tool, msg)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/agent/test_tool_runtime_guards.py tests/agent/test_tool_enforcement.py -q`  
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/agent/loop_core/tool_runtime.py kabot/agent/loop_core/message_runtime.py kabot/agent/loop_core/tool_enforcement.py kabot/agent/loop_core/execution_runtime.py tests/agent/test_tool_runtime_guards.py tests/agent/test_tool_enforcement.py
git commit -m "feat(agent): add strict tool-calling guardrail with deterministic execution fallback"
```

### Task 6: Improve Weather Accuracy Transparency and Care Advice

**Files:**
- Modify: `kabot/agent/tools/weather.py`
- Modify: `kabot/i18n/catalog.py`
- Test: `tests/tools/test_weather_tool.py`

**Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_weather_response_includes_source_and_observation_context(monkeypatch):
    ...
    assert "source:" in result.lower()

@pytest.mark.asyncio
async def test_weather_advice_matches_hot_condition(monkeypatch):
    ...
    assert "sunscreen" in result.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_weather_tool.py::test_weather_response_includes_source_and_observation_context -q`  
Expected: FAIL because source metadata is not currently emitted.

**Step 3: Write minimal implementation**

```python
# weather.py
async def fetch_openmeteo(location: str) -> str | None:
    ...
    return f"{city_name}: {condition} +{temp}C\nSource: Open-Meteo (current_weather)"
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_weather_tool.py -q`  
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/agent/tools/weather.py kabot/i18n/catalog.py tests/tools/test_weather_tool.py
git commit -m "feat(weather): add source transparency and localized practical care advice"
```

### Task 7: Add Cron Lightweight Policies (Dedup + Limits + Grouping Safety)

**Files:**
- Create: `kabot/cron/policies.py`
- Modify: `kabot/cron/service.py`
- Modify: `kabot/agent/tools/cron_ops/actions.py`
- Modify: `kabot/config/schema.py`
- Test: `tests/cron/test_resource_policies.py`
- Test: `tests/cron/test_service_facade.py`

**Step 1: Write the failing tests**

```python
def test_cron_rejects_duplicate_one_shot_with_same_target_and_time(cron_service):
    ...
    assert second_result.startswith("Error:")

def test_cron_enforces_max_jobs_per_destination(cron_service):
    ...
    assert "limit" in result.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cron/test_resource_policies.py -q`  
Expected: FAIL (policy layer absent).

**Step 3: Write minimal implementation**

```python
# policies.py
MAX_JOBS_PER_DESTINATION_DEFAULT = 300

def is_duplicate(existing_jobs, candidate) -> bool:
    ...

def check_capacity(existing_jobs, channel: str, to: str, limit: int) -> bool:
    ...
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/cron/test_resource_policies.py tests/cron/test_service_facade.py -q`  
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/cron/policies.py kabot/cron/service.py kabot/agent/tools/cron_ops/actions.py kabot/config/schema.py tests/cron/test_resource_policies.py tests/cron/test_service_facade.py
git commit -m "feat(cron): add lightweight dedup and capacity policies for scalable scheduling"
```

### Task 8: Setup Wizard Productization (Simple Mode First, Advanced Optional)

**Files:**
- Modify: `kabot/cli/setup_wizard.py`
- Modify: `kabot/cli/fleet_templates.py`
- Modify: `docs/multi-agent.md`
- Modify: `docs/ROADMAP.md`
- Test: `tests/cli/test_setup_wizard_freedom_mode.py`
- Test: `tests/cli/test_setup_wizard_channel_instances.py`
- Test: `tests/cli/test_setup_wizard_environment.py`

**Step 1: Write the failing tests**

```python
def test_setup_wizard_simple_mode_hides_advanced_cron_knobs(...):
    ...
    assert "Simple Mode" in rendered
    assert "cron_expr" not in rendered

def test_setup_wizard_simple_mode_supports_multi_bot_binding(...):
    ...
    assert instance.agent_binding == "agent-a"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_setup_wizard_freedom_mode.py::test_setup_wizard_simple_mode_hides_advanced_cron_knobs -q`  
Expected: FAIL (simple mode flow not present).

**Step 3: Write minimal implementation**

```python
# setup_wizard.py
wizard_mode = ClackUI.clack_select(
    "Setup Mode",
    choices=["Simple (Recommended)", "Advanced"],
)
if wizard_mode.startswith("Simple"):
    self._run_simple_flow()
else:
    self._run_advanced_flow()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/cli/test_setup_wizard_freedom_mode.py tests/cli/test_setup_wizard_channel_instances.py tests/cli/test_setup_wizard_environment.py -q`  
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/cli/setup_wizard.py kabot/cli/fleet_templates.py docs/multi-agent.md docs/ROADMAP.md tests/cli/test_setup_wizard_freedom_mode.py tests/cli/test_setup_wizard_channel_instances.py tests/cli/test_setup_wizard_environment.py
git commit -m "feat(wizard): add simple-first setup flow with advanced opt-in and multi-bot clarity"
```

### Task 9: Integration Verification and Documentation Updates

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/OPENCLAW_VS_KABOT_COMPLETE_ANALYSIS.md`
- Create: `docs/trouble/multilingual-and-tool-reliability.md`
- Test: `tests/agent/test_tool_enforcement.py`
- Test: `tests/tools/test_weather_tool.py`
- Test: `tests/cron/test_cron_tool.py`
- Test: `tests/cli/test_setup_wizard_channel_instances.py`

**Step 1: Write final regression checklist test command**

```bash
pytest tests/agent/test_fallback_i18n.py tests/agent/test_tool_enforcement.py tests/agent/test_cron_fallback_nlp.py tests/tools/test_weather_tool.py tests/cron/test_cron_tool.py tests/cron/test_resource_policies.py tests/cli/test_setup_wizard_channel_instances.py -q
```

**Step 2: Run test to verify all pass**

Run: the command above  
Expected: PASS, no regression in reminder/weather/tool enforcement flows.

**Step 3: Write docs updates**

```markdown
# README.md (new section)
- Multilingual deterministic fallback behavior
- Tool-calling reliability guarantees
- Lightweight cron policy defaults
```

**Step 4: Update changelog and analysis doc**

```markdown
- Added centralized i18n catalog and locale resolver.
- Removed hardcoded language from fallback/system outputs.
- Added cron dedup and per-destination limits.
- Added simple-first setup wizard mode.
```

**Step 5: Commit**

```bash
git add README.md CHANGELOG.md docs/OPENCLAW_VS_KABOT_COMPLETE_ANALYSIS.md docs/trouble/multilingual-and-tool-reliability.md
git commit -m "docs: publish multilingual reliability architecture and verification results"
```

## Execution Rules for Implementer

- Use `@test-driven-development` for every task above.
- Use `@systematic-debugging` for any failing or flaky test.
- Use `@verification-before-completion` before claiming done.
- Keep commits small and task-scoped; do not batch unrelated changes.
- Keep runtime lightweight: prefer grouped schedules and heartbeat batching over creating many isolated periodic jobs.

