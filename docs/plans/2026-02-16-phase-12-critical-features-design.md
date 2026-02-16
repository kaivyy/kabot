# Phase 12: Critical OpenClaw Features - Design Document

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to create implementation plan from this design.

**Date:** 2026-02-16
**Status:** Design Approved ✅

## Goal

Implement critical production reliability features from OpenClaw to prevent bot crashes and enhance user control:
1. Tool Result Truncation - Prevent context overflow from large tool outputs
2. Directives Behavior - Complete Phase 11 work by consuming parsed directives

## Context

**Phase 11 Completed:**
- Context Auto-Compaction (ContextGuard + Compactor)
- Directives Parser (parsing only, no consumption)
- Auth Rotation System

**Current Gaps:**
- No tool result size limits → bot crashes on large outputs (e.g., `cat huge_file.log`)
- Directives parsed but not consumed → no behavior modification
- ~16% OpenClaw feature parity

**Phase 12 Scope:**
- Tool Result Truncation (HIGH priority - stability critical)
- Directives Behavior Implementation (HIGH priority - complete Phase 11)
- ~~Atomic Config Writes~~ - Already implemented in loader.py

---

## Architecture Overview

### Approach: Hybrid Pattern

**ToolResultTruncator** as standalone utility class (like ContextGuard, Compactor)
**Directives** as behavior modifiers checked at multiple points

### Components

1. **ToolResultTruncator** (utility class)
   - Standalone class in `kabot/agent/truncator.py`
   - Responsible for checking and truncating tool results
   - Uses tiktoken for accurate token counting
   - Limit: 30% of context window (~38K tokens for 128K context)

2. **Directives Behavior** (behavior modifiers)
   - Directives parsed by DirectiveParser (Phase 11)
   - Stored in `session.metadata['directives']`
   - Consumed at multiple points in AgentLoop:
     - `/think`: Inject reasoning prompt + increase analysis depth
     - `/verbose`: Enable debug logging + show intermediate results
     - `/elevated`: Auto-approve tools + disable restrictions

### Integration Points

- **ToolResultTruncator**: Called after tool execution, before result enters LLM context
- **Directives**: Checked at multiple points (message processing, tool execution, response generation)

### File Structure

```
kabot/agent/truncator.py                    # ToolResultTruncator class
kabot/agent/loop.py                         # Integrate truncator + consume directives
tests/agent/test_truncator.py              # Truncator tests
tests/agent/test_directives_behavior.py    # Directives behavior tests
```

---

## Components Detail

### 1. ToolResultTruncator Class

**Location:** `kabot/agent/truncator.py`

**Interface:**
```python
class ToolResultTruncator:
    """Truncates tool results to prevent context overflow."""

    def __init__(self, max_tokens: int = 128000, max_share: float = 0.3):
        """
        Args:
            max_tokens: Total context window size
            max_share: Maximum percentage of context for single tool result (0.3 = 30%)
        """
        self.max_tokens = max_tokens
        self.max_share = max_share
        self.threshold = int(max_tokens * max_share)  # ~38K tokens for 128K context

    def truncate(self, result: str, tool_name: str) -> str:
        """
        Truncate result if exceeds threshold.

        Args:
            result: Raw tool output
            tool_name: Name of tool that produced output (for logging)

        Returns:
            Original result if within limit, truncated result with warning if over
        """
        # Count tokens using tiktoken
        token_count = self._count_tokens(result)

        if token_count <= self.threshold:
            return result

        # Truncate: keep first 80% of threshold, add warning
        keep_tokens = int(self.threshold * 0.8)
        truncated = self._truncate_to_tokens(result, keep_tokens)

        warning = f"\n\n⚠️ [Output truncated: {token_count} tokens exceeds limit of {self.threshold}. Showing first {keep_tokens} tokens. Use pagination or filters to get specific data.]"

        return truncated + warning

    def _count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken with fallback."""
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model("gpt-4")
            return len(encoding.encode(text))
        except ImportError:
            # Fallback: ~4 chars per token
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

**Key Design Decisions:**
- **30% limit**: Matches OpenClaw, prevents single tool from dominating context
- **Keep first 80%**: Preserves most important context (beginning of output)
- **Graceful fallback**: Character-based estimation if tiktoken unavailable
- **Clear warning**: User knows output was truncated and why

### 2. Directives Behavior Implementation

**Location:** `kabot/agent/loop.py`

Directives are consumed at multiple points to modify agent behavior:

#### A. /think Mode - Extended Reasoning

**What it does:**
- Injects system prompt for chain-of-thought reasoning
- Increases analysis depth (reads more files, considers more edge cases)

**Implementation:**
```python
def _apply_think_mode(self, messages: list, session: Session) -> list:
    """Apply think mode if directive is active."""
    if not session.metadata.get('directives', {}).get('think'):
        return messages

    reasoning_prompt = {
        "role": "system",
        "content": (
            "Think step-by-step. Show your reasoning process explicitly before taking action. "
            "Consider edge cases, alternative approaches, and potential issues. "
            "When analyzing code, read related files to understand full context."
        )
    }

    # Insert at beginning (after system prompt if exists)
    messages.insert(0, reasoning_prompt)
    return messages
