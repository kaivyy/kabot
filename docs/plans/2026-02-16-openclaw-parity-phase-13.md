# OpenClaw Parity Phase 13: Resilience & Security Hardening

> **Status**: 🟡 Planning
> **Date**: 2026-02-16
> **Prerequisites**: Phase 12 Complete (Directives, ToolResultTruncator, Context Guard)
> **Target Parity**: 65% → 85%

---

## Executive Summary

Phase 13 focuses on closing critical gaps in **Resilience** and **Security** to bring kabot from 65% to 85% OpenClaw parity. Based on the gap analysis verification, we have strong intelligence (95%) but weak resilience (60%) and security (45%).

### Current State (Verified 2026-02-16)

| Category | Current % | Target % | Priority |
|----------|-----------|----------|----------|
| 🛡️ Resilience | 60% | 90% | 🔴 Critical |
| 👮 Security | 45% | 80% | 🔴 Critical |
| 🧠 Intelligence | 95% | 95% | ✅ Maintain |

### Critical Gaps to Address

1. **PID Locking** (0% → 100%) - Prevents race conditions in multi-process scenarios
2. **Windows ACL Security** (0% → 100%) - Currently explicitly skipped, contradicts gap analysis
3. **Crash Recovery Sentinel** (0% → 100%) - Seamless recovery UX after crashes
4. **Granular Command Approvals** (40% → 100%) - Allowlist/deny patterns with tamper-proofing
5. **Security Audit Completion** (50% → 100%) - Enable Windows checks, add network validation

---

## Phase 13 Implementation Plan

### Task 1: PID Locking System
**Priority**: 🔴 Critical
**Estimated Complexity**: Medium
**Files to Create/Modify**:
- `kabot/utils/pid_lock.py` (new)
- `kabot/config/loader.py` (modify)
- `kabot/memory/chroma_memory.py` (modify)
- `tests/utils/test_pid_lock.py` (new)

**Implementation Steps**:

1.1. Create `PIDLock` class with file-based locking
```python
class PIDLock:
    """
    File-based process locking with stale lock recovery.
    Pattern from OpenClaw: agents/session-write-lock.ts
    """
    def __init__(self, lock_path: Path, timeout: int = 30):
        self.lock_path = lock_path
        self.lock_file = lock_path.with_suffix('.lock')
        self.timeout = timeout
        self.pid = os.getpid()

    def acquire(self) -> bool:
        """Acquire lock, stealing from dead processes if needed."""
        pass

    def release(self) -> None:
        """Release lock and clean up lock file."""
        pass

    def _is_process_alive(self, pid: int) -> bool:
        """Check if process is still running (cross-platform)."""
        pass
```

1.2. Integrate with config loader
- Wrap `save_config()` with PIDLock
- Wrap `load_config()` with PIDLock for consistency

1.3. Integrate with memory system
- Wrap ChromaDB operations that modify collections
- Protect metadata SQLite writes

1.4. Add comprehensive tests
- Test normal lock/unlock flow
- Test stale lock recovery (simulate dead process)
- Test timeout behavior
- Test cross-platform compatibility (Windows/Linux)

**Acceptance Criteria**:
- ✅ No race conditions when multiple processes access same files
- ✅ Stale locks automatically recovered
- ✅ Works on Windows and Linux
- ✅ 90%+ test coverage

---

### Task 2: Crash Recovery Sentinel
**Priority**: 🔴 Critical
**Estimated Complexity**: Medium
**Files to Create/Modify**:
- `kabot/core/sentinel.py` (new)
- `kabot/agent/loop.py` (modify)
- `kabot/main.py` (modify)
- `tests/core/test_sentinel.py` (new)

**Implementation Steps**:

2.1. Create `CrashSentinel` class
```python
class CrashSentinel:
    """
    Black box recorder for crash recovery.
    Pattern from OpenClaw: server-restart-sentinel.ts
    """
    def __init__(self, sentinel_path: Path):
        self.sentinel_path = sentinel_path
        self.session_id: Optional[str] = None
        self.last_message_id: Optional[str] = None

    def mark_session_active(self, session_id: str, message_id: str) -> None:
        """Write sentinel file before processing message."""
        pass

    def clear_sentinel(self) -> None:
        """Remove sentinel on clean shutdown."""
        pass

    def check_for_crash(self) -> Optional[Dict[str, str]]:
        """On startup, check if previous session crashed."""
        pass
```

2.2. Integrate with agent loop
- Call `mark_session_active()` before processing each message
- Call `clear_sentinel()` on clean shutdown
- On startup, check for crash and send recovery message

2.3. Add recovery message template
```python
RECOVERY_MESSAGE = """
🔄 I just restarted after an unexpected shutdown.

Last session: {session_id}
Last message: {message_id}

I'm back online and ready to continue. What were we working on?
"""
```

2.4. Add tests
- Test sentinel creation/deletion
- Test crash detection on restart
- Test clean shutdown (no sentinel)

