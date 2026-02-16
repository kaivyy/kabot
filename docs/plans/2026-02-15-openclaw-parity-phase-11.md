# OpenClaw Parity - Phase 11 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement critical OpenClaw features for production reliability: Auto-Compaction, Directives Parser, and Auth Rotation.

**Architecture:** Add context management layer, inline command parser, and multi-key auth rotation to match OpenClaw's resilience patterns.

**Tech Stack:** Python 3.13, pytest, asyncio, tiktoken (token counting)

---

## Task 1: Context Auto-Compaction

**Files:**
- Create: `kabot/agent/context_guard.py`
- Create: `kabot/agent/compactor.py`
- Create: `tests/agent/test_context_guard.py`
- Create: `tests/agent/test_compactor.py`
- Modify: `kabot/agent/loop.py:309-318` (add compaction check)

**Step 1: Write failing test for ContextGuard**

Create `tests/agent/test_context_guard.py`:

```python
"""Tests for context window guard."""

import pytest
from kabot.agent.context_guard import ContextGuard


def test_context_guard_detects_overflow():
    """Test that guard detects when context exceeds limit."""
    guard = ContextGuard(max_tokens=1000, buffer_tokens=100)

    # Simulate messages that exceed limit
    messages = [
        {"role": "user", "content": "x" * 500},
        {"role": "assistant", "content": "y" * 500},
        {"role": "user", "content": "z" * 200},
    ]

    needs_compaction = guard.check_overflow(messages, model="gpt-4")
    assert needs_compaction is True


def test_context_guard_allows_within_limit():
    """Test that guard allows messages within limit."""
    guard = ContextGuard(max_tokens=10000, buffer_tokens=1000)

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]

    needs_compaction = guard.check_overflow(messages, model="gpt-4")
    assert needs_compaction is False
```

**Step 2: Run test to verify it fails**

```bash
cd C:\Users\Arvy Kairi\Desktop\bot\kabot
python -m pytest tests/agent/test_context_guard.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'kabot.agent.context_guard'"

**Step 3: Implement ContextGuard**

Create `kabot/agent/context_guard.py`:

```python
"""Context window guard to prevent token overflow."""

from typing import Any
from loguru import logger


class ContextGuard:
    """Guards against context window overflow."""

    def __init__(self, max_tokens: int = 128000, buffer_tokens: int = 4000):
        """
        Initialize context guard.

        Args:
            max_tokens: Maximum context window size
            buffer_tokens: Safety buffer before triggering compaction
        """
        self.max_tokens = max_tokens
        self.buffer_tokens = buffer_tokens
        self.threshold = max_tokens - buffer_tokens

    def check_overflow(self, messages: list[dict[str, Any]], model: str) -> bool:
        """
        Check if messages exceed context window threshold.

        Args:
            messages: Conversation messages
            model: Model name for token counting

        Returns:
            True if compaction needed, False otherwise
        """
        try:
            import tiktoken

            # Get encoding for model
            try:
                encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fallback to cl100k_base for unknown models
                encoding = tiktoken.get_encoding("cl100k_base")

            # Count tokens
            total_tokens = 0
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str):
                    total_tokens += len(encoding.encode(content))
                # Add overhead for role, formatting
                total_tokens += 4

            logger.debug(f"Context tokens: {total_tokens}/{self.max_tokens}")

            return total_tokens > self.threshold

        except ImportError:
            logger.warning("tiktoken not available, using character-based estimation")
            # Fallback: rough estimate (4 chars ≈ 1 token)
            total_chars = sum(len(str(msg.get("content", ""))) for msg in messages)
            estimated_tokens = total_chars // 4
            return estimated_tokens > self.threshold
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/agent/test_context_guard.py -v
```

Expected: PASS (2/2 tests)

**Step 5: Write failing test for Compactor**

Add to `tests/agent/test_compactor.py`:

```python
"""Tests for message compactor."""

import pytest
from kabot.agent.compactor import Compactor


