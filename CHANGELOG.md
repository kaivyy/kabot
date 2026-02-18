# Changelog

All notable changes to Kabot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed - Setup Wizard Critical Issues and Missing Features (2026-02-18)

**Comprehensive setup wizard overhaul addressing 10+ critical issues discovered during completeness audit.**

#### Critical Fixes (Phase 1)
- **Removed duplicate method definition** (`kabot/setup/wizard.py`)
  - Eliminated duplicate `_configure_skills` method causing import conflicts
- **Fixed Windows service installer** (`kabot/setup/installers/windows.py`)
  - Corrected PowerShell variable syntax from `${{variable}}` to `${variable}`
  - Fixed service registration and startup configuration
- **Implemented Linux systemd service installer** (`kabot/setup/installers/linux.py`)
  - Added complete systemd service file generation and installation
  - Proper user/system service handling with appropriate permissions
- **Added API key validation framework** (`kabot/setup/wizard.py`)
  - Integrated validation for OpenAI, Anthropic, and other LLM providers
  - Real-time validation during setup process with clear error messages

#### Core Features (Phase 2)
- **Created comprehensive uninstaller scripts**
  - Windows PowerShell uninstaller (`kabot/setup/uninstallers/windows.py`)
  - Linux/Mac shell uninstaller (`kabot/setup/uninstallers/unix.py`)
  - Service removal, file cleanup, and configuration backup
- **Implemented configuration backup system** (`kabot/setup/backup.py`)
  - Versioned backup storage with automatic rollback capability
  - Backup creation before major configuration changes
- **Added setup state persistence** (`kabot/setup/state.py`)
  - JSON-based state tracking for setup process resumption
  - Recovery from interrupted installations
- **Fixed built-in skills installation integration**
  - Proper integration with existing skills system
  - Resolved circular import issues and dependency conflicts

#### Test Infrastructure Updates
- **Updated AgentBinding schema** across all test files
  - Migrated from legacy format to new `match` field structure
  - Updated imports to include `AgentBindingMatch` and `PeerMatch`
- **Fixed agent routing logic** (`kabot/agent/loop.py:_resolve_model_for_message`)
  - Corrected peer resolution for proper model selection
  - Fixed session key handling in background sessions
- **Resolved mock setup issues** in autoplanner integration tests
  - Added missing `_agent_subscribers` attribute to mock MessageBus

### Impact
- **Before**: Setup wizard had 10+ critical issues including broken service installers, missing uninstall capability, no configuration backup, and test failures
- **After**: Complete, production-ready setup wizard with full lifecycle management and robust test coverage
- **Test Results**: All 507 tests passing (fixed 17 failing tests)

### References
- Design document: `docs/plans/2026-02-18-setup-wizard-fixes-design.md`
- Implementation plan: `docs/plans/2026-02-18-setup-wizard-fixes-implementation.md`
- Commit: `a540af5` - fix: complete setup wizard fixes and test infrastructure updates

---

### Added - Phase 14: Event Bus Expansion (2026-02-17)

**OpenClaw Parity: 85% → 100% (COMPLETE)**

This phase expands the message bus from chat-only to full system event support, enabling real-time monitoring of agent internals.

#### System Event Architecture
- **Expanded SystemEvent class** (`kabot/bus/events.py`)
- Added factory methods for lifecycle, tool, assistant, and error events
- Monotonic sequencing per run_id for event ordering
- Pattern from OpenClaw: src/infra/agent-events.ts

#### Event Bus Infrastructure
- **Enhanced MessageBus** (`kabot/bus/queue.py`)
- Added system_events queue for event distribution
- Added get_next_seq() for monotonic sequence generation
- Added emit_system_event() and subscribe_system_events() methods
- Added dispatch_system_events() background task

#### Agent Loop Integration
- **Integrated lifecycle events** (`kabot/agent/loop.py`)
- Emit lifecycle start event on agent startup
- Emit lifecycle stop event on clean shutdown
- Emit error events for processing failures
- Pass bus parameter to ToolRegistry

#### Tool Execution Monitoring
- **Enhanced ToolRegistry** (`kabot/agent/tools/registry.py`)
- Accept bus and run_id parameters for event emission
- Emit tool start events before execution
- Emit tool complete events with result length
- Emit tool error events on validation/execution failures

### Impact
- **Before**: Event bus only supported chat messages (85% parity)
- **After**: Full system event support with real-time monitoring (100% parity)
- **Achievement**: 100% OpenClaw parity reached

### References
- Pattern source: OpenClaw src/infra/agent-events.ts
- Commit: `25bde71` - feat(phase-14): expand event bus to full system events

---

### Fixed - Phase 13 Completion: Critical Gap Integration (2026-02-17)

**OpenClaw Parity: 65% → 85% (ACTUALLY ACHIEVED)**

After deep verification analysis, discovered that Phase 13 initial implementation (2026-02-16) created the infrastructure but did NOT integrate it into the system. This update completes the integration:

#### Session File Protection (CRITICAL FIX)
- **Applied PIDLock to session files** (`kabot/session/manager.py:138-169`)
- Added atomic write pattern (temp file + rename) to prevent corruption
- Eliminates race condition risk when multiple processes access sessions
- Pattern: Same as `config/loader.py` but was missing from session manager

