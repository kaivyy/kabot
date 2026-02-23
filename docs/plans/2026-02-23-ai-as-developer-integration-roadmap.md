# AI-as-Developer Integration Roadmap

> **Integration Document**: This document reconciles `2026-02-23-openclaw-parity.md` (tactical implementation) with `AI-AS-DEVELOPER-GAP-ANALYSIS.md` (strategic analysis) into a unified roadmap.

## Executive Summary

**Purpose**: Achieve OpenClaw parity for Kabot's AI-as-Developer capabilities through a phased approach that combines immediate tactical wins with strategic long-term improvements.

**Timeline**:
- **Phase 0 (Immediate)**: ~95 minutes - 6 tactical modules from parity plan
- **Phase 1-4 (Strategic)**: 8 weeks - Complete gap closure with comprehensive testing

**Priority Alignment**:
- **P0/HIGH**: Critical for production stability and user safety
- **P1/MEDIUM**: Important for developer experience and reliability
- **P2/LOW**: Nice-to-have enhancements

---

## Phase 0: Immediate Tactical Wins (~95 minutes)

**Goal**: Implement 6 OpenClaw parity modules for immediate impact.

### Task 1: Context Window Guard (P0/HIGH) - 15 min
**Gap Analysis Mapping**: Auto Compaction (Category 8)

**Files**:
- Create: `kabot/agent/context_guard.py`
- Modify: `kabot/agent/loop.py:_call_llm()`

**Implementation**:
```python
# kabot/agent/context_guard.py
class ContextWindowGuard:
    def __init__(self, model_limits: dict[str, int]):
        self.model_limits = model_limits
        self.warning_threshold = 0.85
        self.critical_threshold = 0.95

    def check_usage(self, messages: list, model: str) -> dict:
        limit = self.model_limits.get(model, 200000)
        estimated_tokens = self._estimate_tokens(messages)
        usage_ratio = estimated_tokens / limit

        return {
            "estimated_tokens": estimated_tokens,
            "limit": limit,
            "usage_ratio": usage_ratio,
            "status": self._get_status(usage_ratio),
            "should_compact": usage_ratio >= self.warning_threshold
        }
```

**Test**:
```bash
pytest tests/agent/test_context_guard.py -v
```

**Success Criteria**: Context usage monitoring active, warnings at 85%, compaction triggered at 95%

---

### Task 2: Context Compaction (P0/HIGH) - 20 min
**Gap Analysis Mapping**: Auto Compaction (Category 8)

**Files**:
- Create: `kabot/agent/compaction.py`
- Modify: `kabot/agent/loop.py:_call_llm()`

**Implementation**:
```python
# kabot/agent/compaction.py
class ContextCompactor:
    def compact(self, messages: list) -> list:
        # Keep system prompt + last 3 exchanges
        system_msgs = [m for m in messages if m["role"] == "system"]
        recent_msgs = messages[-6:]  # Last 3 user-assistant pairs

        # Summarize middle section
        middle_msgs = messages[len(system_msgs):-6]
        if middle_msgs:
            summary = self._summarize_middle(middle_msgs)
            return system_msgs + [summary] + recent_msgs
        return messages

    def _summarize_middle(self, messages: list) -> dict:
        # Extract key facts, decisions, file changes
        summary_text = "Previous context summary:\n"
        summary_text += self._extract_key_facts(messages)
        return {"role": "user", "content": summary_text}
```

**Test**:
```bash
pytest tests/agent/test_compaction.py -v
```

**Success Criteria**: Context compaction reduces token usage by 60-80% while preserving critical information

---

### Task 3: Tool Loop Detection (P1/MEDIUM) - 15 min
**Gap Analysis Mapping**: Execute-and-Verify (Category 1), Auto-Retry (Category 2)

**Files**:
- Create: `kabot/agent/loop_detector.py`
- Modify: `kabot/agent/loop.py:_execute_tool()`

**Implementation**:
```python
# kabot/agent/loop_detector.py
class ToolLoopDetector:
    def __init__(self, window_size: int = 5, threshold: int = 3):
        self.window_size = window_size
        self.threshold = threshold
        self.recent_calls: list[tuple[str, dict]] = []

    def check_loop(self, tool_name: str, params: dict) -> bool:
        call_signature = (tool_name, self._normalize_params(params))
        self.recent_calls.append(call_signature)

        if len(self.recent_calls) > self.window_size:
            self.recent_calls.pop(0)

        count = self.recent_calls.count(call_signature)
        return count >= self.threshold
```