@pytest.mark.asyncio
async def test_compactor_summarizes_old_messages():
    """Test that compactor summarizes older messages."""
    compactor = Compactor()

    messages = [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a programming language..."},
        {"role": "user", "content": "What about Java?"},
        {"role": "assistant", "content": "Java is also a programming language..."},
        {"role": "user", "content": "Compare them"},
    ]

    # Mock LLM provider
    class MockProvider:
        async def chat(self, messages, model, max_tokens=500, temperature=0.3):
            class Response:
                content = "Summary: User asked about Python and Java."
            return Response()

    provider = MockProvider()
    compacted = await compactor.compact(messages, provider, model="gpt-4", keep_recent=2)

    # Should keep last 2 messages + summary
    assert len(compacted) == 3
    assert "Summary:" in compacted[0]["content"]
    assert compacted[1]["content"] == "Compare them"


@pytest.mark.asyncio
async def test_compactor_preserves_recent_messages():
    """Test that compactor always preserves recent messages."""
    compactor = Compactor()

    messages = [
        {"role": "user", "content": "Recent message 1"},
        {"role": "assistant", "content": "Recent response 1"},
    ]

    class MockProvider:
        async def chat(self, messages, model, max_tokens=500, temperature=0.3):
            class Response:
                content = "Summary"
            return Response()

    provider = MockProvider()
    compacted = await compactor.compact(messages, provider, model="gpt-4", keep_recent=2)

    # Should not compact if all messages are recent
    assert len(compacted) == 2
```

**Step 6: Run test to verify it fails**

```bash
python -m pytest tests/agent/test_compactor.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'kabot.agent.compactor'"

**Step 7: Implement Compactor**

Create `kabot/agent/compactor.py`:

```python
"""Message compactor for context window management."""

from typing import Any
from loguru import logger


class Compactor:
    """Compacts conversation history by summarizing old messages."""

    async def compact(
        self,
        messages: list[dict[str, Any]],
        provider: Any,
        model: str,
        keep_recent: int = 10
    ) -> list[dict[str, Any]]:
        """
        Compact messages by summarizing older ones.

        Args:
            messages: Full conversation history
            provider: LLM provider for summarization
            model: Model to use for summarization
            keep_recent: Number of recent messages to preserve

        Returns:
            Compacted message list with summary + recent messages
        """
        if len(messages) <= keep_recent:
            logger.debug("No compaction needed, message count within limit")
            return messages

        # Split into old (to summarize) and recent (to keep)
        old_messages = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]

        logger.info(f"Compacting {len(old_messages)} old messages, keeping {keep_recent} recent")

        # Build summarization prompt
        conversation_text = self._format_for_summary(old_messages)
        summary_prompt = f"""Summarize this conversation history concisely (max 200 words):

{conversation_text}

Focus on key topics, decisions, and context needed to continue the conversation."""

        try:
            response = await provider.chat(
                messages=[{"role": "user", "content": summary_prompt}],
                model=model,
                max_tokens=500,
                temperature=0.3
            )

            summary = response.content or "Previous conversation summary unavailable."

            # Create summary message
            summary_msg = {
                "role": "system",
                "content": f"[Conversation History Summary]\n{summary}"
            }

            # Return summary + recent messages
            return [summary_msg] + recent_messages

        except Exception as e:
            logger.error(f"Compaction failed: {e}, keeping recent messages only")
            return recent_messages

    def _format_for_summary(self, messages: list[dict[str, Any]]) -> str:
        """Format messages for summarization."""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                lines.append(f"{role.upper()}: {content[:500]}")
        return "\n\n".join(lines)
```

**Step 8: Run test to verify it passes**

```bash
python -m pytest tests/agent/test_compactor.py -v
```

Expected: PASS (2/2 tests)

**Step 9: Integrate into AgentLoop**

Modify `kabot/agent/loop.py` in `__init__` method (around line 85):

