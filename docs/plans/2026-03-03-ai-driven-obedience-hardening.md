# AI-Driven Obedience Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Kabot more AI-driven but evidence-based: tool/skill execution follows user intent, responses avoid premature/imagined completion claims, and multilingual skill matching works beyond Indonesian.

**Architecture:** Keep existing balanced routing (required-tool intents force tool path), then harden two critical boundaries: (1) direct-tool and pre-tool response behavior in `execution_runtime`, and (2) skill matching quality + deterministic test isolation in `skills` tests. Use strict TDD per change so each behavior shift is explicitly proven.

**Tech Stack:** Python 3, pytest, existing AgentLoop runtime (`loop_core`), SkillsLoader (`kabot/agent/skills.py`), no new external dependencies.

---

### Task 1: Prevent premature “done” claims before tool output exists

**Files:**
- Modify: `tests/agent/loop_core/test_execution_runtime.py`
- Modify: `kabot/agent/loop_core/execution_runtime.py`

**Step 1: Write the failing test**

Add a test that proves tool-call responses must send neutral progress text, not model-completion text, before tool output is executed.

```python
@pytest.mark.asyncio
async def test_run_agent_loop_uses_neutral_status_when_tool_calls_have_completion_text():
    bus = SimpleNamespace(publish_outbound=AsyncMock(return_value=None))
    first = LLMResponse(
        content="Cleanup selesai total",
        tool_calls=[ToolCallRequest(id="call_1", name="cleanup_system", arguments={"level": "standard"})],
    )
    second = LLMResponse(content="Tool finished", tool_calls=[])

    loop = SimpleNamespace(
        max_iterations=2,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _call_llm_with_fallback=AsyncMock(side_effect=[(first, None), (second, None)]),
        _self_evaluate=lambda _q, _a: (True, None),
        _critic_evaluate=AsyncMock(return_value=(10, "ok")),
        _log_lesson=AsyncMock(),
        _process_tool_calls=AsyncMock(side_effect=lambda _msg, msgs, _resp, _sess: msgs),
        context=SimpleNamespace(add_assistant_message=lambda msgs, content, reasoning_content=None: msgs + [{"role": "assistant", "content": content}]),
        context_guard=SimpleNamespace(check_overflow=lambda _m, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _is_weak_model=lambda _model: False,
        bus=bus,
    )

    msg = InboundMessage(channel="cli", chat_id="direct", sender_id="user", content="tolong bersihkan cache")
    session = SimpleNamespace(metadata={})

    await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    outbound_texts = [call.args[0].content for call in bus.publish_outbound.await_args_list]
    assert "Cleanup selesai total" not in outbound_texts
    assert "Processing your request, please wait..." in outbound_texts
```

**Step 2: Run test to verify it fails**

Run: `pytest -q tests/agent/loop_core/test_execution_runtime.py -k neutral_status_when_tool_calls`

Expected: **FAIL** (current runtime may forward model content before tool execution).

**Step 3: Write minimal implementation**

In `run_agent_loop(...)`, replace pre-tool status emission logic with a neutral status for any `response.has_tool_calls`.

```python
# before processing tool calls
if response.has_tool_calls:
    display_content = "Processing your request, please wait..."
    if display_content not in status_updates_sent:
        status_updates_sent.add(display_content)
        await loop.bus.publish_outbound(
            OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=display_content)
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest -q tests/agent/loop_core/test_execution_runtime.py -k neutral_status_when_tool_calls`

Expected: **PASS**.

**Step 5: Commit**

```bash
git add tests/agent/loop_core/test_execution_runtime.py kabot/agent/loop_core/execution_runtime.py
git commit -m "fix: avoid pre-tool completion claims in status updates"
```

---

### Task 2: For mutating direct tools, return raw tool output (no LLM re-summary)

**Files:**
- Modify: `tests/agent/loop_core/test_execution_runtime.py`
- Modify: `kabot/agent/loop_core/execution_runtime.py`

**Step 1: Write the failing test**

Add test to prove `cleanup_system` direct path returns raw tool result and does not call summary LLM.

```python
@pytest.mark.asyncio
async def test_run_agent_loop_cleanup_direct_path_returns_raw_result_without_summary():
    provider = SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="hallucinated summary")))
    loop = SimpleNamespace(
        max_iterations=1,
        provider=provider,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "cleanup_system",
        _execute_required_tool_fallback=AsyncMock(return_value="Cleanup failed: permission denied"),
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _is_weak_model=lambda _model: False,
        context_guard=SimpleNamespace(check_overflow=lambda _m, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
    )

    msg = InboundMessage(channel="cli", chat_id="direct", sender_id="user", content="cleanup disk sekarang")
    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], SimpleNamespace(metadata={}))

    assert result == "Cleanup failed: permission denied"
    provider.chat.assert_not_awaited()
```

**Step 2: Run test to verify it fails**

Run: `pytest -q tests/agent/loop_core/test_execution_runtime.py -k cleanup_direct_path_returns_raw_result`

Expected: **FAIL** (current code tries to summarize direct result via LLM).

**Step 3: Write minimal implementation**

In `run_agent_loop(...)`, add a mutating direct-tool set and bypass LLM summary for those tools.

```python
_DIRECT_TOOLS = {"get_process_memory", "get_system_info", "cleanup_system", "weather", "speedtest", "stock", "crypto", "server_monitor"}
_MUTATING_DIRECT_TOOLS = {"cleanup_system"}

...
if required_tool and required_tool in _DIRECT_TOOLS:
    direct_result = await loop._execute_required_tool_fallback(required_tool, msg)
    if direct_result is not None:
        if required_tool in _MUTATING_DIRECT_TOOLS:
            return direct_result
        # existing optional summary path for read-only tools
```