**Acceptance Criteria**:
- ✅ Sentinel file created before each message processing
- ✅ Sentinel cleared on clean shutdown
- ✅ Recovery message sent after crash
- ✅ User experience is seamless

---

### Task 3: Windows ACL Security
**Priority**: 🔴 Critical
**Estimated Complexity**: High
**Files to Modify**:
- `kabot/utils/security_audit.py` (modify)
- `kabot/utils/windows_acl.py` (new)
- `tests/utils/test_windows_acl.py` (new)

**Implementation Steps**:

3.1. Create `WindowsACL` utility class
```python
class WindowsACL:
    """
    Windows ACL checker using icacls.
    Pattern from OpenClaw: security/windows-acl.ts
    """
    @staticmethod
    def check_directory_permissions(path: Path) -> List[SecurityFinding]:
        """Check if directory has secure permissions."""
        pass

    @staticmethod
    def is_world_writable(path: Path) -> bool:
        """Check if Everyone/Users has write access."""
        pass

    @staticmethod
    def get_acl_info(path: Path) -> Dict[str, Any]:
        """Parse icacls output into structured data."""
        pass
```

3.2. Remove Windows skip in security_audit.py
- **REMOVE** lines 67-68: `if os.name == "nt": return findings`
- Add Windows-specific checks using WindowsACL class

3.3. Add security checks
- Config directory should NOT be world-writable
- State directory should NOT be world-writable
- Memory database should NOT be world-readable
- Warn if running as Administrator unnecessarily

3.4. Add tests (Windows-specific)
- Test ACL parsing
- Test world-writable detection
- Test secure vs insecure configurations

**Acceptance Criteria**:
- ✅ Windows ACL checks enabled (not skipped)
- ✅ Detects insecure file permissions
- ✅ Clear remediation instructions in findings
- ✅ Works on Windows 10/11

---

### Task 4: Granular Command Approvals
**Priority**: 🟠 High
**Estimated Complexity**: High
**Files to Create/Modify**:
- `kabot/security/command_firewall.py` (new)
- `kabot/agent/loop.py` (modify)
- `kabot/config/schemas.py` (modify)
- `tests/security/test_command_firewall.py` (new)

**Implementation Steps**:

4.1. Create `CommandFirewall` class
```python
class CommandFirewall:
    """
    Granular command execution firewall.
    Pattern from OpenClaw: infra/exec-approvals.ts
    """
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.policy: Dict[str, Any] = self._load_policy()
        self.config_hash: str = self._compute_hash()

    def check_command(self, command: str) -> ApprovalDecision:
        """
        Returns: ALLOW, DENY, or ASK
        """
        pass

    def _verify_integrity(self) -> bool:
        """Detect if config was tampered with."""
        pass
```

4.2. Define approval policies
```yaml
# config/command_approvals.yaml
policy: "ask"  # deny | ask | allowlist

allowlist:
  - pattern: "git status"
    description: "Safe read-only git command"
  - pattern: "npm test *"
    description: "Run tests with any arguments"
  - pattern: "ls *"
    description: "List directory contents"

denylist:
  - pattern: "rm -rf *"
    description: "Dangerous recursive delete"
  - pattern: "dd if=*"
    description: "Low-level disk operations"
```

4.3. Add tamper-proof hashing
- Compute SHA256 of approval config on load
- Store hash in separate file
- Verify hash before each command execution
- Lock down if hash mismatch detected

4.4. Integrate with agent loop
- Replace simple `auto_approve` flag with `CommandFirewall.check_command()`
- Show user-friendly approval prompts with command details
- Log all approvals/denials for audit trail

4.5. Add tests
- Test allowlist matching (exact and wildcard)
- Test denylist blocking
- Test tamper detection
- Test policy modes (deny/ask/allowlist)

**Acceptance Criteria**:
- ✅ Granular pattern-based approvals work
- ✅ Tamper detection prevents unauthorized changes
- ✅ Clear audit trail of all command executions
- ✅ User-friendly approval prompts

---

### Task 5: Security Audit Completion
**Priority**: 🟠 High
**Estimated Complexity**: Medium
**Files to Modify**:
- `kabot/utils/security_audit.py` (modify)
- `tests/utils/test_security_audit.py` (modify)

**Implementation Steps**:

5.1. Add network binding checks
```python
def check_network_security(config: Dict[str, Any]) -> List[SecurityFinding]:
    """Check if services bind to public interfaces without auth."""
    findings = []

    # Check if API server binds to 0.0.0.0
    if config.get("api", {}).get("host") == "0.0.0.0":
        if not config.get("api", {}).get("auth_enabled"):
            findings.append(SecurityFinding(
                severity="HIGH",
                category="network",
                message="API server exposed to public without authentication",
                remediation="Set api.host to '127.0.0.1' or enable auth"
            ))

    return findings
```

