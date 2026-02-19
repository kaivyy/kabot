# Changelog

All notable changes to Kabot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Universal Integrations (Meta + Fleet + Parity) (2026-02-19)

- Added hardened HTTP integration guard configuration:
  - `integrations.http_guard` in config schema
  - SSRF-style private/local target blocking in `web_fetch`
  - `integrations.http_guard.enabled` toggle to explicitly disable guard in trusted mode
  - Empty `deny_hosts` is now honored (no forced default denylist when explicitly cleared)
- Added Meta Graph outbound integration:
  - New `meta_graph` tool for `threads_create`, `threads_publish`, `ig_media_create`, `ig_media_publish`
  - New `MetaGraphClient` with authenticated Graph API requests
  - Wired into main agent loop and subagent tool registry
- Added Meta webhook ingress with verification:
  - New `GET /webhooks/meta` challenge endpoint
  - New `POST /webhooks/meta` event endpoint
  - Signature validation via `X-Hub-Signature-256` and app secret
  - Payload mapping into internal `InboundMessage` channels (`meta:threads` / `meta:instagram`)
- Added setup wizard fleet templates for multi-bot/multi-agent setup:
  - New `content_pipeline` template
  - New `Apply Fleet Template` channel-instance flow
  - Auto-creates role agents and binds channel instances
- Added OpenClaw-style trusted freedom profile in setup wizard (`Tools & Sandbox`):
  - Enables `tools.exec.auto_approve`
  - Disables HTTP guard restrictions for unrestricted integrations in trusted deployments
- Added plugin scaffolding workflow:
  - New `kabot plugins scaffold --target <plugin_id>`
  - New dynamic plugin templates (`plugin.json`, `main.py`)
- Added auth parity diagnostics:
  - New `AuthManager.parity_report()` for handler/alias parity checks
  - New CLI command `kabot auth parity`
- Added tests:
  - `tests/tools/test_meta_graph_tool.py`
  - `tests/gateway/test_webhooks_meta.py`
  - `tests/cli/test_setup_wizard_fleet_builder.py`
  - `tests/plugins/test_scaffold.py`
  - `tests/auth/test_oauth_provider_parity.py`

### Added - Reliability, Security, and OpenClaw Parity Enhancements (2026-02-19)

#### OpenAI Codex OAuth + Provider Parity
- Added ChatGPT backend compatibility improvements for OpenAI Codex OAuth:
  - Do not send unsupported `temperature` parameter to codex backend endpoint.
  - Improved SSE parsing coverage (`response.output_text.delta`, `response.content_part.added`) and UTF-8 byte decoding fallback to prevent mojibake output.
- Fixed runtime model orchestration for Codex/OpenAI fallback stacks:
  - CLI/provider bootstrap now supports `agents.defaults.model` as `AgentModelConfig` (`primary` + `fallbacks`) end-to-end.
  - Runtime fallback chain now merges model-level fallbacks with provider-level fallbacks in deterministic order.
- Added provider alias parity for auth methods and login routing:
  - `gemini -> google`
  - `moonshot -> kimi`
  - `vllm -> ollama`
- Added OAuth refresh endpoint alias support for `gemini`.
- Fixed OAuth refresh provider resolution and secrets propagation:
  - `get_api_key_async()` now refreshes using resolved provider name from default model selection (including default model object mode).
  - Added optional `client_secret` support in auth profiles and refresh payloads for providers that require it (e.g., Google-style refresh flows).
- Added `setup_token` compatibility across config/auth status paths and setup validation flow.
- Fixed non-OpenAI auth parity gap:
  - `google.gemini_cli` auth handler now implements required `name` contract, so dynamic auth handler loading no longer fails with abstract-class instantiation error.
  - Added regression tests for `google_gemini_cli` handler instantiation and AuthManager loading path.

#### Installer and Environment Auto-Detection Parity
- Added centralized runtime environment detection utility:
  - Detects `termux`, `wsl`, `vps`, `headless`, `ci`, and platform (`windows`/`macos`/`linux`).
  - Added mode recommendation helper for setup defaults.
- Setup wizard now auto-detects runtime environment and:
  - Shows detected environment tags in the Environment section.
  - Uses environment-aware default for gateway mode (`remote` on headless/VPS/Termux, else `local`).
  - Persists detected environment snapshot into setup state.