```

**Called:** Before LLM call in `_process_message()`

#### B. /verbose Mode - Debug Logging

**What it does:**
- Enables detailed logging of internal agent operations
- Appends tool results and intermediate steps to response
- Shows token usage, decision points, tool calls

**Implementation:**
```python
def _should_log_verbose(self, session: Session) -> bool:
    """Check if verbose logging is enabled."""
    return session.metadata.get('directives', {}).get('verbose', False)

def _format_verbose_output(self, tool_name: str, tool_result: str, tokens_used: int) -> str:
    """Format verbose debug output."""
    return f"\n\n[DEBUG] Tool: {tool_name}\n[DEBUG] Tokens: {tokens_used}\n[DEBUG] Result:\n{tool_result}\n"
```

**Called:** After tool execution, appended to response

#### C. /elevated Mode - Extended Permissions

**What it does:**
- Auto-approves all tool calls (no user confirmation)
- Disables workspace restrictions (can access files outside workspace)
- Enables high-risk commands

**Implementation:**
```python
def _get_tool_permissions(self, session: Session) -> dict:
    """Get tool execution permissions based on directives."""
    elevated = session.metadata.get('directives', {}).get('elevated', False)

    return {
        'auto_approve': elevated,
        'restrict_to_workspace': not elevated,
        'allow_high_risk': elevated
    }
```

**Called:** Before tool execution in `_execute_tool()`

**Key Design Decisions:**
- **Directives persist**: Stored in session.metadata, active for entire conversation
- **Multiple check points**: Directives affect different parts of system naturally
- **Graceful degradation**: If directive application fails, continue with default behavior
- **User control**: User can toggle directives mid-conversation

---

## Data Flow

### Flow 1: Tool Result Truncation

```
User Message
    ↓
AgentLoop._process_message()
    ↓
Tool Execution (e.g., ExecTool.execute())
    ↓
Raw Result (potentially huge - e.g., 200KB log file)
    ↓
ToolResultTruncator.truncate(result, tool_name)
    ↓
    ├─ Count tokens using tiktoken
    ├─ If > threshold (38K tokens):
    │   ├─ Truncate to 80% of threshold (~30K tokens)
    │   └─ Append warning message
    └─ Return (truncated or original)
    ↓
Truncated Result → LLM Context
    ↓
LLM Response (no crash, context preserved)
```

**Example:**
```
User: "cat large_log.txt"
Tool Output: 200KB text (50K tokens)
Truncator: Detects 50K > 38K threshold
Truncator: Keeps first 30K tokens + warning
LLM sees: 30K tokens + "⚠️ Output truncated..."
Result: Bot continues working, no crash
```

### Flow 2: Directives Consumption

```
User: "/think /verbose analyze this code"
    ↓
DirectiveParser.parse() [Phase 11 - already exists]
    ↓
Parsed: {
    has_directives: true,
    think_mode: true,
    verbose_mode: true,
    elevated_mode: false,
    cleaned_message: "analyze this code"
}
    ↓
Store in session.metadata['directives'] = {
    'think': True,
    'verbose': True,
    'elevated': False
}
    ↓
Cleaned message: "analyze this code"
    ↓
AgentLoop checks directives at multiple points:
    │
    ├─ Before LLM call: _apply_think_mode()
    │   └─ Inject reasoning system prompt
    │   └─ Messages: [system_prompt, reasoning_prompt, user_message]
    │
    ├─ During tool execution: _get_tool_permissions()
    │   └─ Set auto_approve=False, restrict_to_workspace=True (elevated=False)
    │
    └─ After tool execution: _should_log_verbose()
        └─ Append tool results to response
        └─ Response: "Analysis: ...\n\n[DEBUG] Tool: read_file\n[DEBUG] Result: ..."