**Test**:
```bash
pytest tests/agent/test_loop_detector.py -v
```

**Success Criteria**: Detect and break loops after 3 identical tool calls within 5-call window

---

### Task 4: Tool Policy Profiles (P1/MEDIUM) - 20 min
**Gap Analysis Mapping**: Tool Policies (Category 5)

**Files**:
- Create: `kabot/agent/tool_policies.py`
- Modify: `kabot/agent/loop.py:_execute_tool()`

**Implementation**:
```python
# kabot/agent/tool_policies.py
class ToolPolicyProfile:
    PROFILES = {
        "safe": {
            "allowed_tools": ["read_file", "search_files", "web_search"],
            "blocked_tools": ["exec", "write_file", "delete_file"],
            "require_confirmation": []
        },
        "standard": {
            "allowed_tools": "*",
            "blocked_tools": ["rm -rf*", "format*"],
            "require_confirmation": ["exec", "write_file"]
        },
        "developer": {
            "allowed_tools": "*",
            "blocked_tools": [],
            "require_confirmation": ["rm*", "git push --force"]
        }
    }

    def check_policy(self, tool_name: str, params: dict, profile: str) -> dict:
        policy = self.PROFILES.get(profile, self.PROFILES["standard"])

        if tool_name in policy["blocked_tools"]:
            return {"allowed": False, "reason": "Tool blocked by policy"}

        if tool_name in policy["require_confirmation"]:
            return {"allowed": True, "requires_confirmation": True}

        return {"allowed": True, "requires_confirmation": False}
```

**Test**:
```bash
pytest tests/agent/test_tool_policies.py -v
```

**Success Criteria**: Policy profiles enforce tool restrictions, confirmation prompts work

---

### Task 5: Failover Error Classification (P2/LOW) - 15 min
**Gap Analysis Mapping**: Auto-Retry (Category 2)

**Files**:
- Create: `kabot/agent/error_classifier.py`
- Modify: `kabot/agent/loop.py:_handle_error()`

**Implementation**:
```python
# kabot/agent/error_classifier.py
class ErrorClassifier:
    RETRYABLE_ERRORS = {
        "rate_limit": ["429", "rate limit", "too many requests"],
        "timeout": ["timeout", "timed out", "connection timeout"],
        "network": ["connection refused", "network error", "dns"],
        "temporary": ["503", "service unavailable", "temporary"]
    }

    NON_RETRYABLE_ERRORS = {
        "auth": ["401", "403", "unauthorized", "forbidden"],
        "not_found": ["404", "not found"],
        "validation": ["400", "bad request", "invalid"],
        "syntax": ["syntax error", "parse error"]
    }

    def classify(self, error: Exception) -> dict:
        error_str = str(error).lower()

        for category, patterns in self.RETRYABLE_ERRORS.items():
            if any(p in error_str for p in patterns):
                return {"retryable": True, "category": category, "strategy": self._get_strategy(category)}

        for category, patterns in self.NON_RETRYABLE_ERRORS.items():
            if any(p in error_str for p in patterns):
                return {"retryable": False, "category": category, "strategy": "fail"}

        return {"retryable": False, "category": "unknown", "strategy": "fail"}
```

**Test**:
```bash
pytest tests/agent/test_error_classifier.py -v
```

**Success Criteria**: Errors correctly classified as retryable/non-retryable with appropriate strategies

---

### Task 6: Session Tool Result Guard (P2/LOW) - 10 min
**Gap Analysis Mapping**: Security & Validation (Category 6)

**Files**:
- Create: `kabot/agent/result_guard.py`
- Modify: `kabot/agent/loop.py:_execute_tool()`