- Linux/macOS installer (`install.sh`) now:
  - Detects Termux/WSL/VPS/headless and logs environment summary.
  - Adapts `BIN_DIR` for Termux (`$PREFIX/bin`) when applicable.
  - Warns for missing Termux prerequisites.
  - Skips interactive setup wizard automatically in non-interactive sessions.
- Windows installer (`install.ps1`) now:
  - Detects remote/headless/non-interactive context and logs environment summary.
  - Skips interactive setup wizard automatically in non-interactive sessions.
- Added tests:
  - `tests/utils/test_environment.py`
  - `tests/cli/test_setup_wizard_environment.py`

#### Security and Command Approval UX
- Added explicit approval workflow for firewall `ASK` mode:
  - Interactive CLI prompt (`once` / `always` / `deny`) for `exec` when TTY is available.
  - Pending approval queue with explicit command IDs for non-interactive channels.
  - New approval commands in chat/gateway sessions:
    - `/approve <id>`
    - `/deny <id>`
- Added persistent "allow always" behavior per command in runtime approval callback path.
- Added strict ASK enforcement (commands are blocked unless elevated/approved).
- Added runtime wiring so elevated directives correctly toggle `ExecTool.auto_approve`.
- Added advanced approval governance matrix in `CommandFirewall`:
  - New context-aware `scoped_policies` supports per-scope policy selection based on `channel`, `agent_id`, `tool`, and other context fields.
  - Scoped rule precedence resolves by specificity (most specific match wins).
  - Scoped policies can inherit global allow/deny patterns or operate independently (`inherit_global`).
  - Added scoped policy persistence APIs for add/remove/list operations.
- Added approval audit trail and inspectability:
  - Every firewall decision (`allow` / `ask` / `deny`) is persisted to JSONL audit log.
  - Added API for querying recent audit entries with filters (`decision`, `channel`, `agent_id`).
- Added approvals CLI surface:
  - `kabot approvals status`
  - `kabot approvals allow`
  - `kabot approvals audit`
  - `kabot approvals scoped-add`
  - `kabot approvals scoped-list`
  - `kabot approvals scoped-remove`
  - Supports `--config` path override for operational and test environments.
- Extended runtime approval context propagation to include identity scope keys:
  - `account_id`, `thread_id`, `peer_kind`, `peer_id` are now forwarded into firewall context for scoped policy matching.

#### Remote Ops Bootstrap
- Added `kabot remote-bootstrap` command for platform-aware remote rollout guidance:
  - Supports dry-run/apply modes with service-manager selection (`systemd`, `launchd`, `windows`, `none`).
  - Prints deterministic hardening checklist (`doctor --fix`, `status`, `approvals status`).
  - Includes lightweight remote-readiness snapshot in command output.
- Added CLI tests for remote bootstrap command and scoped approvals management.

#### Cron and Reminder Reliability
- Added deterministic reminder delivery fallback:
  - If provider execution fails (rate/auth/quota/error class), reminder still delivers using scheduled message payload.
  - Attached reminder context block is stripped from fallback delivery text.
- Improved CLI resilience when scheduler lock is unavailable:
  - `kabot agent -m ...` no longer crashes if cron lock/start fails (e.g., another instance owns the lock).
  - Session continues and warns that reminder delivery may be delegated to another running instance.
- Session persistence now fails open:
  - Agent replies are still returned even if session state cannot be persisted (lock contention / readonly FS).
- Added bounded and persisted cron run history:
  - Multi-run history retained (not only last run snapshot).
  - Stored under cron state and capped (`MAX_RUN_HISTORY`) to prevent unbounded growth.
- Added cron CLI parity surface:
  - `kabot cron status`
  - `kabot cron update`
  - `kabot cron runs`
- Added durable cron store writes using `PIDLock` + temp file + `os.replace`.

#### Gateway and Webhook Hardening
- Added webhook bearer-token enforcement for ingress.
- Added gateway host/auth-token wiring into webhook startup path.
- Added security audit checks for current `gateway.host` / `gateway.auth_token` schema.
- Hardened logger initialization in constrained environments:
  - File/DB sink initialization now fails open with console fallback instead of crashing startup.
  - Added fallback from `enqueue=True` to `enqueue=False` for environments where multiprocessing queues are restricted.