```

**Key Points:**
- Truncation happens AFTER tool execution, BEFORE LLM sees result
- Directives are checked at multiple points (not centralized)
- Directives persist in session.metadata for entire conversation
- User can toggle directives mid-conversation with new message

---

## Error Handling

### 1. ToolResultTruncator Error Handling

**Scenarios:**

**A. tiktoken Import Failure**
```python
def _count_tokens(self, text: str) -> int:
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model("gpt-4")
        return len(encoding.encode(text))
    except ImportError:
        logger.warning("tiktoken not available, using character-based estimation")
        return len(text) // 4  # ~4 chars per token
```

**B. Token Counting Error**
```python
def truncate(self, result: str, tool_name: str) -> str:
    try:
        token_count = self._count_tokens(result)
        # ... truncation logic ...
    except Exception as e:
        logger.error(f"Truncation failed for {tool_name}: {e}")
        # Fallback: character-based truncation
        max_chars = self.threshold * 4
        if len(result) <= max_chars:
            return result

        truncated = result[:int(max_chars * 0.8)]
        warning = f"\n\n⚠️ [Output truncated: ~{len(result)} chars exceeds limit.]"
        return truncated + warning
```

**C. Truncation Failure**
```python
except Exception as e:
    logger.error(f"Critical truncation error for {tool_name}: {e}")
    # Last resort: return original with warning
    return result + f"\n\n⚠️ [Truncation failed: {e}]"
```

### 2. Directives Error Handling

**Scenarios:**

**A. Missing/Corrupted Metadata**
```python
def _apply_think_mode(self, messages: list, session: Session) -> list:
    try:
        directives = session.metadata.get('directives', {})
        if not isinstance(directives, dict):
            logger.warning("Directives metadata corrupted, using defaults")
            directives = {}

        if directives.get('think'):
            # Apply think mode
            ...
    except Exception as e:
        logger.error(f"Failed to apply think mode: {e}")
        # Continue without think mode

    return messages
```

**B. System Prompt Injection Failure**
```python
try:
    reasoning_prompt = {...}
    messages.insert(0, reasoning_prompt)
except Exception as e:
    logger.error(f"Failed to inject reasoning prompt: {e}")
    # Continue with original messages
```

**C. Tool Permission Modification Failure**
```python
def _get_tool_permissions(self, session: Session) -> dict:
    try:
        elevated = session.metadata.get('directives', {}).get('elevated', False)
        return {
            'auto_approve': elevated,
            'restrict_to_workspace': not elevated
        }
    except Exception as e:
        logger.error(f"Failed to get tool permissions: {e}")
        # Safe defaults
        return {
            'auto_approve': False,
            'restrict_to_workspace': True
        }
```

### Error Handling Principles

1. **Graceful Degradation**: Errors never crash the agent
2. **Fallback Strategies**: Always have fallback for critical operations
3. **Comprehensive Logging**: All errors logged for debugging
4. **User Transparency**: User informed if features don't work (via warnings)
5. **Safe Defaults**: On error, use safest configuration (no auto-approve, workspace restricted)

---

## Testing Strategy

### 1. ToolResultTruncator Tests

**File:** `tests/agent/test_truncator.py`

**Test Cases:**

```python
def test_truncator_allows_small_results():
    """Small results pass through unchanged."""
    truncator = ToolResultTruncator(max_tokens=128000, max_share=0.3)
    small_result = "Hello world" * 100  # ~200 tokens

    result = truncator.truncate(small_result, "test_tool")

    assert result == small_result
    assert "⚠️" not in result

def test_truncator_truncates_large_results():
    """Large results are truncated with warning."""
    truncator = ToolResultTruncator(max_tokens=128000, max_share=0.3)
    large_result = "x" * 200000  # ~50K tokens, exceeds 38K threshold

    result = truncator.truncate(large_result, "test_tool")

    assert len(result) < len(large_result)
    assert "⚠️" in result
    assert "Output truncated" in result
    assert str(50000) in result  # Shows original token count

def test_truncator_preserves_beginning():
    """Truncation preserves beginning of output (most important context)."""
    truncator = ToolResultTruncator(max_tokens=128000, max_share=0.3)
    large_result = "IMPORTANT_START" + ("x" * 200000) + "END"

    result = truncator.truncate(large_result, "test_tool")

    assert "IMPORTANT_START" in result
    assert "END" not in result

def test_truncator_fallback_on_tiktoken_error():
    """Falls back to char-based truncation if tiktoken fails."""
    truncator = ToolResultTruncator(max_tokens=128000, max_share=0.3)

    # Mock tiktoken to raise exception
    with patch('tiktoken.encoding_for_model', side_effect=Exception("Mock error")):
        large_result = "x" * 200000
        result = truncator.truncate(large_result, "test_tool")

        assert len(result) < len(large_result)
        assert "⚠️" in result