```python
        self.context = ContextBuilder(workspace)
        self.sessions = session_manager or SessionManager(workspace)
        self.memory = ChromaMemoryManager(
            workspace / "memory_db",
            enable_hybrid_memory=enable_hybrid_memory
        )

        # Context management (Phase 11)
        from kabot.agent.context_guard import ContextGuard
        from kabot.agent.compactor import Compactor
        self.context_guard = ContextGuard(max_tokens=128000, buffer_tokens=4000)
        self.compactor = Compactor()
```

Add compaction check in `_run_agent_loop` method before LLM call (around line 376):

```python
        while iteration < self.max_iterations:
            iteration += 1

            # Check for context overflow and compact if needed
            if self.context_guard.check_overflow(messages, self.model):
                logger.warning("Context overflow detected, compacting history")
                messages = await self.compactor.compact(
                    messages, self.provider, self.model, keep_recent=10
                )

            response, error = await self._call_llm_with_fallback(messages, models_to_try)
```

**Step 10: Run integration test**

```bash
python -m pytest tests/agent/test_context_guard.py tests/agent/test_compactor.py -v
```

Expected: PASS (4/4 tests)

**Step 11: Commit**

```bash
git add kabot/agent/context_guard.py kabot/agent/compactor.py tests/agent/test_context_guard.py tests/agent/test_compactor.py kabot/agent/loop.py
git commit -m "feat(agent): add auto-compaction for context window management

- Implement ContextGuard to detect token overflow
- Implement Compactor to summarize old messages
- Integrate into AgentLoop with automatic compaction
- Add comprehensive tests for both components

Prevents crashes on long conversations by automatically
summarizing older messages when approaching token limits."
```

---

## Task 2: Directives Parser

**Files:**
- Create: `kabot/agent/directives.py`
- Create: `tests/agent/test_directives.py`
- Modify: `kabot/agent/loop.py:298-325` (add directive parsing)

**Step 1: Write failing test for DirectiveParser**

Create `tests/agent/test_directives.py`:

```python
"""Tests for inline directives parser."""

import pytest
from kabot.agent.directives import DirectiveParser, ParsedDirectives


def test_parse_think_directive():
    """Test parsing /think directive."""
    parser = DirectiveParser()

    message = "/think What is the capital of France?"
    result = parser.parse(message)

    assert result.has_directives is True
    assert result.think_mode is True
    assert result.cleaned_message == "What is the capital of France?"


def test_parse_verbose_directive():
    """Test parsing /verbose directive."""
    parser = DirectiveParser()

    message = "/verbose Explain how async works"
    result = parser.parse(message)

    assert result.verbose_mode is True
    assert result.cleaned_message == "Explain how async works"


def test_parse_multiple_directives():
    """Test parsing multiple directives."""
    parser = DirectiveParser()

    message = "/think /verbose Solve this problem"
    result = parser.parse(message)

    assert result.think_mode is True
    assert result.verbose_mode is True
    assert result.cleaned_message == "Solve this problem"


def test_parse_no_directives():
    """Test message without directives."""
    parser = DirectiveParser()

    message = "Just a normal message"
    result = parser.parse(message)

    assert result.has_directives is False
    assert result.think_mode is False
    assert result.verbose_mode is False
    assert result.cleaned_message == "Just a normal message"


def test_parse_elevated_directive():
    """Test parsing /elevated directive for extended permissions."""
    parser = DirectiveParser()

    message = "/elevated Run system command"
    result = parser.parse(message)

    assert result.elevated_mode is True
    assert result.cleaned_message == "Run system command"
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/agent/test_directives.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'kabot.agent.directives'"

**Step 3: Implement DirectiveParser**

Create `kabot/agent/directives.py`:

```python
"""Inline directives parser for power-user control."""

import re
from dataclasses import dataclass
from loguru import logger


@dataclass
class ParsedDirectives:
    """Result of parsing directives from a message."""
    has_directives: bool = False
    think_mode: bool = False
    verbose_mode: bool = False
    elevated_mode: bool = False
    cleaned_message: str = ""