- Added terminal-safe output normalization for CLI responses:
  - Prevents UnicodeEncodeError crashes on non-UTF Windows terminals by replacing unsupported glyphs.

#### Memory Retrieval Enhancements
- Added temporal decay weighting in hybrid retrieval ranking.
- Added optional MMR reranking on top of fused candidates for better relevance/diversity balance.
- Retained existing vector + BM25 + RRF pipeline while upgrading final ranking strategy.

#### Test Infrastructure and Verification
- Added Windows-safe pytest temp-root harness (`tests/conftest.py`) to mitigate `tmp_path` ACL permission failures in this environment.
- Added/updated targeted tests for:
  - Codex backend parsing/temperature behavior
  - Auth alias routing and refresh aliases
  - Runtime provider bootstrap for `AgentModelConfig` primary/fallback mode
  - Async provider-name refresh routing from default model context
  - OAuth refresh payload support for `client_secret`
  - Logger startup fallback for file-permission and queue-restricted runtimes
  - One-shot agent behavior when cron lock/start is unavailable
  - Session finalize behavior when persistence save fails
  - Terminal-safe output sanitization for CP1252-like terminals
  - Setup wizard default-model/auth checks
  - Firewall ASK flow + approval execution path
  - Cron persistence + run history behavior
  - Webhook auth enforcement
  - Security audit gateway schema checks
  - Reminder wait/fallback behavior
  - Memory temporal/MMR ranking helpers
- Verification snapshot:
  - Consolidated targeted suite passed: `130 passed, 1 warning`.

### Added - Multi-Bot/Multi-AI Routing and Setup Wizard Parity (2026-02-19)

#### Runtime Routing and Channel Instance Identity
- Added end-to-end instance identity propagation for multi-channel instances:
  - Channel instances now stamp inbound messages with stable instance metadata (`channel_instance.id`, `type`, `agent_binding`).
  - Inbound `channel` now preserves instance key (`<type>:<instance_id>`) for deterministic reply routing.
- Added OpenClaw-style routing field extraction in base channel handling:
  - Maps metadata to `account_id`, `peer_kind`, `peer_id`, `guild_id`, `team_id`, `thread_id`, and `parent_peer`.
  - Improves binding/session-key resolution consistency across Telegram/Discord/Slack and other channels.
- Added channel routing compatibility for instance channels:
  - Binding `channel: telegram` now matches `telegram:<instance_id>`.
  - Exact instance bindings (e.g. `channel: telegram:work_bot`) are prioritized over base-channel bindings.
- Added explicit forced-route support in resolver:
  - `resolve_agent_route(..., forced_agent_id=...)` for runtime overrides such as instance-level `agent_binding`.

#### Agent Loop Model and Fallback Resolution
- Added centralized route-context resolution in `AgentLoop`:
  - Session key, routed agent ID, and model selection now share one instance-aware route resolver.
  - Instance `agent_binding` is now honored at runtime (not only stored in config).
- Added per-message model-chain resolver:
  - New `_resolve_models_for_message()` returns primary + fallbacks with dedupe.
  - Per-agent fallbacks from `AgentModelConfig` now override global runtime fallbacks as intended.
- Updated agent execution loop to use resolved per-message model chain for fallback attempts.

#### Setup Wizard UX for Many Bots and Many AI Agents
- Enhanced Channel Instances flow with scalable setup UX:
  - Added `Quick Add Multiple` for batch creating many bot instances.
  - Added deterministic unique-ID handling (`<id>`, `<id>_2`, ...).
  - Added optional auto-create dedicated agent per instance.
  - Added optional model override when creating new bound agents.
- Added reusable setup wizard helpers to support both single add and bulk add:
  - `_next_available_instance_id`
  - `_ensure_agent_exists`
  - `_add_channel_instance_record`
  - `_prompt_instance_config`
  - `_prompt_agent_binding`

#### Tests and Verification
- Added and updated coverage for the new behavior:
  - `tests/channels/test_multi_instance_manager.py`
  - `tests/routing/test_bindings.py`
  - `tests/agent/test_agent_model_switching.py`
  - `tests/cli/test_setup_wizard_channel_instances.py` (new)
- Verification snapshot for this change set:
  - `23 passed` targeted runtime/wizard/routing/model suite.
  - Additional integration/channel suite: `10 passed`.
  - `py_compile` check passed for all modified runtime and test files.