**Implementation**:
```python
# kabot/agent/result_guard.py
class ToolResultGuard:
    MAX_RESULT_SIZE = 50000  # 50KB
    SENSITIVE_PATTERNS = [
        r"sk-[a-zA-Z0-9]{48}",  # OpenAI API keys
        r"ghp_[a-zA-Z0-9]{36}",  # GitHub tokens
        r"xox[baprs]-[a-zA-Z0-9-]+",  # Slack tokens
    ]

    def sanitize(self, result: str) -> dict:
        issues = []

        # Check size
        if len(result) > self.MAX_RESULT_SIZE:
            result = result[:self.MAX_RESULT_SIZE] + "\n[TRUNCATED]"
            issues.append("Result truncated due to size")

        # Check for sensitive data
        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, result):
                result = re.sub(pattern, "[REDACTED]", result)
                issues.append("Sensitive data redacted")

        return {"result": result, "issues": issues}
```

**Test**:
```bash
pytest tests/agent/test_result_guard.py -v
```

**Success Criteria**: Large results truncated, sensitive data redacted

---

## Phase 1: Critical Gaps (Week 1-2)

**Goal**: Address HIGH priority gaps from gap analysis not covered in Phase 0.

### Task 7: Model Fallback Chains (HIGH) - 2 days
**Gap Analysis Reference**: Category 2 (Auto-Retry/Self-Healing)

**Files**:
- Create: `kabot/agent/model_fallback.py`
- Modify: `kabot/agent/loop.py:_call_llm()`
- Test: `tests/agent/test_model_fallback.py`

**Implementation**:
```python
class ModelFallbackChain:
    def __init__(self, primary: str, fallbacks: list[str]):
        self.primary = primary
        self.fallbacks = fallbacks
        self.current_index = 0

    async def call_with_fallback(self, messages: list) -> dict:
        models = [self.primary] + self.fallbacks

        for i, model in enumerate(models):
            try:
                result = await self._call_model(model, messages)
                if i > 0:
                    logger.info(f"Fallback to {model} succeeded")
                return result
            except Exception as e:
                if i == len(models) - 1:
                    raise
                logger.warning(f"Model {model} failed, trying fallback")
                continue
```

**Success Criteria**: Automatic fallback to secondary models on primary failure

---

### Task 8: Preflight Validation (HIGH) - 2 days
**Gap Analysis Reference**: Category 6 (Security & Validation)

**Files**:
- Create: `kabot/agent/preflight.py`
- Modify: `kabot/agent/tools/exec.py`
- Test: `tests/agent/test_preflight.py`

**Implementation**:
```python
class PreflightValidator:
    DANGEROUS_PATTERNS = [
        r";\s*rm\s+-rf",  # Command injection
        r"\$\([^)]+\)",  # Command substitution
        r"`[^`]+`",  # Backtick execution
        r">\s*/dev/",  # Device file writes
    ]

    def validate_command(self, cmd: str) -> dict:
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, cmd):
                return {
                    "safe": False,
                    "reason": f"Dangerous pattern detected: {pattern}",
                    "action": "block"
                }
        return {"safe": True}
```

**Success Criteria**: Shell injection attempts blocked before execution

---

### Task 9: Sandbox Security Validation (HIGH) - 2 days
**Gap Analysis Reference**: Category 6 (Security & Validation)

**Files**:
- Create: `kabot/agent/sandbox_validator.py`
- Modify: `kabot/agent/tools/exec.py`
- Test: `tests/agent/test_sandbox_validator.py`

**Implementation**:
```python
class SandboxValidator:
    def validate_docker_config(self, config: dict) -> dict:
        issues = []

        # Check for privileged mode
        if config.get("privileged"):
            issues.append("Privileged mode not allowed")

        # Check volume mounts
        for mount in config.get("volumes", []):
            if mount.startswith("/"):
                issues.append(f"Absolute path mount not allowed: {mount}")

        return {"valid": len(issues) == 0, "issues": issues}
```

**Success Criteria**: Docker sandbox configurations validated for security

---

### Task 10: Workspace Root Guards (HIGH) - 1 day
**Gap Analysis Reference**: Category 6 (Security & Validation)

**Files**:
- Create: `kabot/agent/workspace_guard.py`
- Modify: `kabot/agent/tools/write_file.py`, `kabot/agent/tools/exec.py`
- Test: `tests/agent/test_workspace_guard.py`

**Implementation**:
```python
class WorkspaceGuard:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root.resolve()

    def validate_path(self, path: Path) -> dict:
        resolved = path.resolve()

        # Check if path is within workspace
        try:
            resolved.relative_to(self.workspace_root)
            return {"valid": True}
        except ValueError:
            return {
                "valid": False,
                "reason": f"Path {resolved} is outside workspace {self.workspace_root}"
            }
