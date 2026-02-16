# Phase 12: Critical OpenClaw Features - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement Tool Result Truncation and Directives Behavior to prevent bot crashes and enable power-user control

**Architecture:** ToolResultTruncator as standalone utility (like ContextGuard), Directives consumed at multiple points in AgentLoop

**Tech Stack:** Python 3.11+, tiktoken, pytest, loguru

---

## Task 1: ToolResultTruncator Implementation

**Files:**
- Create: `kabot/agent/truncator.py`
- Create: `tests/agent/test_truncator.py`

### Step 1: Write failing test for small results

```python
# tests/agent/test_truncator.py
"""Tests for ToolResultTruncator."""

from kabot.agent.truncator import ToolResultTruncator


def test_truncator_allows_small_results():
    """Small results pass through unchanged."""
    truncator = ToolResultTruncator(max_tokens=128000, max_share=0.3)
    small_result = "Hello world" * 100  # ~200 tokens

    result = truncator.truncate(small_result, "test_tool")

    assert result == small_result
    assert "⚠️" not in result
```

### Step 2: Run test to verify it fails

Run: `pytest tests/agent/test_truncator.py::test_truncator_allows_small_results -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'kabot.agent.truncator'"

### Step 3: Implement ToolResultTruncator class

```python
# kabot/agent/truncator.py
"""Tool result truncation to prevent context overflow."""

from loguru import logger