class DirectiveParser:
    """
    Parses inline directives from user messages.

    Supported directives:
    - /think: Enable extended reasoning mode
    - /verbose: Enable detailed explanations
    - /elevated: Grant extended permissions (use with caution)
    """

    DIRECTIVE_PATTERN = re.compile(r'^(/\w+)\s*', re.MULTILINE)

    DIRECTIVES = {
        "/think": "think_mode",
        "/verbose": "verbose_mode",
        "/elevated": "elevated_mode",
    }

    def parse(self, message: str) -> ParsedDirectives:
        """
        Parse directives from message.

        Args:
            message: User message potentially containing directives

        Returns:
            ParsedDirectives with flags and cleaned message
        """
        result = ParsedDirectives()
        cleaned = message

        # Find all directives at start of message
        matches = self.DIRECTIVE_PATTERN.findall(message)

        if not matches:
            result.cleaned_message = message
            return result

        result.has_directives = True

        # Process each directive
        for directive in matches:
            directive_lower = directive.lower()
            if directive_lower in self.DIRECTIVES:
                attr_name = self.DIRECTIVES[directive_lower]
                setattr(result, attr_name, True)
                logger.debug(f"Directive detected: {directive}")
                # Remove directive from message
                cleaned = cleaned.replace(directive, "", 1).strip()

        result.cleaned_message = cleaned
        return result
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/agent/test_directives.py -v
```

Expected: PASS (5/5 tests)

**Step 5: Integrate into AgentLoop**

Modify `kabot/agent/loop.py` in `_process_message` method (around line 305):

```python
    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        # Emit ON_MESSAGE_RECEIVED hook
        await self.hooks.emit("ON_MESSAGE_RECEIVED", msg)

        # Parse directives (Phase 11)
        from kabot.agent.directives import DirectiveParser
        parser = DirectiveParser()
        directives = parser.parse(msg.content)

        # Use cleaned message for processing
        original_content = msg.content
        if directives.has_directives:
            msg.content = directives.cleaned_message
            logger.info(f"Directives: think={directives.think_mode}, verbose={directives.verbose_mode}, elevated={directives.elevated_mode}")

        if msg.channel == "system":
            return await self._process_system_message(msg)
```

Store directives in session for later use:

```python
        session = await self._init_session(msg)

        # Store directives in session metadata
        if directives.has_directives:
            session.metadata = getattr(session, 'metadata', {})
            session.metadata['directives'] = {
                'think': directives.think_mode,
                'verbose': directives.verbose_mode,
                'elevated': directives.elevated_mode,
            }
```

**Step 6: Run integration test**

```bash
python -m pytest tests/agent/test_directives.py -v
```

Expected: PASS (5/5 tests)

**Step 7: Commit**

```bash
git add kabot/agent/directives.py tests/agent/test_directives.py kabot/agent/loop.py
git commit -m "feat(agent): add inline directives parser

- Implement DirectiveParser for /think, /verbose, /elevated
- Parse directives from user messages
- Store directive state in session metadata
- Add comprehensive tests

Enables power-user control over agent behavior in real-time."
```

---

## Task 3: Auth Rotation System

**Files:**
- Create: `kabot/auth/rotation.py`
- Create: `tests/auth/test_rotation.py`
- Modify: `kabot/agent/loop.py:595-627` (add rotation on error)
- Modify: `kabot/config/schema.py:50-80` (add multiple API keys support)

**Step 1: Write failing test for AuthRotation**

Create `tests/auth/test_rotation.py`:

```python
"""Tests for auth key rotation."""

import pytest
from kabot.auth.rotation import AuthRotation


def test_rotation_cycles_through_keys():
    """Test that rotation cycles through available keys."""
    keys = ["key1", "key2", "key3"]
    rotation = AuthRotation(keys)

    assert rotation.current_key() == "key1"

    rotation.rotate()
    assert rotation.current_key() == "key2"

    rotation.rotate()
    assert rotation.current_key() == "key3"

    # Should cycle back to first
    rotation.rotate()
    assert rotation.current_key() == "key1"