```

**Success Criteria**: File operations restricted to workspace directory

---

## Phase 2: Developer Experience (Week 3-4)

**Goal**: Improve reliability and debugging capabilities.

### Task 11: Enhanced Execute-and-Verify (MEDIUM) - 3 days
**Gap Analysis Reference**: Category 1 (Execute-and-Verify)

**Enhancement**: Add verification templates for common operations
- File write → Read back and compare
- Git commit → Verify with git log
- Package install → Import test
- Config change → Validate syntax

**Files**:
- Enhance: `kabot/agent/verification.py`
- Test: `tests/agent/test_verification_enhanced.py`

---

### Task 12: Retry Strategy Profiles (MEDIUM) - 2 days
**Gap Analysis Reference**: Category 2 (Auto-Retry/Self-Healing)

**Enhancement**: Configurable retry strategies
- Exponential backoff for rate limits
- Immediate retry for network errors
- No retry for validation errors

**Files**:
- Create: `kabot/agent/retry_strategies.py`
- Test: `tests/agent/test_retry_strategies.py`

---

### Task 13: Subagent Monitoring Dashboard (MEDIUM) - 3 days
**Gap Analysis Reference**: Category 3 (Workflow Orchestration)

**Enhancement**: Real-time subagent status tracking
- Active subagents count
- Task completion status
- Resource usage per subagent

**Files**:
- Create: `kabot/agent/subagent_monitor.py`
- Test: `tests/agent/test_subagent_monitor.py`

---

## Phase 3: Advanced Features (Week 5-6)

**Goal**: Add sophisticated capabilities for complex workflows.

### Task 14: Kill/Abort Subagent Operations (HIGH) - 2 days
**Gap Analysis Reference**: Category 3 (Workflow Orchestration)

**Files**:
- Create: `kabot/agent/subagent_control.py`
- Modify: `kabot/agent/subagent_registry.py`
- Test: `tests/agent/test_subagent_control.py`

---

### Task 15: Symlink Escape Detection (MEDIUM) - 2 days
**Gap Analysis Reference**: Category 6 (Security & Validation)

**Files**:
- Enhance: `kabot/agent/workspace_guard.py`
- Test: `tests/agent/test_symlink_detection.py`

---

### Task 16: Code Generation Validation (MEDIUM) - 3 days
**Gap Analysis Reference**: Category 7 (Code Generation & Validation)

**Enhancement**: Syntax validation before file write
- Python: ast.parse()
- JavaScript: esprima
- JSON: json.loads()

**Files**:
- Create: `kabot/agent/code_validator.py`
- Test: `tests/agent/test_code_validator.py`

---

## Phase 4: Polish & Optimization (Week 7-8)

**Goal**: Refine implementations and optimize performance.

### Task 17: Comprehensive Integration Tests - 3 days
**Files**:
- Create: `tests/integration/test_ai_as_developer_full.py`

**Test Scenarios**:
1. Context overflow → Auto-compaction → Continued execution
2. Tool loop → Detection → Break with explanation
3. Model failure → Fallback chain → Success
4. Shell injection attempt → Preflight block → User warning
5. Subagent spawn → Monitor → Kill on timeout

---

### Task 18: Performance Optimization - 2 days
**Focus**:
- Context guard caching
- Error classification memoization
- Subagent pool reuse

---

### Task 19: Documentation & Examples - 3 days
**Files**:
- Update: `docs/AI-AS-DEVELOPER-COMPLETE.md`
- Create: `docs/examples/ai-as-developer-workflows.md`

---

## Priority Matrix

| Feature | Phase 0 | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Priority |
|---------|---------|---------|---------|---------|---------|----------|
| Context Window Guard | ✓ | | | | | P0/HIGH |
| Context Compaction | ✓ | | | | | P0/HIGH |
| Tool Loop Detection | ✓ | | | | | P1/MEDIUM |
| Tool Policy Profiles | ✓ | | | | | P1/MEDIUM |
| Error Classification | ✓ | | | | | P2/LOW |
| Result Guard | ✓ | | | | | P2/LOW |
| Model Fallback | | ✓ | | | | HIGH |
| Preflight Validation | | ✓ | | | | HIGH |
| Sandbox Validation | | ✓ | | | | HIGH |
| Workspace Guards | | ✓ | | | | HIGH |
| Enhanced Verify | | | ✓ | | | MEDIUM |
| Retry Strategies | | | ✓ | | | MEDIUM |
| Subagent Monitor | | | ✓ | | | MEDIUM |
| Kill/Abort | | | | ✓ | | HIGH |
| Symlink Detection | | | | ✓ | | MEDIUM |
| Code Validation | | | | ✓ | | MEDIUM |
| Integration Tests | | | | | ✓ | HIGH |
| Performance | | | | | ✓ | MEDIUM |
| Documentation | | | | | ✓ | MEDIUM |

---

## Success Criteria

### Phase 0 (Immediate)
- [ ] All 6 modules implemented with tests passing
- [ ] Context usage reduced by 60-80% with compaction
- [ ] Tool loops detected and broken automatically
- [ ] Policy profiles enforce restrictions
- [ ] Errors classified correctly
- [ ] Sensitive data redacted from results

### Phase 1 (Critical Gaps)
- [ ] Model fallback chains work automatically
- [ ] Shell injection attempts blocked
- [ ] Docker sandbox configs validated
- [ ] File operations restricted to workspace

### Phase 2 (Developer Experience)
- [ ] Verification templates cover common operations
- [ ] Retry strategies configurable per error type
- [ ] Subagent monitoring dashboard functional

### Phase 3 (Advanced Features)
- [ ] Subagents can be killed/aborted
- [ ] Symlink escapes detected and blocked
- [ ] Code syntax validated before write

### Phase 4 (Polish)
- [ ] All integration tests passing
- [ ] Performance benchmarks meet targets
- [ ] Documentation complete with examples

---

## Cross-References

**From Gap Analysis to Parity Plan**:
- Category 1 (Execute-and-Verify) → Task 3 (Loop Detection), Task 11 (Enhanced Verify)
- Category 2 (Auto-Retry) → Task 5 (Error Classification), Task 7 (Model Fallback), Task 12 (Retry Strategies)
- Category 3 (Orchestration) → Task 13 (Subagent Monitor), Task 14 (Kill/Abort)
- Category 5 (Tool Policies) → Task 4 (Policy Profiles)
- Category 6 (Security) → Task 6 (Result Guard), Task 8 (Preflight), Task 9 (Sandbox), Task 10 (Workspace Guards), Task 15 (Symlink Detection)
- Category 7 (Code Generation) → Task 16 (Code Validation)
- Category 8 (Context Management) → Task 1 (Context Guard), Task 2 (Compaction)

**From Parity Plan to Gap Analysis**:
- Task 1 (Context Guard) → Category 8 (Context Management)
- Task 2 (Compaction) → Category 8 (Context Management)
- Task 3 (Loop Detection) → Category 1 (Execute-and-Verify), Category 2 (Auto-Retry)
- Task 4 (Policy Profiles) → Category 5 (Tool Policies)
- Task 5 (Error Classification) → Category 2 (Auto-Retry)
- Task 6 (Result Guard) → Category 6 (Security & Validation)

---

## Timeline Clarification

**95 Minutes (Phase 0)**: Tactical implementation of 6 core modules for immediate production use. These are well-defined, isolated changes with clear test cases.

**8 Weeks (Phase 1-4)**: Strategic implementation of remaining gaps with comprehensive testing, documentation, and optimization. This includes more complex features requiring design decisions, integration work, and thorough validation.

**Relationship**: Phase 0 provides immediate value and can be deployed independently. Phases 1-4 build on Phase 0 to achieve complete OpenClaw parity with production-grade quality.

---

## Next Steps

1. **Review this integration roadmap** with stakeholders
2. **Execute Phase 0** (95 minutes) for immediate wins
3. **Validate Phase 0** in production environment
4. **Begin Phase 1** (Week 1-2) for critical gaps
5. **Iterate** through Phases 2-4 based on feedback

---

## Maintenance

This document should be updated:
- After each phase completion
- When new gaps are identified
- When priorities change based on production feedback
- When OpenClaw introduces new features

**Last Updated**: 2026-02-23
**Version**: 1.0
**Status**: Ready for Review