#### Crash Recovery Integration (CRITICAL FIX)
- **Integrated CrashSentinel into agent loop** (`kabot/agent/loop.py`)
- Added crash detection on startup (lines 361-375)
- Mark session active before processing messages (lines 480-486)
- Clear sentinel on clean shutdown (lines 402-403)
- Recovery messages now sent to users after unexpected restarts
- Note: `core/sentinel.py` existed but was completely unused

#### Persistent Subagent Registry (NEW FEATURE)
- **Created SubagentRegistry class** (`kabot/agent/subagent_registry.py` - 229 lines)
- Persistent tracking of subagent tasks across process restarts
- Integrated into SubagentManager (`kabot/agent/subagent.py`)
- Updated SpawnTool to pass parent session key (`kabot/agent/tools/spawn.py`)
- Subagents now survive crashes and can be queried/resumed
- Registry stored at `~/.kabot/subagents/runs.json` with PIDLock protection

#### Additional Changes
- Added `elevated` directive to `kabot/core/directives.py` for high-risk tool usage

### Impact
- **Before**: Phase 13 was 60% complete (infrastructure created but not integrated)
- **After**: Phase 13 is 100% complete (all critical gaps closed)
- **Verification**: Ultimate verification document confirmed all gaps are now fixed

### References
- Ultimate verification: `docs/openclaw-analysis/ultimate-verification-gap-kabot-openclaw.md`
- Commit: `2a5e276` - feat(phase-13): complete OpenClaw parity

---

### Added - Phase 13: Resilience & Security Infrastructure (2026-02-16)

**Initial Implementation (Partial - 60% Complete)**

#### Task 1: PID Locking System
- Added `kabot/utils/pid_lock.py` with file-based process locking
- Stale lock recovery using psutil for cross-platform process checking
- Atomic lock file creation with O_CREAT | O_EXCL flags
- Integrated PIDLock into config loader replacing basic file_lock
- 19 comprehensive tests covering concurrency, edge cases, and cross-platform compatibility

#### Task 2: Crash Recovery Sentinel
- Added `kabot/core/sentinel.py` for unclean shutdown detection
- Black box recorder writes sentinel before message processing
- Atomic writes with temp file pattern to prevent corruption
- Recovery message formatting with session context
- 23 comprehensive tests covering crash detection and recovery workflows

#### Task 3: Windows ACL Security
- Added `kabot/utils/windows_acl.py` for Windows permission checks
- Uses `icacls` to parse Windows ACL permissions
- Detects world-writable directories and world-readable sensitive files
- Checks if running as Administrator
- Provides remediation commands for insecure permissions
- Integrated into `kabot/utils/security_audit.py`
- 23 comprehensive tests (Windows-specific with platform detection)

#### Task 4: Granular Command Approvals
- Added `kabot/security/command_firewall.py` with pattern-based approval system
- Three policy modes: deny, ask, allowlist
- Wildcard pattern matching with proper regex escaping
- Tamper-proof configuration with SHA256 hash verification
- Default safe commands (git status, ls, pwd) and dangerous denylists (rm -rf, dd, fork bomb)
- Integrated into `kabot/agent/tools/shell.py` (ExecTool)
- Added missing `_is_high_risk()` method for high-risk command detection
- Audit logging for all command executions
- 45 comprehensive tests (32 firewall + 13 integration tests)

#### Task 5: Security Audit Completion
- Enhanced secret scanning patterns:
  - GitHub tokens (ghp_, gho_, ghu_, ghs_)
  - AWS Access Keys (AKIA...)
  - AWS Secret Keys
  - Slack tokens (xox...)
  - Stripe API keys (sk_live_...)
  - Private keys (RSA, EC, OPENSSH)
- Environment variable secret scanning
- Network security checks:
  - Public API binding without authentication (0.0.0.0, ::, *)
  - WebSocket security validation
- Redaction policy validation:
  - PII logging detection
  - Sensitive data redaction checks
  - Telemetry user data tracking
- 23 comprehensive tests covering all new security features

### Changed
- `kabot/config/loader.py`: Replaced basic file_lock with PIDLock for better concurrency control
- `kabot/agent/tools/shell.py`: Integrated CommandFirewall, added high-risk command detection
- `kabot/utils/security_audit.py`: Enhanced with network/redaction checks, environment scanning

### Technical Details
- Total new code: 3,474 insertions, 97 deletions
- Total new tests: 133 tests passing
- New modules: 4 (sentinel, command_firewall, pid_lock, windows_acl)
- Test coverage: 85%+ for all new modules
- Cross-platform: Windows/Linux/macOS support with platform-specific implementations

### References
- Implementation plan: `docs/plans/2026-02-16-openclaw-parity-phase-13.md`
- Gap analysis: `docs/openclaw-analysis/kabot-gap-analysis.md`
- Technical findings: `docs/openclaw-analysis/deep-technical-findings.md`

---

## Previous Releases

### Phase 12 and Earlier
See git history for previous changes.
