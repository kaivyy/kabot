# Openfang-Style Semantic Routing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor Kabot routing so semantic/contextual intent arbitration runs before deterministic tool forcing, while preserving fast paths for high-confidence operational asks.

**Architecture:** Add a new intent arbitration layer that consumes current text, recent user history, and pending tool context to decide whether a turn should remain chat, continue prior tool context, or force a direct tool. Keep deterministic routing only as a fallback for high-confidence or safety-critical intents.

**Tech Stack:** Python, asyncio, Kabot agent runtime, pytest, existing i18n/runtime status pipeline.

---

### Task 1: Add semantic intent arbitration primitives

**Files:**
- Create: `kabot/agent/semantic_intent.py`
- Test: `tests/agent/test_semantic_intent.py`

**Step 1: Write the failing test**

```python
def test_arbitration_prefers_chat_for_advice_followup():
    result = arbitrate_intent(
        text="sunscreen nya apa yang bagus",
        route_profile="CHAT",
        history=[],
        pending_tool=None,
        last_tool_context=None,
        available_tools={"weather", "stock", "web_search"},
    )
    assert result.intent_type == "advice"
    assert result.candidate_tool is None
    assert result.confidence >= 0.6
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_semantic_intent.py::test_arbitration_prefers_chat_for_advice_followup -v`
Expected: FAIL because `kabot.agent.semantic_intent` does not exist yet.

**Step 3: Write minimal implementation**

```python
@dataclass
class IntentArbitration:
    intent_type: str
    candidate_tool: str | None
    confidence: float
    reason_source: str


def arbitrate_intent(...):
    normalized = _normalize(text)
    if _looks_like_advice_turn(normalized):
        return IntentArbitration("advice", None, 0.72, "semantic")
    return IntentArbitration("unknown", None, 0.0, "semantic")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_semantic_intent.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/semantic_intent.py tests/agent/test_semantic_intent.py
git commit -m "feat: add semantic intent arbitration primitives"
```

### Task 2: Integrate arbitration into message routing before deterministic forcing

**Files:**
- Modify: `kabot/agent/loop_core/message_runtime.py`
- Modify: `kabot/agent/loop_core/tool_enforcement.py`
- Modify: `kabot/agent/loop.py`
- Test: `tests/agent/loop_core/test_message_runtime.py`

**Step 1: Write the failing test**

```python
async def test_meta_complaint_does_not_inherit_stock_tool():
    loop = build_loop_double(
        pending_followup_tool="stock",
        pending_followup_source="MSFT berapa sekarang",
    )
    msg = make_inbound("kenapa jawabnya gitu?")
    response = await process_message(loop, msg)
    assert loop.captured_required_tool is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/loop_core/test_message_runtime.py::test_meta_complaint_does_not_inherit_stock_tool -v`
Expected: FAIL because current follow-up inference still favors stale deterministic tool state.

**Step 3: Write minimal implementation**

```python
arbitration = arbitrate_intent(
    text=effective_content,
    route_profile=str(decision.profile),
    history=conversation_history,
    pending_tool=pending_followup_tool,
    last_tool_context=_get_last_tool_context(session),
    available_tools=_available_tool_names(loop),
)

if arbitration.candidate_tool and arbitration.confidence >= 0.85:
    required_tool = arbitration.candidate_tool
elif arbitration.intent_type in {"chat", "advice", "meta_feedback"}:
    required_tool = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/loop_core/test_message_runtime.py -k "meta_complaint or followup" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/loop_core/message_runtime.py kabot/agent/loop_core/tool_enforcement.py kabot/agent/loop.py tests/agent/loop_core/test_message_runtime.py
git commit -m "refactor: route through semantic arbitration before forced tools"
```

### Task 3: Persist structured last-tool context for follow-ups

**Files:**
- Modify: `kabot/agent/loop_core/execution_runtime.py`
- Modify: `kabot/session/manager.py`
- Test: `tests/agent/loop_core/test_execution_runtime.py`
- Test: `tests/session/test_session_manager.py`

**Step 1: Write the failing test**

```python
async def test_stock_quote_stores_structured_followup_context():
    session = {}
    store_last_tool_context(session, tool="stock", payload={"ticker": "MSFT", "currency": "USD", "price": 410.68})
    assert session["last_tool_context"]["payload"]["ticker"] == "MSFT"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/session/test_session_manager.py::test_stock_quote_stores_structured_followup_context -v`
Expected: FAIL because structured tool context storage does not exist yet.

**Step 3: Write minimal implementation**

```python
def store_last_tool_context(session, *, tool, payload, intent_type=None):
    session["last_tool_context"] = {
        "tool": tool,
        "payload": payload,
        "intent_type": intent_type or tool,
        "ts": time.time(),
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/session/test_session_manager.py tests/agent/loop_core/test_execution_runtime.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/loop_core/execution_runtime.py kabot/session/manager.py tests/session/test_session_manager.py tests/agent/loop_core/test_execution_runtime.py
git commit -m "feat: store structured last-tool context for semantic followups"
```

### Task 4: Use structured context for quote/weather/fx follow-ups