def test_truncator_handles_empty_result():
    """Handles empty results gracefully."""
    truncator = ToolResultTruncator(max_tokens=128000, max_share=0.3)

    result = truncator.truncate("", "test_tool")

    assert result == ""

def test_truncator_custom_threshold():
    """Respects custom threshold configuration."""
    truncator = ToolResultTruncator(max_tokens=128000, max_share=0.5)  # 50%

    assert truncator.threshold == 64000  # 50% of 128K
```

### 2. Directives Behavior Tests

**File:** `tests/agent/test_directives_behavior.py`

**Test Cases:**

```python
async def test_think_mode_injects_reasoning_prompt():
    """Think mode adds reasoning system prompt."""
    session = Session(session_id="test", user_id="user1")
    session.metadata['directives'] = {'think': True, 'verbose': False, 'elevated': False}

    loop = AgentLoop(...)
    messages = [{"role": "user", "content": "test"}]

    modified = loop._apply_think_mode(messages, session)

    assert len(modified) > len(messages)
    assert any("reasoning" in str(m).lower() for m in modified)
    assert any("step-by-step" in str(m).lower() for m in modified)

async def test_think_mode_disabled_by_default():
    """Think mode not applied when directive not set."""
    session = Session(session_id="test", user_id="user1")
    # No directives set

    loop = AgentLoop(...)
    messages = [{"role": "user", "content": "test"}]

    modified = loop._apply_think_mode(messages, session)

    assert modified == messages  # Unchanged

async def test_verbose_mode_shows_tool_results():
    """Verbose mode appends tool results to response."""
    session = Session(session_id="test", user_id="user1")
    session.metadata['directives'] = {'think': False, 'verbose': True, 'elevated': False}

    loop = AgentLoop(...)

    assert loop._should_log_verbose(session) is True

    # Test verbose output formatting
    verbose_output = loop._format_verbose_output("read_file", "file contents", 150)
    assert "[DEBUG]" in verbose_output
    assert "read_file" in verbose_output
    assert "150" in verbose_output

async def test_elevated_mode_auto_approves():
    """Elevated mode sets auto_approve flag."""
    session = Session(session_id="test", user_id="user1")
    session.metadata['directives'] = {'think': False, 'verbose': False, 'elevated': True}

    loop = AgentLoop(...)
    perms = loop._get_tool_permissions(session)

    assert perms['auto_approve'] is True
    assert perms['restrict_to_workspace'] is False
    assert perms['allow_high_risk'] is True

async def test_elevated_mode_disabled_by_default():
    """Elevated mode uses safe defaults when not set."""
    session = Session(session_id="test", user_id="user1")
    # No directives set

    loop = AgentLoop(...)
    perms = loop._get_tool_permissions(session)

    assert perms['auto_approve'] is False
    assert perms['restrict_to_workspace'] is True
    assert perms['allow_high_risk'] is False

async def test_directives_persist_across_messages():
    """Directives remain active for entire session."""
    session = Session(session_id="test", user_id="user1")

    # First message with /think
    msg1 = Message(role="user", content="/think analyze code")
    # ... process message, directives stored ...

    # Second message without directives
    msg2 = Message(role="user", content="continue analysis")

    # Directives should still be active
    assert session.metadata['directives']['think'] is True

async def test_multiple_directives_combined():
    """Multiple directives can be active simultaneously."""
    session = Session(session_id="test", user_id="user1")
    session.metadata['directives'] = {'think': True, 'verbose': True, 'elevated': False}

    loop = AgentLoop(...)

    # Think mode applied
    messages = [{"role": "user", "content": "test"}]
    modified = loop._apply_think_mode(messages, session)
    assert len(modified) > len(messages)

    # Verbose mode active
    assert loop._should_log_verbose(session) is True

    # Elevated mode not active
    perms = loop._get_tool_permissions(session)
    assert perms['auto_approve'] is False

async def test_directives_error_handling():
    """Directives handle corrupted metadata gracefully."""
    session = Session(session_id="test", user_id="user1")
    session.metadata['directives'] = "corrupted_string"  # Should be dict

    loop = AgentLoop(...)

    # Should not crash, use safe defaults
    perms = loop._get_tool_permissions(session)
    assert perms['auto_approve'] is False
    assert perms['restrict_to_workspace'] is True
