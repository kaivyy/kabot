# Kabot Parity: AI-as-Developer Backend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close all remaining gaps between Kabot and Kabot's AI-as-Developer backend, making Kabot 100% AI-driven with the same level of sophistication.

**Architecture:** 6 new modules will be added to Kabot mirroring Kabot's approach â€” context compaction, context window guard, tool loop detection, tool policy profiles, failover error classification, and session tool result guard. Each is a standalone module wired into the existing agent loop.

**Tech Stack:** Python 3.11+, asyncio, existing Kabot agent loop / hook system / resilience layer

---

## Revised Gap Analysis (after deep source-code read)

| # | Feature | Kabot Source | Kabot Status | Priority |
|---|---------|----------------|-------------|----------|
| 1 | Context Compaction | `compaction.ts` (390 lines) | âŒ Missing | **P0** |
| 2 | Context Window Guard | `context-window-guard.ts` (75 lines) | âŒ Missing | **P0** |
| 3 | Tool Loop Detection | `tool-loop-detection.ts` (624 lines) | âŒ Missing | **P1** |
| 4 | Tool Policy Profiles | `tool-policy.ts` (313 lines) | âŒ Missing | **P1** |
| 5 | Failover Error Classification | `failover-error.ts` (241 lines) | âš ï¸ Partial | **P2** |
| 6 | Session Tool Result Guard | `session-tool-result-guard.ts` (253 lines) | âš ï¸ Partial | **P2** |

---

## Task 1: Context Window Guard

**Files:**
- Create: `kabot/agent/loop_core/context_guard.py`
- Test: `tests/test_context_guard.py`

**What it does:** Evaluates if the current model's context window is too small (hard block < 16K tokens, warn < 32K). Prevents crashes from models with tiny context windows.

**Step 1: Write failing tests**

```python
# tests/test_context_guard.py
import pytest
from kabot.agent.loop_core.context_guard import (
    ContextWindowInfo,
    evaluate_context_window_guard,
    resolve_context_window_info,
    HARD_MIN_TOKENS,
    WARN_BELOW_TOKENS,
)


def test_guard_blocks_below_hard_min():
    info = ContextWindowInfo(tokens=8000, source="default")
    result = evaluate_context_window_guard(info)
    assert result.should_block is True


def test_guard_warns_below_threshold():
    info = ContextWindowInfo(tokens=20000, source="model")
    result = evaluate_context_window_guard(info)
    assert result.should_warn is True
    assert result.should_block is False


def test_guard_passes_large_context():
    info = ContextWindowInfo(tokens=128000, source="model")
    result = evaluate_context_window_guard(info)
    assert result.should_warn is False
    assert result.should_block is False


def test_resolve_from_model_context():
    info = resolve_context_window_info(
        model_context_window=128000,
        default_tokens=8192,
    )
    assert info.tokens == 128000
    assert info.source == "model"


def test_resolve_falls_back_to_default():
    info = resolve_context_window_info(default_tokens=8192)
    assert info.tokens == 8192
    assert info.source == "default"
```

**Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_context_guard.py -v`
Expected: FAIL (module not found)

**Step 3: Implement context guard**

```python
# kabot/agent/loop_core/context_guard.py
"""Context window size guard â€” prevents crashes from undersized models."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

HARD_MIN_TOKENS = 16_000
WARN_BELOW_TOKENS = 32_000

Source = Literal["model", "config", "default"]


@dataclass
class ContextWindowInfo:
    tokens: int
    source: Source


@dataclass
class ContextWindowGuardResult(ContextWindowInfo):
    should_warn: bool = False
    should_block: bool = False


def resolve_context_window_info(
    *,
    model_context_window: int | None = None,
    config_context_tokens: int | None = None,
    default_tokens: int = 8192,
) -> ContextWindowInfo:
    if config_context_tokens and config_context_tokens > 0:
        return ContextWindowInfo(tokens=config_context_tokens, source="config")
    if model_context_window and model_context_window > 0:
        return ContextWindowInfo(tokens=model_context_window, source="model")
    return ContextWindowInfo(tokens=default_tokens, source="default")


def evaluate_context_window_guard(
    info: ContextWindowInfo,
    *,
    warn_below: int = WARN_BELOW_TOKENS,
    hard_min: int = HARD_MIN_TOKENS,
) -> ContextWindowGuardResult:
    tokens = max(0, info.tokens)
    return ContextWindowGuardResult(
        tokens=tokens,
        source=info.source,
        should_warn=0 < tokens < warn_below,
        should_block=0 < tokens < hard_min,
    )
```

**Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_context_guard.py -v`
Expected: ALL PASS

**Step 5: Wire into agent loop**

Modify: `kabot/agent/loop_core/execution_runtime.py`
â€” In `run_agent_loop()`, before calling `call_llm_with_fallback()`, call `evaluate_context_window_guard()` and log warning or return early if blocked.

**Step 6: Commit**

```bash
git add kabot/agent/loop_core/context_guard.py tests/test_context_guard.py
git commit -m "feat: add context window guard (Kabot parity)"
```

---

## Task 2: Context Compaction (Auto-Summarization on Overflow)

**Files:**
- Create: `kabot/agent/loop_core/compaction.py`
- Test: `tests/test_compaction.py`
- Modify: `kabot/agent/loop_core/execution_runtime.py`

**What it does:** When context window overflows, automatically summarizes older messages into a compressed summary instead of crashing. Uses the LLM itself to generate summaries (just like Kabot uses `generateSummary()`).

**Step 1: Write failing tests**

```python
# tests/test_compaction.py
import pytest
from kabot.agent.loop_core.compaction import (
    estimate_tokens,
    split_messages_by_token_share,
    prune_history_for_context,
)


def test_estimate_tokens_basic():
    assert estimate_tokens("hello world") > 0


def test_estimate_tokens_list():
    msgs = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    total = estimate_tokens(msgs)
    assert total > 0


def test_split_messages_two_parts():
    msgs = [{"role": "user", "content": f"Msg {i}"} for i in range(10)]
    parts = split_messages_by_token_share(msgs, num_parts=2)
    assert len(parts) == 2
    assert sum(len(p) for p in parts) == 10


def test_prune_drops_oldest():
    msgs = [{"role": "user", "content": f"Message number {i} " * 50} for i in range(20)]
    result = prune_history_for_context(msgs, max_tokens=500)
    assert result["dropped_messages"] > 0
    assert len(result["messages"]) < 20
```

**Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_compaction.py -v`
Expected: FAIL

**Step 3: Implement compaction**

```python
# kabot/agent/loop_core/compaction.py
"""Context compaction â€” auto-summarize history when token limit is reached."""

from __future__ import annotations
from typing import Any

DEFAULT_TOKENS_PER_CHAR = 0.25  # rough estimate: 4 chars â‰ˆ 1 token


def estimate_tokens(content: str | list[dict[str, Any]]) -> int:
    if isinstance(content, str):
        return max(1, int(len(content) * DEFAULT_TOKENS_PER_CHAR))
    total = 0
    for msg in content:
        text = msg.get("content", "")
        if isinstance(text, str):
            total += int(len(text) * DEFAULT_TOKENS_PER_CHAR)
    return max(1, total)


def split_messages_by_token_share(
    messages: list[dict[str, Any]], num_parts: int = 2
) -> list[list[dict[str, Any]]]:
    num_parts = max(1, min(num_parts, len(messages)))
    chunk_size = max(1, len(messages) // num_parts)
    parts = []
    for i in range(0, len(messages), chunk_size):
        parts.append(messages[i : i + chunk_size])
    # Merge leftover into last part
    while len(parts) > num_parts:
        parts[-2].extend(parts.pop())
    return parts


def prune_history_for_context(
    messages: list[dict[str, Any]],
    max_tokens: int,
    max_history_share: float = 0.75,
) -> dict[str, Any]:
    budget = int(max_tokens * max_history_share)
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    running_tokens = 0

    # Keep system message always
    system_msgs = [m for m in messages if m.get("role") == "system"]
    other_msgs = [m for m in messages if m.get("role") != "system"]

    for msg in system_msgs:
        running_tokens += estimate_tokens(msg.get("content", ""))

    # Walk from newest to oldest, keep what fits
    for msg in reversed(other_msgs):
        msg_tokens = estimate_tokens(msg.get("content", ""))
        if running_tokens + msg_tokens <= budget:
            kept.insert(0, msg)
            running_tokens += msg_tokens
        else:
            dropped.insert(0, msg)

    return {
        "messages": system_msgs + kept,
        "dropped_messages": len(dropped),
        "dropped_tokens": sum(estimate_tokens(m.get("content", "")) for m in dropped),
        "kept_tokens": running_tokens,
        "budget_tokens": budget,
    }


async def summarize_for_compaction(
    provider: Any,
    messages: list[dict[str, Any]],
    model: str,
    previous_summary: str = "",
) -> str:
    """Use the LLM to summarize older messages into a compact summary."""
    content_lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        text = msg.get("content", "")
        if text:
            content_lines.append(f"[{role}]: {text[:500]}")

    prompt = (
        "Summarize this conversation segment concisely. "
        "Preserve: decisions made, key facts, todos, open questions, constraints.\n\n"
    )
    if previous_summary:
        prompt += f"Previous summary:\n{previous_summary}\n\n"
    prompt += "Conversation:\n" + "\n".join(content_lines[:30])

    try:
        response = await provider.chat(
            messages=[
                {"role": "system", "content": "You are a conversation summarizer. Be concise."},
                {"role": "user", "content": prompt},
            ],
            model=model,
        )
        return response.content or "No prior history."
    except Exception:
        return previous_summary or "No prior history."
```

**Step 4: Run tests, verify pass**

Run: `python -m pytest tests/test_compaction.py -v`
Expected: ALL PASS

**Step 5: Wire into agent loop**

Modify: `kabot/agent/loop_core/execution_runtime.py:run_agent_loop()`
â€” Before each LLM call, check `estimate_tokens(messages)` against context window. If > 80% of window, call `prune_history_for_context()` and optionally `summarize_for_compaction()`.

**Step 6: Commit**

```bash
git add kabot/agent/loop_core/compaction.py tests/test_compaction.py
git commit -m "feat: add context compaction with auto-summarization (Kabot parity)"
```

---

## Task 3: Tool Loop Detection

**Files:**
- Create: `kabot/agent/loop_core/tool_loop_detection.py`
- Test: `tests/test_tool_loop_detection.py`
- Modify: `kabot/agent/loop_core/execution_runtime.py`

**What it does:** Detect when the AI is stuck calling the same tool repeatedly with the same parameters or in a ping-pong pattern. Block critical loops, warn on minor ones.

**Step 1: Write failing tests**

```python
# tests/test_tool_loop_detection.py
import pytest
from kabot.agent.loop_core.tool_loop_detection import (
    LoopDetector,
    LoopDetectionResult,
)


def test_no_loop_on_first_call():
    detector = LoopDetector()
    result = detector.check("exec", {"command": "ls"})
    assert result.stuck is False


def test_detects_generic_repeat():
    detector = LoopDetector(warning_threshold=3, critical_threshold=5)
    for _ in range(5):
        detector.record("exec", {"command": "ls"})
    result = detector.check("exec", {"command": "ls"})
    assert result.stuck is True
    assert result.level == "critical"


def test_warns_before_critical():
    detector = LoopDetector(warning_threshold=3, critical_threshold=5)
    for _ in range(3):
        detector.record("exec", {"command": "ls"})
    result = detector.check("exec", {"command": "ls"})
    assert result.stuck is True
    assert result.level == "warning"


def test_no_loop_for_different_params():
    detector = LoopDetector(warning_threshold=3, critical_threshold=5)
    for i in range(10):
        detector.record("exec", {"command": f"cmd_{i}"})
    result = detector.check("exec", {"command": "cmd_new"})
    assert result.stuck is False


def test_detects_ping_pong():
    detector = LoopDetector(warning_threshold=3, critical_threshold=5)
    for _ in range(3):
        detector.record("read_file", {"path": "a.py"})
        detector.record("write_file", {"path": "a.py", "content": "x"})
    result = detector.check("read_file", {"path": "a.py"})
    assert result.stuck is True


def test_sliding_window():
    detector = LoopDetector(history_size=5)
    for i in range(10):
        detector.record("exec", {"command": f"different_{i}"})
    # Old entries should be evicted
    assert len(detector._history) <= 5
```

**Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_tool_loop_detection.py -v`

**Step 3: Implement**

```python
# kabot/agent/loop_core/tool_loop_detection.py
"""Tool loop detection â€” detect stuck agents calling same tools repeatedly."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal

HISTORY_SIZE = 30
WARNING_THRESHOLD = 10
CRITICAL_THRESHOLD = 20


@dataclass
class LoopDetectionResult:
    stuck: bool = False
    level: Literal["warning", "critical"] | None = None
    detector: str = ""
    count: int = 0
    message: str = ""
    paired_tool: str | None = None


def _hash_call(tool_name: str, params: Any) -> str:
    """Create stable hash of tool name + params."""
    try:
        serialized = json.dumps(params, sort_keys=True, default=str)
    except (TypeError, ValueError):
        serialized = str(params)
    raw = f"{tool_name}:{serialized}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


class LoopDetector:
    def __init__(
        self,
        history_size: int = HISTORY_SIZE,
        warning_threshold: int = WARNING_THRESHOLD,
        critical_threshold: int = CRITICAL_THRESHOLD,
    ):
        self.history_size = history_size
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self._history: list[dict[str, str]] = []

    def record(self, tool_name: str, params: Any, tool_call_id: str | None = None) -> None:
        entry = {
            "tool_name": tool_name,
            "args_hash": _hash_call(tool_name, params),
        }
        self._history.append(entry)
        if len(self._history) > self.history_size:
            self._history = self._history[-self.history_size :]

    def check(self, tool_name: str, params: Any) -> LoopDetectionResult:
        current_hash = _hash_call(tool_name, params)

        # Generic repeat detection
        repeat_count = sum(
            1 for h in self._history
            if h["args_hash"] == current_hash
        )

        if repeat_count >= self.critical_threshold:
            return LoopDetectionResult(
                stuck=True, level="critical", detector="generic_repeat",
                count=repeat_count,
                message=f"Tool '{tool_name}' called {repeat_count} times with same params â€” blocked.",
            )
        if repeat_count >= self.warning_threshold:
            return LoopDetectionResult(
                stuck=True, level="warning", detector="generic_repeat",
                count=repeat_count,
                message=f"Tool '{tool_name}' called {repeat_count} times with same params â€” warning.",
            )

        # Ping-pong detection
        if len(self._history) >= 4:
            recent = self._history[-4:]
            signatures = [f"{h['tool_name']}:{h['args_hash']}" for h in recent]
            if len(signatures) == 4 and signatures[0] == signatures[2] and signatures[1] == signatures[3]:
                pair_count = sum(1 for i in range(0, len(self._history) - 1, 2)
                    if i + 1 < len(self._history)
                    and f"{self._history[i]['tool_name']}:{self._history[i]['args_hash']}" == signatures[0]
                    and f"{self._history[i+1]['tool_name']}:{self._history[i+1]['args_hash']}" == signatures[1]
                )
                if pair_count >= self.warning_threshold // 2:
                    return LoopDetectionResult(
                        stuck=True, level="critical" if pair_count >= self.critical_threshold // 2 else "warning",
                        detector="ping_pong", count=pair_count,
                        message=f"Ping-pong detected: {recent[0]['tool_name']} â†” {recent[1]['tool_name']} ({pair_count} cycles)",
                        paired_tool=recent[1]["tool_name"],
                    )

        return LoopDetectionResult()