class ToolResultTruncator:
    """Truncates tool results to prevent context overflow."""

    def __init__(self, max_tokens: int = 128000, max_share: float = 0.3):
        """
        Initialize truncator.

        Args:
            max_tokens: Total context window size
            max_share: Maximum percentage of context for single tool result
        """
        self.max_tokens = max_tokens
        self.max_share = max_share
        self.threshold = int(max_tokens * max_share)

    def truncate(self, result: str, tool_name: str) -> str:
        """
        Truncate result if exceeds threshold.

        Args:
            result: Raw tool output
            tool_name: Name of tool that produced output

        Returns:
            Original result if within limit, truncated result with warning if over
        """
        try:
            token_count = self._count_tokens(result)

            if token_count <= self.threshold:
                return result

            # Truncate: keep first 80% of threshold
            keep_tokens = int(self.threshold * 0.8)
            truncated = self._truncate_to_tokens(result, keep_tokens)

            warning = (
                f"\n\n⚠️ [Output truncated: {token_count} tokens exceeds limit of {self.threshold}. "
                f"Showing first {keep_tokens} tokens. Use pagination or filters to get specific data.]"
            )

            return truncated + warning

        except Exception as e:
            logger.error(f"Truncation failed for {tool_name}: {e}")
            # Fallback: character-based truncation
            max_chars = self.threshold * 4
            if len(result) <= max_chars:
                return result

            truncated = result[:int(max_chars * 0.8)]
            warning = f"\n\n⚠️ [Output truncated: ~{len(result)} chars exceeds limit.]"
            return truncated + warning

    def _count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken with fallback."""
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model("gpt-4")
            return len(encoding.encode(text))
        except ImportError:
            logger.warning("tiktoken not available, using character-based estimation")
            return len(text) // 4

    def _truncate_to_tokens(self, text: str, target_tokens: int) -> str:
        """Truncate text to approximately target_tokens."""
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model("gpt-4")
            tokens = encoding.encode(text)
            truncated_tokens = tokens[:target_tokens]
            return encoding.decode(truncated_tokens)
        except ImportError:
            # Fallback: character-based
            target_chars = target_tokens * 4
            return text[:target_chars]
```

### Step 4: Run test to verify it passes

Run: `pytest tests/agent/test_truncator.py::test_truncator_allows_small_results -v`
Expected: PASS

### Step 5: Write test for large result truncation

```python
# tests/agent/test_truncator.py (add to existing file)

def test_truncator_truncates_large_results():
    """Large results are truncated with warning."""
    truncator = ToolResultTruncator(max_tokens=128000, max_share=0.3)
    large_result = "x" * 200000  # ~50K tokens, exceeds 38K threshold

    result = truncator.truncate(large_result, "test_tool")

    assert len(result) < len(large_result)
    assert "⚠️" in result
    assert "Output truncated" in result
```

### Step 6: Run test to verify it passes

Run: `pytest tests/agent/test_truncator.py::test_truncator_truncates_large_results -v`
Expected: PASS (implementation already handles this)

### Step 7: Write test for preserving beginning

```python
# tests/agent/test_truncator.py (add to existing file)

def test_truncator_preserves_beginning():
    """Truncation preserves beginning of output."""
    truncator = ToolResultTruncator(max_tokens=128000, max_share=0.3)
    large_result = "IMPORTANT_START" + ("x" * 200000) + "END"

    result = truncator.truncate(large_result, "test_tool")

    assert "IMPORTANT_START" in result
    assert "END" not in result
```

### Step 8: Run test to verify it passes

Run: `pytest tests/agent/test_truncator.py::test_truncator_preserves_beginning -v`
Expected: PASS

### Step 9: Write test for empty result

```python
# tests/agent/test_truncator.py (add to existing file)

def test_truncator_handles_empty_result():
    """Handles empty results gracefully."""
    truncator = ToolResultTruncator(max_tokens=128000, max_share=0.3)

    result = truncator.truncate("", "test_tool")

    assert result == ""
```

### Step 10: Run test to verify it passes

Run: `pytest tests/agent/test_truncator.py::test_truncator_handles_empty_result -v`
Expected: PASS

### Step 11: Write test for custom threshold

```python
# tests/agent/test_truncator.py (add to existing file)

def test_truncator_custom_threshold():
    """Respects custom threshold configuration."""
    truncator = ToolResultTruncator(max_tokens=128000, max_share=0.5)

    assert truncator.threshold == 64000  # 50% of 128K
```

### Step 12: Run all truncator tests

Run: `pytest tests/agent/test_truncator.py -v`
Expected: 5/5 tests PASS

### Step 13: Commit Task 1

```bash
git add kabot/agent/truncator.py tests/agent/test_truncator.py
git commit -m "feat(agent): add ToolResultTruncator for context overflow prevention

- Implements 30% context window limit (~38K tokens)
- Uses tiktoken for accurate token counting
- Fallback to character-based estimation
- Preserves beginning of output (most important context)
- 5/5 tests passing

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Directives Behavior Implementation

**Files:**
- Modify: `kabot/agent/loop.py`
- Create: `tests/agent/test_directives_behavior.py`

### Step 1: Write failing test for think mode

```python
# tests/agent/test_directives_behavior.py
"""Tests for directives behavior in AgentLoop."""

import pytest
from kabot.core.session import Session
from kabot.agent.loop import AgentLoop


def test_think_mode_injects_reasoning_prompt():
    """Think mode adds reasoning system prompt."""
    session = Session(session_id="test", user_id="user1", channel="test")
    session.metadata['directives'] = {'think': True, 'verbose': False, 'elevated': False}

    # Create minimal AgentLoop (we'll need to mock dependencies)
    loop = AgentLoop(provider=None, model="test", config=None)
    messages = [{"role": "user", "content": "test"}]

    modified = loop._apply_think_mode(messages, session)

    assert len(modified) > len(messages)
    assert any("reasoning" in str(m).lower() for m in modified)
    assert any("step-by-step" in str(m).lower() for m in modified)
```

### Step 2: Run test to verify it fails

Run: `pytest tests/agent/test_directives_behavior.py::test_think_mode_injects_reasoning_prompt -v`
Expected: FAIL with "AttributeError: 'AgentLoop' object has no attribute '_apply_think_mode'"

### Step 3: Implement _apply_think_mode method

Add to `kabot/agent/loop.py`:

```python
def _apply_think_mode(self, messages: list, session: Session) -> list:
    """Apply think mode if directive is active."""
    try:
        directives = session.metadata.get('directives', {})
        if not isinstance(directives, dict):
            logger.warning("Directives metadata corrupted, using defaults")
            directives = {}

        if not directives.get('think'):
            return messages

        reasoning_prompt = {
            "role": "system",
            "content": (
                "Think step-by-step. Show your reasoning process explicitly before taking action. "
                "Consider edge cases, alternative approaches, and potential issues. "
                "When analyzing code, read related files to understand full context."
            )
        }

        # Insert at beginning
        messages.insert(0, reasoning_prompt)
        logger.debug("Think mode applied: reasoning prompt injected")
        return messages

    except Exception as e:
        logger.error(f"Failed to apply think mode: {e}")
        return messages
```

### Step 4: Run test to verify it passes

Run: `pytest tests/agent/test_directives_behavior.py::test_think_mode_injects_reasoning_prompt -v`
Expected: PASS

### Step 5: Write test for verbose mode

```python
# tests/agent/test_directives_behavior.py (add to existing file)

def test_verbose_mode_enabled():
    """Verbose mode check returns True when enabled."""
    session = Session(session_id="test", user_id="user1", channel="test")
    session.metadata['directives'] = {'think': False, 'verbose': True, 'elevated': False}

    loop = AgentLoop(provider=None, model="test", config=None)

    assert loop._should_log_verbose(session) is True


def test_verbose_mode_disabled():
    """Verbose mode check returns False when disabled."""
    session = Session(session_id="test", user_id="user1", channel="test")

    loop = AgentLoop(provider=None, model="test", config=None)

    assert loop._should_log_verbose(session) is False


def test_format_verbose_output():
    """Verbose output formatting includes debug info."""
    loop = AgentLoop(provider=None, model="test", config=None)

    output = loop._format_verbose_output("read_file", "file contents", 150)

    assert "[DEBUG]" in output
    assert "read_file" in output
    assert "150" in output
    assert "file contents" in output
```

### Step 6: Run test to verify it fails

Run: `pytest tests/agent/test_directives_behavior.py -k verbose -v`
Expected: FAIL with "AttributeError: 'AgentLoop' object has no attribute '_should_log_verbose'"

### Step 7: Implement verbose mode methods

Add to `kabot/agent/loop.py`:

```python
def _should_log_verbose(self, session: Session) -> bool:
    """Check if verbose logging is enabled."""
    try:
        return session.metadata.get('directives', {}).get('verbose', False)
    except Exception as e:
        logger.error(f"Failed to check verbose mode: {e}")
        return False


def _format_verbose_output(self, tool_name: str, tool_result: str, tokens_used: int) -> str:
    """Format verbose debug output."""
    return (
        f"\n\n[DEBUG] Tool: {tool_name}\n"
        f"[DEBUG] Tokens: {tokens_used}\n"
        f"[DEBUG] Result:\n{tool_result}\n"
    )
```

### Step 8: Run test to verify it passes

Run: `pytest tests/agent/test_directives_behavior.py -k verbose -v`
Expected: PASS (3 tests)

### Step 9: Write test for elevated mode

```python
# tests/agent/test_directives_behavior.py (add to existing file)

def test_elevated_mode_enabled():
    """Elevated mode sets auto_approve and disables restrictions."""
    session = Session(session_id="test", user_id="user1", channel="test")
    session.metadata['directives'] = {'think': False, 'verbose': False, 'elevated': True}

    loop = AgentLoop(provider=None, model="test", config=None)
    perms = loop._get_tool_permissions(session)

    assert perms['auto_approve'] is True
    assert perms['restrict_to_workspace'] is False
    assert perms['allow_high_risk'] is True


def test_elevated_mode_disabled():
    """Elevated mode uses safe defaults when disabled."""
    session = Session(session_id="test", user_id="user1", channel="test")

    loop = AgentLoop(provider=None, model="test", config=None)
    perms = loop._get_tool_permissions(session)

    assert perms['auto_approve'] is False
    assert perms['restrict_to_workspace'] is True
    assert perms['allow_high_risk'] is False
```

### Step 10: Run test to verify it fails

Run: `pytest tests/agent/test_directives_behavior.py -k elevated -v`
Expected: FAIL with "AttributeError: 'AgentLoop' object has no attribute '_get_tool_permissions'"

### Step 11: Implement _get_tool_permissions method

Add to `kabot/agent/loop.py`:

```python
def _get_tool_permissions(self, session: Session) -> dict:
    """Get tool execution permissions based on directives."""
    try:
        elevated = session.metadata.get('directives', {}).get('elevated', False)

        return {
            'auto_approve': elevated,
            'restrict_to_workspace': not elevated,
            'allow_high_risk': elevated
        }
    except Exception as e:
        logger.error(f"Failed to get tool permissions: {e}")
        # Safe defaults
        return {
            'auto_approve': False,
            'restrict_to_workspace': True,
            'allow_high_risk': False
        }
```

### Step 12: Run test to verify it passes

Run: `pytest tests/agent/test_directives_behavior.py -k elevated -v`
Expected: PASS (2 tests)

### Step 13: Write test for directives persistence

```python
# tests/agent/test_directives_behavior.py (add to existing file)

def test_think_mode_disabled_by_default():
    """Think mode not applied when directive not set."""
    session = Session(session_id="test", user_id="user1", channel="test")

    loop = AgentLoop(provider=None, model="test", config=None)
    messages = [{"role": "user", "content": "test"}]

    modified = loop._apply_think_mode(messages, session)

    assert modified == messages  # Unchanged


def test_directives_error_handling():
    """Directives handle corrupted metadata gracefully."""
    session = Session(session_id="test", user_id="user1", channel="test")
    session.metadata['directives'] = "corrupted_string"  # Should be dict

    loop = AgentLoop(provider=None, model="test", config=None)

    # Should not crash, use safe defaults
    perms = loop._get_tool_permissions(session)
    assert perms['auto_approve'] is False
    assert perms['restrict_to_workspace'] is True
```

### Step 14: Run all directives behavior tests

Run: `pytest tests/agent/test_directives_behavior.py -v`
Expected: 9/9 tests PASS

### Step 15: Integrate truncator into AgentLoop

Add to `kabot/agent/loop.py` in `__init__`:

```python
from kabot.agent.truncator import ToolResultTruncator

# In __init__ method, after context_guard initialization:
self.truncator = ToolResultTruncator(max_tokens=128000, max_share=0.3)
logger.info("Tool result truncator initialized (30% limit)")
```

### Step 16: Apply truncation after tool execution

Find tool execution point in `kabot/agent/loop.py` and wrap result:

```python
# After tool.execute() call:
result = await tool.execute(**tool_args)

# Apply truncation
result = self.truncator.truncate(result, tool_name)
```

### Step 17: Apply think mode before LLM call

In `_process_message` method, before calling LLM:

```python
# Apply think mode if enabled
messages = self._apply_think_mode(messages, session)
```

### Step 18: Run integration test

Create simple integration test:

```python
# tests/agent/test_phase12_integration.py
"""Integration tests for Phase 12 features."""

import pytest
from kabot.agent.loop import AgentLoop
from kabot.core.session import Session


def test_truncator_initialized():
    """AgentLoop initializes truncator."""
    loop = AgentLoop(provider=None, model="test", config=None)

    assert hasattr(loop, 'truncator')
    assert loop.truncator.threshold == 38400  # 30% of 128K


def test_directives_methods_exist():
    """AgentLoop has all directives methods."""
    loop = AgentLoop(provider=None, model="test", config=None)

    assert hasattr(loop, '_apply_think_mode')
    assert hasattr(loop, '_should_log_verbose')
    assert hasattr(loop, '_format_verbose_output')
    assert hasattr(loop, '_get_tool_permissions')
```

Run: `pytest tests/agent/test_phase12_integration.py -v`
Expected: 2/2 tests PASS

### Step 19: Run all Phase 12 tests

Run: `pytest tests/agent/test_truncator.py tests/agent/test_directives_behavior.py tests/agent/test_phase12_integration.py -v`
Expected: 16/16 tests PASS

### Step 20: Commit Task 2

```bash
git add kabot/agent/loop.py tests/agent/test_directives_behavior.py tests/agent/test_phase12_integration.py
git commit -m "feat(agent): implement directives behavior consumption

- /think mode: injects reasoning prompt for extended analysis
- /verbose mode: enables debug logging and intermediate results
- /elevated mode: auto-approves tools and disables restrictions
- Integrated ToolResultTruncator into AgentLoop
- 11/11 new tests passing (16/16 total Phase 12)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Validation

### Run all tests

```bash
pytest tests/agent/test_truncator.py tests/agent/test_directives_behavior.py tests/agent/test_phase12_integration.py -v --cov=kabot.agent.truncator --cov=kabot.agent.loop --cov-report=term-missing
```

Expected: 16/16 tests PASS, >80% coverage

### Manual validation

1. **Test truncation:**
   ```python
   from kabot.agent.truncator import ToolResultTruncator
   t = ToolResultTruncator()
   result = t.truncate("x" * 200000, "test")
   print("Truncated:", len(result), "⚠️" in result)
   ```

2. **Test directives:**
   ```python
   from kabot.core.session import Session
   from kabot.agent.loop import AgentLoop

   session = Session(session_id="test", user_id="u1", channel="test")
   session.metadata['directives'] = {'think': True}

   loop = AgentLoop(...)
   messages = [{"role": "user", "content": "test"}]
   modified = loop._apply_think_mode(messages, session)
   print("Think mode applied:", len(modified) > len(messages))
   ```

---

## Success Criteria

- ✅ ToolResultTruncator class implemented with 5 tests passing
- ✅ Directives behavior methods implemented with 9 tests passing
- ✅ Integration complete with 2 integration tests passing
- ✅ Total: 16/16 tests passing
- ✅ >80% test coverage for new code
- ✅ No breaking changes to existing functionality

---

## References

- Design Document: `docs/plans/2026-02-16-phase-12-critical-features-design.md`
- Phase 11 Implementation: `docs/logs/2026-02-15-phase-11-openclaw-parity.md`
- OpenClaw Analysis: `docs/openclaw-analysis/deep-technical-findings.md`