```

### 3. Integration Tests

**File:** `tests/agent/test_phase12_integration.py`

**Test Cases:**

```python
async def test_full_flow_with_truncation():
    """Test complete flow: user message → tool execution → truncation → LLM response."""
    # Setup agent with truncator
    # Execute tool that returns large output
    # Verify output was truncated
    # Verify LLM received truncated version
    # Verify bot didn't crash

async def test_full_flow_with_directives():
    """Test complete flow: user message with directives → behavior modification."""
    # Send message: "/think /verbose read large_file.txt"
    # Verify directives parsed and stored
    # Verify think mode applied (reasoning prompt injected)
    # Verify verbose mode applied (debug output shown)
    # Verify tool executed with correct permissions

async def test_truncation_with_directives():
    """Test truncation works correctly with verbose mode."""
    # Enable verbose mode
    # Execute tool with large output
    # Verify output truncated
    # Verify verbose debug info still shown
```

### Test Coverage Target

- **Unit Tests**: >80% coverage for new code
- **Integration Tests**: Cover critical user flows
- **Error Cases**: Test all error handling paths

### Test Execution

```bash
# Run all Phase 12 tests
pytest tests/agent/test_truncator.py -v
pytest tests/agent/test_directives_behavior.py -v
pytest tests/agent/test_phase12_integration.py -v

# Run with coverage
pytest tests/agent/test_truncator.py --cov=kabot.agent.truncator --cov-report=term-missing
pytest tests/agent/test_directives_behavior.py --cov=kabot.agent.loop --cov-report=term-missing
```

---

## Implementation Notes

### Dependencies

- **tiktoken**: For accurate token counting (already used in Phase 11 ContextGuard)
- **loguru**: For logging (already in use)
- **pytest**: For testing (already in use)

### Configuration

No new configuration needed. Uses existing:
- `agents.defaults.max_tokens` (128000) for context window size
- Tool truncation uses hardcoded 30% share (matches OpenClaw)

### Backwards Compatibility

- **Tool truncation**: Transparent to existing code, just wraps tool results
- **Directives**: Opt-in feature, no impact if not used
- **No breaking changes**: All changes are additive

### Performance Considerations

- **Token counting overhead**: ~1-5ms per tool result (negligible)
- **Truncation overhead**: Only when result exceeds threshold (rare)
- **Directives overhead**: Simple dict lookups (negligible)

### Security Considerations

- **Elevated mode**: Dangerous if misused, requires explicit user opt-in
- **Tool truncation**: Prevents DoS via large outputs
- **No new attack surface**: Features are defensive in nature

---

## Success Criteria

### Phase 12 Complete When:

1. ✅ **ToolResultTruncator implemented**
   - Class created with truncate() method
   - Uses tiktoken for token counting
   - Fallback to character-based estimation
   - 30% context window limit enforced

2. ✅ **Directives behavior implemented**
   - `/think` mode: reasoning prompt + deeper analysis
   - `/verbose` mode: debug logging + intermediate results
   - `/elevated` mode: auto-approve + extended permissions
   - All three directives consumed from session.metadata

3. ✅ **Integration complete**
   - Truncator called after all tool executions
   - Directives checked at appropriate points in AgentLoop
   - No breaking changes to existing functionality

4. ✅ **Tests passing**
   - >80% test coverage for new code
   - All unit tests passing
   - Integration tests passing

5. ✅ **Documentation updated**
   - Implementation log created
   - User-facing docs explain directives usage

### Validation

```bash
# All tests pass
pytest tests/agent/test_truncator.py -v
pytest tests/agent/test_directives_behavior.py -v

# Manual validation
# 1. Execute tool with large output → verify truncation
# 2. Send "/think analyze code" → verify reasoning shown
# 3. Send "/verbose read file" → verify debug output
# 4. Send "/elevated exec command" → verify auto-approval
```

---

## Next Steps

After design approval:
1. Invoke `superpowers:writing-plans` skill to create detailed implementation plan
2. Execute plan using subagent-driven development (Phase 11 pattern)
3. Create implementation log in `docs/logs/`
4. Update user documentation

---

## References

- **OpenClaw Analysis**: `docs/openclaw-analysis/deep-technical-findings.md`
- **Phase 11 Implementation**: `docs/logs/2026-02-15-phase-11-openclaw-parity.md`
- **Phase 11 Plan**: `docs/plans/2026-02-15-openclaw-parity-phase-11.md`
- **Verification Report**: Conversation 2026-02-15 (OpenClaw feature verification)