```

**Step 4:** Run tests, verify pass
**Step 5:** Wire into `process_tool_calls()` â€” before each `tools.execute()`, call `detector.check()`. If critical, return error string instead.
**Step 6:** Commit

---

## Task 4: Tool Policy Profiles

**Files:**
- Create: `kabot/agent/tools/tool_policy.py`
- Test: `tests/test_tool_policy.py`
- Modify: `kabot/agent/tools/registry.py`

**What it does:** Define tool access profiles (minimal, coding, messaging, full) and tool groups (fs, runtime, sessions, web, memory, automation). Apply per-agent or per-channel policies.

**Step 1: Write failing tests**

```python
# tests/test_tool_policy.py
from kabot.agent.tools.tool_policy import (
    TOOL_GROUPS,
    TOOL_PROFILES,
    resolve_profile_policy,
    apply_tool_policy,
    is_owner_only_tool,
)


def test_minimal_profile_only_allows_session_status():
    policy = resolve_profile_policy("minimal")
    assert "session_status" in policy.allow


def test_coding_profile_includes_fs_group():
    policy = resolve_profile_policy("coding")
    expanded = policy.expand_groups()
    assert "read_file" in expanded


def test_full_profile_allows_everything():
    policy = resolve_profile_policy("full")
    assert policy.allow is None and policy.deny is None