5.2. Add redaction policy checks
```python
def check_redaction_policy(config: Dict[str, Any]) -> List[SecurityFinding]:
    """Check if sensitive data redaction is enabled."""
    findings = []

    if config.get("logging", {}).get("redact_sensitive") == False:
        findings.append(SecurityFinding(
            severity="MEDIUM",
            category="privacy",
            message="Sensitive data redaction is disabled",
            remediation="Set logging.redact_sensitive to true"
        ))

    return findings
```

5.3. Enhance secret scanning
- Add more patterns (GitHub tokens, AWS keys, etc.)
- Check environment variables
- Check config files recursively

5.4. Add comprehensive tests
- Test all security check functions
- Test finding severity levels
- Test remediation suggestions

**Acceptance Criteria**:
- ✅ Network security checks implemented
- ✅ Redaction policy validation works
- ✅ Enhanced secret scanning catches more patterns
- ✅ 85%+ test coverage

---

## Testing Strategy

### Unit Tests
- Each new module has dedicated test file
- Minimum 85% code coverage
- Mock external dependencies (filesystem, processes)

### Integration Tests
- Test PID locking with actual file operations
- Test crash recovery with simulated crashes
- Test command firewall with real command execution

### Platform-Specific Tests
- Windows ACL tests run only on Windows
- Unix permission tests run only on Linux/Mac
- Cross-platform tests run on all platforms

### Security Tests
- Penetration testing for command firewall bypass attempts
- Tamper detection validation
- Race condition stress tests for PID locking

---

## Rollout Plan

### Phase 13.1: Foundation (Week 1)
- Task 1: PID Locking System
- Task 2: Crash Recovery Sentinel

### Phase 13.2: Security Hardening (Week 2)
- Task 3: Windows ACL Security
- Task 4: Granular Command Approvals

### Phase 13.3: Completion (Week 3)
- Task 5: Security Audit Completion
- Integration testing
- Documentation updates

---

## Success Metrics

### Quantitative
- Resilience parity: 60% → 90%
- Security parity: 45% → 80%
- Overall parity: 65% → 85%
- Test coverage: 85%+
- Zero race conditions in stress tests

### Qualitative
- No config corruption under power failure simulation
- Seamless recovery UX after crashes
- Clear security audit findings with actionable remediation
- User confidence in command execution safety

---

## Risk Mitigation

### Risk 1: PID Locking Complexity on Windows
**Mitigation**: Use `psutil` library for cross-platform process checking

### Risk 2: Windows ACL Parsing Fragility
**Mitigation**: Extensive testing on Windows 10/11, fallback to basic checks if icacls fails

### Risk 3: Command Firewall Bypass
**Mitigation**: Whitelist approach (deny by default), comprehensive pattern testing

### Risk 4: Performance Impact of Locking
**Mitigation**: Lock only critical sections, use timeouts, benchmark before/after

---

## Dependencies

### External Libraries
- `psutil` - Cross-platform process utilities (for PID checking)
- `pyyaml` - YAML parsing (for command approval config)

### Internal Dependencies
- Phase 12 must be complete (Directives, ToolResultTruncator)
- Config system must support schema validation
- Logging system must be functional

---

## Documentation Updates

### User-Facing
- `docs/security/command-approvals.md` - How to configure command firewall
- `docs/security/windows-security.md` - Windows-specific security best practices
- `docs/troubleshooting/crash-recovery.md` - What happens after a crash

### Developer-Facing
- `docs/architecture/pid-locking.md` - PID locking implementation details
- `docs/architecture/sentinel-system.md` - Crash recovery architecture
- `docs/contributing/security-testing.md` - How to test security features

---

## Post-Phase 13 Roadmap

### Phase 14: Interface & Experience (TUI, Canvas, TTS)
- Terminal User Interface with real-time streaming
- Canvas host for web UI rendering
- Multi-provider TTS integration

### Phase 15: Infrastructure (Tailscale, Bonjour, Advanced Cron)
- Native Tailscale integration
- Zero-config discovery with mDNS
- Advanced cron scheduling (everyMs, atMs)

### Phase 16: Advanced Features (Pi Agent, Browser Relay, Plugin SDK)
- Embedded mini-agent for speed
- Chrome extension relay
- Universal plugin SDK

---

## Conclusion

Phase 13 transforms kabot from a smart but fragile system into a production-ready, secure agent. By implementing PID locking, crash recovery, Windows ACL checks, granular command approvals, and completing the security audit, we achieve 85% OpenClaw parity and establish a solid foundation for advanced features in Phase 14+.

**Key Deliverables**:
1. ✅ Zero race conditions (PID Locking)
2. ✅ Seamless crash recovery (Sentinel)
3. ✅ Windows security parity (ACL checks)
4. ✅ Production-grade command safety (Firewall)
5. ✅ Comprehensive security auditing

**Next Steps**: Begin implementation with Task 1 (PID Locking System).