def test_rotation_marks_failed_keys():
    """Test that failed keys are marked and skipped."""
    keys = ["key1", "key2", "key3"]
    rotation = AuthRotation(keys)

    # Mark key1 as failed
    rotation.mark_failed("key1", reason="rate_limit")

    # Should skip to key2
    rotation.rotate()
    assert rotation.current_key() == "key2"

    # key1 should be skipped on next cycle
    rotation.rotate()  # -> key3
    rotation.rotate()  # -> key2 (skip key1)
    assert rotation.current_key() == "key2"


def test_rotation_resets_after_cooldown():
    """Test that failed keys are reset after cooldown period."""
    keys = ["key1", "key2"]
    rotation = AuthRotation(keys, cooldown_seconds=0)  # Instant cooldown for testing

    rotation.mark_failed("key1", reason="rate_limit")
    rotation.rotate()
    assert rotation.current_key() == "key2"

    # After cooldown, key1 should be available again
    import time
    time.sleep(0.1)
    rotation.reset_expired_failures()

    rotation.rotate()  # Should cycle back to key1
    assert rotation.current_key() == "key1"


def test_rotation_with_single_key():
    """Test rotation with only one key."""
    keys = ["only_key"]
    rotation = AuthRotation(keys)

    assert rotation.current_key() == "only_key"

    rotation.rotate()
    assert rotation.current_key() == "only_key"  # Same key


def test_rotation_all_keys_failed():
    """Test behavior when all keys have failed."""
    keys = ["key1", "key2"]
    rotation = AuthRotation(keys)

    rotation.mark_failed("key1", reason="invalid")
    rotation.mark_failed("key2", reason="invalid")

    # Should still return a key (last resort)
    assert rotation.current_key() in keys
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/auth/test_rotation.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'kabot.auth.rotation'"

**Step 3: Implement AuthRotation**

Create `kabot/auth/rotation.py`:

```python
"""Auth key rotation for production reliability."""

import time
from typing import Optional
from loguru import logger


class AuthRotation:
    """
    Manages rotation of API keys for resilience.

    Automatically rotates to next available key on failures
    (rate limits, auth errors) and tracks cooldown periods.
    """

    def __init__(self, keys: list[str], cooldown_seconds: int = 300):
        """
        Initialize auth rotation.

        Args:
            keys: List of API keys to rotate through
            cooldown_seconds: Time before retrying failed keys (default: 5 min)
        """
        if not keys:
            raise ValueError("At least one API key required")

        self.keys = keys
        self.cooldown_seconds = cooldown_seconds
        self.current_index = 0
        self.failed_keys: dict[str, dict] = {}  # key -> {reason, timestamp}

    def current_key(self) -> str:
        """Get the current active API key."""
        return self.keys[self.current_index]

    def rotate(self) -> str:
        """
        Rotate to next available key.

        Returns:
            The new current key
        """
        # Reset expired failures first
        self.reset_expired_failures()

        # Try to find next non-failed key
        attempts = 0
        while attempts < len(self.keys):
            self.current_index = (self.current_index + 1) % len(self.keys)
            key = self.keys[self.current_index]

            if key not in self.failed_keys:
                logger.info(f"Rotated to key #{self.current_index + 1}")
                return key

            attempts += 1

        # All keys failed, return current as last resort
        logger.warning("All keys have failed, using current key as fallback")
        return self.keys[self.current_index]

    def mark_failed(self, key: str, reason: str) -> None:
        """
        Mark a key as failed.

        Args:
            key: The API key that failed
            reason: Failure reason (rate_limit, auth_error, etc.)
        """
        self.failed_keys[key] = {
            "reason": reason,
            "timestamp": time.time()
        }
        logger.warning(f"Marked key as failed: {reason}")

    def reset_expired_failures(self) -> None:
        """Reset keys that have passed their cooldown period."""
        now = time.time()
        expired = []

        for key, info in self.failed_keys.items():
            if now - info["timestamp"] > self.cooldown_seconds:
                expired.append(key)

        for key in expired:
            del self.failed_keys[key]
            logger.info(f"Reset failed key after cooldown")

    def get_status(self) -> dict:
        """Get rotation status for monitoring."""
        return {
            "total_keys": len(self.keys),
            "current_index": self.current_index,
            "failed_count": len(self.failed_keys),
            "available_count": len(self.keys) - len(self.failed_keys)
        }
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/auth/test_rotation.py -v
```