**Step 4: Run test to verify it passes**

Run: `pytest -q tests/agent/loop_core/test_execution_runtime.py -k cleanup_direct_path_returns_raw_result`

Expected: **PASS**.

**Step 5: Commit**

```bash
git add tests/agent/loop_core/test_execution_runtime.py kabot/agent/loop_core/execution_runtime.py
git commit -m "fix: return raw cleanup tool output to prevent summary hallucination"
```

---

### Task 3: Improve skill matching obedience for multilingual and explicit skill requests

**Files:**
- Modify: `tests/agent/test_skills_matching.py`
- Modify: `kabot/agent/skills.py`

**Step 1: Write the failing tests**

Add tests for Thai keyword extraction and explicit skill-name prioritization.

```python
def _write_skill(skill_root: Path, skill_name: str, body: str) -> None:
    skill_dir = skill_root / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: test skill\n---\n\n{body}\n",
        encoding="utf-8",
    )


def test_match_skills_supports_thai_keywords(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(workspace / "skills", "cleanup-th", "ล้างแคช ดิสก์ ลบไฟล์ชั่วคราว")

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    matches = loader.match_skills("ช่วยล้างแคชดิสก์ให้หน่อย", profile="GENERAL")

    assert any(m.startswith("cleanup-th") for m in matches)


def test_match_skills_prioritizes_explicit_skill_name(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    builtin = tmp_path / "builtin"
    builtin.mkdir(parents=True, exist_ok=True)

    _write_skill(workspace / "skills", "clawra-selfie", "generate selfie image")
    _write_skill(workspace / "skills", "generic-image", "generate image")

    loader = SkillsLoader(workspace=workspace, builtin_skills_dir=builtin)
    matches = loader.match_skills("please use clawra-selfie skill now", profile="GENERAL")

    assert matches
    assert matches[0].startswith("clawra-selfie")
```

**Step 2: Run tests to verify they fail**

Run: `pytest -q tests/agent/test_skills_matching.py -k "thai_keywords or explicit_skill_name"`

Expected: **FAIL**.

**Step 3: Write minimal implementation**

Update keyword extraction regex in `kabot/agent/skills.py` to include Thai Unicode block and add explicit-name score boost in `match_skills(...)`.

```python
# _extract_keywords
words = re.findall(r"[a-zA-Z\u00C0-\u024F\u0400-\u04FF\u0E00-\u0E7F\u3000-\u9FFF\uAC00-\uD7AF]{2,}", text.lower())

# match_skills
message_lower = message.lower()
...
if re.search(rf"(?<![\w-]){re.escape(skill_name.lower())}(?![\w-])", message_lower):
    score += 5.0
```

**Step 4: Run tests to verify they pass**

Run: `pytest -q tests/agent/test_skills_matching.py`

Expected: **PASS**.

**Step 5: Commit**

```bash
git add tests/agent/test_skills_matching.py kabot/agent/skills.py
git commit -m "feat: improve multilingual and explicit-name skill matching"
```

---

### Task 4: Make skills tests deterministic by isolating HOME from host-local skills

**Files:**
- Modify: `tests/agent/test_skills_matching.py`

**Step 1: Write/adjust failing regression test**

Ensure the existing regression test does not depend on host `~/.kabot/skills` by explicitly monkeypatching `Path.home()` to a temp home.

```python
def test_match_skills_does_not_auto_load_irrelevant_tool_skills(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kabot.agent.skills.Path.home", lambda: fake_home)

    loader = SkillsLoader(Path("."))
    matches = loader.match_skills("jadi tools mu yang bermasalah?", profile="GENERAL")

    assert "mcporter" not in matches
    assert "sherpa-onnx-tts" not in matches
```

**Step 2: Run test to verify deterministic behavior**

Run: `pytest -q tests/agent/test_skills_matching.py -k irrelevant_tool_skills`

Expected: **PASS** consistently regardless of host-local skills.

**Step 3: No production-code change (YAGNI)**

Keep this as test-harness hardening only.

**Step 4: Re-run skills suite**

Run: `pytest -q tests/agent/test_skills_loader_precedence.py tests/agent/test_skills_matching.py tests/agent/test_skills_entries_semantics.py tests/agent/test_skills_requirements_os.py`

Expected: **All PASS**.

**Step 5: Commit**

```bash
git add tests/agent/test_skills_matching.py
git commit -m "test: isolate skill matching tests from host home contamination"
```

---

### Task 5: Final verification matrix (no completion claim without evidence)

**Files:**
- Test-only execution (no file edits expected)

**Step 1: Tool enforcement + multilingual routing**

Run: `pytest -q tests/agent/test_tool_enforcement.py`

Expected: **PASS**.

**Step 2: Runtime behavior (agent loop core)**

Run: `pytest -q tests/agent/loop_core/test_execution_runtime.py tests/agent/loop_core/test_message_runtime.py`

Expected: **PASS**.

**Step 3: Runtime guard regressions**

Run: `pytest -q tests/agent/test_tool_runtime_guards.py`

Expected: **PASS**.

**Step 4: Skills behavior and precedence**

Run: `pytest -q tests/agent/test_skills_loader_precedence.py tests/agent/test_skills_matching.py tests/agent/test_skills_entries_semantics.py tests/agent/test_skills_requirements_os.py`

Expected: **PASS**.

**Step 5: Commit verification result (if all green)**

```bash
git add tests/agent/loop_core/test_execution_runtime.py tests/agent/test_tool_runtime_guards.py
git commit -m "test: verify balanced tool-first and skills determinism hardening"
```

If any command fails, stop and return to the corresponding task’s RED step.