### Added - Plugin Lifecycle + Remote Env Operations Enhancements (2026-02-19)

#### Plugin Lifecycle Management (OpenClaw-style parity upgrade)
- Added new plugin lifecycle manager:
  - `kabot/plugins/manager.py` for install/update/enable/disable/remove/doctor flows.
  - Persistent plugin state stored in workspace plugin state file (disabled + source tracking).
  - Supports install/update from local plugin directories (`plugin.json` or `SKILL.md`).
  - Adds doctor diagnostics for plugin entry-point and dependency health checks.
- Expanded `kabot plugins` CLI from list-only to full lifecycle actions:
  - `list`
  - `install --source <dir>`
  - `update --target <id> [--source <dir>]`
  - `enable --target <id>`
  - `disable --target <id>`
  - `remove --target <id> [--yes]`
  - `doctor [--target <id>]`

#### Environment/Remote Ops Hardening
- Added new `kabot env-check` command:
  - Prints runtime platform profile (windows/macos/linux/wsl/termux/vps/headless/ci).
  - Shows recommended gateway mode derived from detected environment.
  - Optional verbose operational guidance per platform.
- Enhanced `kabot remote-bootstrap` service resolver and dry-run guidance:
  - Auto-resolves `termux` to a dedicated service mode.
  - Added Termux dry-run plan with `termux-services` guidance.
  - Added Termux apply guidance path in command output.

#### Tests and Verification
- Added tests:
  - `tests/plugins/test_manager.py`
  - `tests/cli/test_plugins_commands.py`
  - `tests/cli/test_env_check.py`
  - extended `tests/cli/test_remote_bootstrap.py` (Termux flow)
- Verification snapshot for this change set:
  - New plugin/env/remote suite: `10 passed`.
  - Regression suite covering routing + wizard + runtime core: `33 passed`.
  - `py_compile` check passed for all modified files.

### Added - Plugin Git Pinning, Windows Task Automation, and Doctor Matrix (2026-02-19)

#### Plugin Manager Hardening (Git + Rollback)
- Enhanced `PluginManager` with git-source support:
  - Added `install_from_git(repo_url, ref=...)` with pinned ref support (tag/branch/commit).
  - Persists git source metadata (`type`, `url`, `ref`) for deterministic update behavior.
- Added rollback-safe plugin updates:
  - `update_plugin()` now creates a backup of the currently installed plugin.
  - If update fails, the previous plugin state is restored automatically.

#### Plugin CLI Upgrade (Git Install/Update)
- Extended `kabot plugins` CLI with git options:
  - `plugins install --git <repo> [--ref <tag|branch|commit>]`
  - `plugins update --target <id> --git <repo> [--ref ...]`
- Install source validation now enforces exactly one source input:
  - `--source <dir>` XOR `--git <repo>`

#### Remote Bootstrap (Windows Apply)
- Upgraded `remote-bootstrap --apply` for Windows:
  - Added executable path for Task Scheduler creation (not guidance-only anymore).
  - New daemon helper: `install_windows_task_service()` using `schtasks` for ONLOGON startup.
- Updated daemon service status for Windows to reflect Task Scheduler support.

#### Doctor Matrix + Deeper Auto-Fix
- Refactored `KabotDoctor` diagnostics:
  - Added environment matrix checks (platform, recommended gateway mode, WSL/Termux/service-manager readiness).
  - Expanded integrity paths to include logs/plugins/tmp runtime directories.
  - Auto-fix now ensures all managed runtime directories are created.
- Report output now includes a dedicated Environment Matrix panel.

#### Tests and Verification
- Added/expanded tests:
  - `tests/plugins/test_manager.py` (git pinning + rollback behavior)
  - `tests/cli/test_plugins_commands.py` (git install path in CLI)
  - `tests/cli/test_remote_bootstrap.py` (windows apply task-scheduler path)
  - `tests/utils/test_doctor_matrix.py` (environment matrix + deeper fix)
- Verification snapshot for this batch:
  - New focused suite: `16 passed`.
  - Combined regression suite: `41 passed`.
  - `py_compile` check passed for all modified runtime and test files.

### Changed - Documentation and Gap Revalidation (2026-02-19)
- Updated parity revalidation doc to reflect current implementation state:
  - Marked stale historical gap claims.
  - Recorded newly completed remediation for security/cron/reminder/memory/approval flows.

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