Expected: PASS (5/5 tests)

**Step 5: Integrate into AgentLoop**

Modify `kabot/agent/loop.py` in `__init__` to support multiple keys:

```python
        # Auth rotation (Phase 11)
        from kabot.auth.rotation import AuthRotation
        api_keys = self._collect_api_keys(provider)
        if len(api_keys) > 1:
            self.auth_rotation = AuthRotation(api_keys, cooldown_seconds=300)
            logger.info(f"Auth rotation enabled with {len(api_keys)} keys")
        else:
            self.auth_rotation = None
```

Add helper method to collect keys:

```python
    def _collect_api_keys(self, provider) -> list[str]:
        """Collect all available API keys from provider."""
        keys = []
        if hasattr(provider, 'api_key') and provider.api_key:
            keys.append(provider.api_key)
        # Add support for multiple keys from config in future
        return keys
```

Modify `_call_llm_with_fallback` to use rotation on auth errors:

```python
    async def _call_llm_with_fallback(self, messages: list, models: list) -> tuple[Any | None, Exception | None]:
        last_error = None
        for current_model in models:
            try:
                # Use rotated key if available
                if self.auth_rotation:
                    current_key = self.auth_rotation.current_key()
                    # Update provider key temporarily
                    original_key = self.provider.api_key
                    self.provider.api_key = current_key

                # Emit PRE_LLM_CALL hook
                await self.hooks.emit("PRE_LLM_CALL", messages, current_model)

                response = await self.provider.chat(
                    messages=messages,
                    tools=self.tools.get_definitions(),
                    model=current_model
                )

                # Emit POST_LLM_CALL hook
                await self.hooks.emit("POST_LLM_CALL", response, current_model)

                # Restore original key
                if self.auth_rotation:
                    self.provider.api_key = original_key

                return response, None
            except Exception as e:
                error_str = str(e).lower()

                # Check if auth/rate limit error
                if self.auth_rotation and ("401" in error_str or "429" in error_str or "rate" in error_str):
                    reason = "rate_limit" if "429" in error_str or "rate" in error_str else "auth_error"
                    self.auth_rotation.mark_failed(current_key, reason)

                    # Try rotating to next key
                    next_key = self.auth_rotation.rotate()
                    if next_key != current_key:
                        logger.info(f"Retrying with rotated key due to {reason}")
                        continue  # Retry with new key

                logger.warning(f"Model {current_model} failed: {e}")
                last_error = e
                # Emit ON_ERROR hook
                await self.hooks.emit("ON_ERROR", e, {"context": "llm_call", "model": current_model})

        return None, last_error
```

**Step 6: Run integration test**

```bash
python -m pytest tests/auth/test_rotation.py -v
```

Expected: PASS (5/5 tests)

**Step 7: Commit**

```bash
git add kabot/auth/rotation.py tests/auth/test_rotation.py kabot/agent/loop.py
git commit -m "feat(auth): add API key rotation for production reliability

- Implement AuthRotation with cooldown tracking
- Auto-rotate on 401/429 errors
- Integrate into AgentLoop LLM calls
- Add comprehensive tests

Prevents service disruption from rate limits or auth failures
by automatically rotating to next available API key."
```

---

## Summary

**Phase 11 Implementation Complete:**

1. ✅ **Auto-Compaction** - Prevents context overflow crashes
2. ✅ **Directives Parser** - Power-user inline commands
3. ✅ **Auth Rotation** - Production reliability with multi-key support

**Total Tests:** 14 new tests
**Files Created:** 6 new files
**Files Modified:** 3 existing files

**Next Steps:**
- Task 4: Input Adaptors (normalize channel events)
- Task 5: Event Injection (heartbeat with cron results)
- Task 6: Enhanced Doctor Service