**Files:**
- Modify: `kabot/agent/loop_core/message_runtime.py`
- Modify: `kabot/agent/tools/stock.py`
- Modify: `kabot/agent/tools/weather.py`
- Test: `tests/agent/loop_core/test_message_runtime.py`
- Test: `tests/agent/tools/test_stock.py`
- Test: `tests/tools/test_weather_tool.py`

**Step 1: Write the failing test**

```python
async def test_idr_followup_uses_last_stock_context():
    loop = build_loop_with_last_tool_context(
        tool="stock",
        payload={"ticker": "MSFT", "currency": "USD", "price": 410.68},
    )
    msg = make_inbound("jadikan idr harganya")
    response = await process_message(loop, msg)
    assert loop.captured_required_tool in {"stock", "stock_analysis", None}
    assert "MSFT" in loop.captured_effective_content
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/loop_core/test_message_runtime.py::test_idr_followup_uses_last_stock_context -v`
Expected: FAIL because current follow-up path does not read structured last-tool context.

**Step 3: Write minimal implementation**

```python
last_ctx = _get_last_tool_context(session)
if arbitration.intent_type == "quote_conversion" and last_ctx and last_ctx.get("tool") == "stock":
    effective_content = f"{effective_content}\n\n[Last Tool Context]\n{json.dumps(last_ctx['payload'])}"
    required_tool = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/loop_core/test_message_runtime.py tests/agent/tools/test_stock.py tests/tools/test_weather_tool.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/loop_core/message_runtime.py kabot/agent/tools/stock.py kabot/agent/tools/weather.py tests/agent/loop_core/test_message_runtime.py tests/agent/tools/test_stock.py tests/tools/test_weather_tool.py
git commit -m "feat: continue quote and weather followups from structured tool context"
```

### Task 5: Unify skill/API preflight with semantic routing contract

**Files:**
- Modify: `kabot/agent/tools/image_gen.py`
- Modify: `kabot/agent/loop_core/execution_runtime.py`
- Modify: `kabot/i18n/catalog.py`
- Test: `tests/agent/tools/test_image_gen.py`
- Test: `tests/agent/loop_core/test_execution_runtime.py`

**Step 1: Write the failing test**

```python
def test_image_generation_missing_key_returns_clear_setup_error():
    result = image_tool.execute({"prompt": "buat gambar mobil di hutan"})
    assert result.is_error is True
    assert "api key" in result.content.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/tools/test_image_gen.py::test_image_generation_missing_key_returns_clear_setup_error -v`
Expected: FAIL if the runtime still returns generic or inconsistent error text.

**Step 3: Write minimal implementation**

```python
if not api_key:
    return ToolResult(
        is_error=True,
        content=t("tool.image_generate.missing_api_key", locale=runtime_locale, text=prompt),
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/tools/test_image_gen.py tests/agent/loop_core/test_execution_runtime.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/tools/image_gen.py kabot/agent/loop_core/execution_runtime.py kabot/i18n/catalog.py tests/agent/tools/test_image_gen.py tests/agent/loop_core/test_execution_runtime.py
git commit -m "fix: normalize semantic skill preflight errors"
```

### Task 6: Update docs and regression matrix

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/LOCAL_PYPI_RELEASE_REMINDER.md`
- Test: `tests/utils/test_doctor_matrix.py`

**Step 1: Write the failing test**

```python
def test_doctor_routing_matrix_includes_semantic_first_regressions():
    report = doctor.run_routing_diagnostic()
    assert "semantic_followups" in report["routing"]["sections"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/utils/test_doctor_matrix.py::test_doctor_routing_matrix_includes_semantic_first_regressions -v`
Expected: FAIL because the routing diagnostic does not include the new regression bucket yet.

**Step 3: Write minimal implementation**

```python
report["routing"]["sections"]["semantic_followups"] = {
    "cases": [...],
}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/utils/test_doctor_matrix.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add README.md CHANGELOG.md docs/LOCAL_PYPI_RELEASE_REMINDER.md tests/utils/test_doctor_matrix.py
git commit -m "docs: document semantic-first routing behavior"
```

### Task 7: Final verification

**Files:**
- Verify: `tests/agent`
- Verify: `tests/cli`
- Verify: `tests/providers`
- Verify: `tests/memory`

**Step 1: Run focused regression suites**

Run: `pytest -q tests/agent/loop_core tests/agent/tools tests/session`
Expected: PASS

**Step 2: Run broader suites**

Run: `pytest -q tests/agent tests/cli tests/providers tests/memory`
Expected: PASS

**Step 3: Run live probes**

Run:

```bash
python -m kabot agent -m "saham Microsoft berapa"
python -m kabot agent -m "sunscreen yang bagus buat cuaca panas apa ya?"
python -m kabot agent -m "dibandung berangin ga sekarang?"
```

Expected:
- stock prompt answers stock
- advice prompt stays advice, not web/search stock
- weather follow-up stays weather

**Step 4: Verify docs updated**

Run: `git diff -- README.md CHANGELOG.md docs/LOCAL_PYPI_RELEASE_REMINDER.md`
Expected: semantic-first routing behavior documented

**Step 5: Commit**

```bash
git add .
git commit -m "feat: shift kabot toward semantic-first routing"
```