def test_owner_only_tools():
    assert is_owner_only_tool("cron") is True
    assert is_owner_only_tool("read_file") is False


def test_apply_policy_filters_tools():
    tools = ["read_file", "exec", "cron", "weather"]
    policy = resolve_profile_policy("coding")
    filtered = apply_tool_policy(tools, policy)
    assert "cron" not in filtered
```

**Step 2â€“6:** Implement `tool_policy.py` with profiles matching Kabot's `TOOL_PROFILES` and `TOOL_GROUPS`, test, wire into `ToolRegistry.get_definitions()`, commit.

---

## Task 5: Enhanced Failover Error Classification

**Files:**
- Modify: `kabot/core/resilience.py`
- Create: `kabot/core/failover_error.py`
- Test: `tests/test_failover_error.py`

**What it does:** Classify API errors into 7 categories (billing/rate_limit/auth/timeout/format/model_not_found/unknown) and respond according to each type. Kabot's `failover-error.ts` maps status codes + error messages + error codes to failover reasons.

**Step 1: Write failing tests**

```python
# tests/test_failover_error.py
from kabot.core.failover_error import (
    FailoverError,
    resolve_failover_reason,
    FailoverReason,
)


def test_402_is_billing():
    assert resolve_failover_reason(status=402) == "billing"


def test_429_is_rate_limit():
    assert resolve_failover_reason(status=429) == "rate_limit"


def test_401_is_auth():
    assert resolve_failover_reason(status=401) == "auth"


def test_timeout_from_message():
    assert resolve_failover_reason(message="Request timed out") == "timeout"


def test_400_is_format():
    assert resolve_failover_reason(status=400) == "format"


def test_unknown_fallback():
    assert resolve_failover_reason(status=500) == "unknown"
```

**Step 2â€“6:** Implement `failover_error.py` with `FailoverReason` enum and `resolve_failover_reason()`, update `ResilienceLayer.handle_error()` to use it, test, commit.

---

## Task 6: Session Tool Result Guard

**Files:**
- Create: `kabot/agent/loop_core/tool_result_guard.py`
- Test: `tests/test_tool_result_guard.py`
- Modify: `kabot/agent/loop_core/execution_runtime.py`

**What it does:** Before persisting tool results to memory, truncate oversized results and validate content. Prevents memory bloat from tools that return massive outputs (e.g., `read_file` on a 10MB file).

**Step 1: Write failing tests**

```python
# tests/test_tool_result_guard.py
from kabot.agent.loop_core.tool_result_guard import cap_tool_result_size


def test_small_result_unchanged():
    result = "Hello world"
    assert cap_tool_result_size(result) == result


def test_large_result_truncated():
    result = "x" * 100_000
    capped = cap_tool_result_size(result, max_chars=10_000)
    assert len(capped) <= 10_100  # allow suffix
    assert "truncated" in capped.lower()


def test_preserves_structure():
    result = "line1\nline2\nline3"
    assert cap_tool_result_size(result, max_chars=50_000) == result
```

**Step 2â€“6:** Implement `tool_result_guard.py`, wire into `process_tool_calls()` before `memory.add_message()`, test, commit.

---

## Verification Plan

### Automated Tests
```bash
python -m pytest tests/test_context_guard.py tests/test_compaction.py tests/test_tool_loop_detection.py tests/test_tool_policy.py tests/test_failover_error.py tests/test_tool_result_guard.py -v
```

### Integration Verification
- Run full test suite: `python -m pytest tests/ -v --timeout=30`
- Verify no regressions in existing tests (22 tests from previous session)

### Manual Verification
- Start Kabot, send many rapid messages to trigger compaction
- Verify loop detection blocks repetitive tool calls
- Verify context guard warns on small-context models

---

## Execution Order

| Priority | Task | Est. Time |
|----------|------|-----------|
| P0 | Task 1: Context Window Guard | 10 min |
| P0 | Task 2: Context Compaction | 20 min |
| P1 | Task 3: Tool Loop Detection | 20 min |
| P1 | Task 4: Tool Policy Profiles | 15 min |
| P2 | Task 5: Failover Error Classification | 10 min |
| P2 | Task 6: Session Tool Result Guard | 10 min |
| â€” | Integration & final tests | 10 min |

**Total estimated time: ~95 minutes**


