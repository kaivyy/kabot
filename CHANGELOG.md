# Changelog

All notable changes to Kabot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Military-Grade Progressive Enhancement & Security Hardening (2026-02-21)

- **Multi-Provider Deep Search:** 
  - Rewrote `WebSearchTool` to support multi-provider chain (Perplexity Sonar, Grok-3, Brave).
  - Implemented automatic fallback: if premium provider fails, it attempts to use Brave Search.
  - Added in-memory thread-safe `TTLCache` to reduce API costs and improve performance.
- **Enhanced Web Fetching & Security:**
  - Added **SSRF Guard** to `WebFetchTool` with host denylists and DNS resolution checks.
  - Implemented **FireCrawl fallback** for JavaScript-heavy websites when BeautifulSoup fails.
  - Added **External Content Wrapping** (`[EXTERNAL_CONTENT]`) to mitigate prompt injection risks from untrusted data.
- **Improved Skills UX:**
  - Enhanced skills validation to check for missing binaries and environment variables.
  - Added explicit installation hints for missing dependencies (e.g., "needs ffmpeg (install: sudo apt install ffmpeg)").
  - Fixed YAML frontmatter parsing in `SkillsLoader` to support multiline JSON metadata blocks.
- **Setup Wizard "Military-Grade" Section:**
  - Added "Advanced Tools" section to `kabot setup` for optional Perplexity, Grok, and FireCrawl keys.
  - Integrated "Freedom Mode" toggle to disable HTTP guards and auto-approve commands for trusted environments.
- **Fixed:**
  - Resolved `TypeError` in `WebFetchTool` initialization that crashed the gateway process.
  - Fixed `[WinError 2]` during WhatsApp bridge setup on Windows by resolving `npm.cmd` absolute path.
  - Fixed logic bug where `kabot setup` failed to prompt for API keys of complex skills (Nano Banana, etc.).
  - Fixed `AttributeError` exception when running `kabot doctor` Health Check from setup wizard by adding `check_requirements` to the tool base class.

### Fixed - Setup Wizard OpenClaw Config Flow (2026-02-21)

- Fixed Discord advanced channel configuration in setup wizard:
  - Prevented crash when opening `Intents` prompt from advanced Discord settings.
  - Intents input now supports both bitmask form (`37377`) and comma-separated flags (`32768,512`) and stores a valid integer bitmask.
- Fixed skills dependency selection logic:
  - Selecting `Skip for now` together with specific selected skills no longer cancels all installs.
  - Wizard now installs selected skills and only ignores the `skip` marker itself.
- Improved skills API-key behavior in setup wizard:
  - Wizard now injects preconfigured `config.skills.*.env` values into process environment before evaluating missing skill env requirements.
  - Prevents unnecessary repeated API-key prompts for skills already configured in config.
- Hardened gateway setup prompt:
  - Invalid/non-numeric gateway port input no longer crashes wizard flow.
  - Wizard keeps the previous valid port and continues.
- Added regression tests:
  - `tests/cli/test_setup_wizard_channel_instances.py` (Discord intents parsing path).
  - `tests/cli/test_setup_wizard_skills.py` (skip+install behavior and preconfigured env usage).
  - `tests/cli/test_setup_wizard_gateway.py` (invalid gateway port handling).

### Fixed - Tool-Calling Reliability for Weather/Reminder (2026-02-20)

- Fixed OpenAI Codex OAuth backend request/response handling so tool calls can run end-to-end:
  - Codex backend payload now forwards `tools` definitions (responses-style function tools).
  - SSE parser now extracts function calls (`function_call`) in addition to text deltas.
  - JSON payload fallback parser now also extracts function calls.
  - Codex backend responses are now mapped into `LLMResponse.tool_calls` (not text-only).
- Improved Codex history payload shaping for tool loops by preserving message fields used by tool flow:
  - `tool_calls`, `tool_call_id`, `name`, `function_call` (when present).
  - Added responses-style conversion for tool loop continuity:
    - Assistant tool calls are sent as `type=function_call` items.
    - Tool results are sent as `type=function_call_output` with matching `call_id`.
- Improved intent routing for real-time utility prompts so they avoid simple/no-tool path:
  - Added explicit complex triggers for weather terms (`weather`, `cuaca`, `suhu`, etc.).
  - Added explicit complex triggers for reminder phrasing (`set sekarang`, `pengingat`, `timer`, etc.).
- Added tool-enforcement fallback path in `AgentLoop` for weather/reminder queries:
  - If model replies text-only for a query that requires tools, Kabot forces one retry with strict tool-call instruction.
  - If model still refuses tool-calling, Kabot executes deterministic fallback:
    - `weather` fallback extracts location and runs weather tool directly.
    - `cron` fallback parses relative time and schedules reminder via cron tool.
    - `cron` fallback now also supports recurring natural language schedules:
      - interval patterns (`tiap 4 jam`, `every 30 minutes`)
      - daily patterns (`setiap hari jam 09:00`, `every day at 9`)
      - weekly patterns (`setiap senin jam 08:00`, `every monday at 8`)
      - complex cycle patterns (`selama X hari` + `libur Y hari` blocks) for shift-like repeating routines and other multi-phase reminders.
- Added cycle-anchored recurring support in cron core/tooling:
  - New `start_at` support in `cron` tool (`every_seconds` + anchor) for deterministic phase-aligned long cycles.
  - Persisted schedule anchor (`startAtMs`) in cron store and restored on reload.
  - `every` next-run computation now supports anchor-based recurrence (`start_at_ms`) for stable repeating cadence.
- Added grouped schedule management for better multi-reminder UX:
  - New cron payload metadata: `group_id`, `group_title`.
  - New cron tool actions:
    - `list_groups`
    - `remove_group` (delete all jobs in one schedule group)
    - `update_group` (rename/reschedule all jobs in one schedule group)
  - `list` and `list_reminders` now expose group title/id so users can manage schedules by title/group.
- Added deterministic cron-management fallback in `AgentLoop` when model skips tool calls:
  - Supports `list` schedule groups from natural language queries.
  - Supports `remove` schedule by `group_id`, title, or job id hints.
  - Supports `update/rename` schedule groups by `group_id`/title with recurring schedule updates.
- Refactored large reminder fallback logic into dedicated modules for maintainability:
  - New `kabot/agent/cron_fallback_nlp.py` for reminder/cron intent parsing and cycle extraction.
  - New `kabot/agent/fallback_i18n.py` for language-aware fallback messaging.
  - `AgentLoop` now delegates parser and message rendering to these modules, reducing in-file complexity.
- Continued structural refactor to reduce large-file risk and prepare folder-based maintenance:
  - New package `kabot/agent/loop_core/`:
    - `tool_enforcement.py` for required-tool detection + deterministic fallback execution.
    - `session_flow.py` for session key/init/finalize lifecycle logic.
    - `quality_runtime.py` for planning/self-eval/critic/lesson runtime logic.
    - `execution_runtime.py` for complex loop execution, fallback model call, and tool-call handling.
    - `directives_runtime.py` for think/verbose/elevated directive behavior helpers.
  - `kabot/agent/loop.py` now acts as compatibility facade for extracted modules (legacy imports/patch points kept).
  - `AgentLoop` source reduced from 1488 lines to 894 lines while preserving runtime behavior.
  - New package `kabot/agent/tools/cron_ops/`:
    - `actions.py` for cron action handlers (`add/list/list_groups/update/remove/run/status`).
    - `schedule.py` for schedule/group-id parsing helpers.
  - `kabot/agent/tools/cron.py` now delegates to `cron_ops` handlers while preserving existing `CronTool` API.
- Refactored cron delivery callback + fallback pipeline into dedicated module:
  - New `kabot/cron/callbacks.py`:
    - message cleanup/fallback guards (`strip_reminder_context`, `resolve_cron_delivery_content`)
    - lightweight AI rewrite helper (`render_cron_delivery_with_ai`)
    - callback builders for gateway and CLI (`build_bus_cron_callback`, `build_cli_cron_callback`)
  - `kabot/cli/commands.py` now wires `cron.on_job` via callback builders and keeps compatibility wrappers for existing helper imports/tests.
- Folderized cron service internals into `kabot/cron/core/` with stable facade API:
  - New `kabot/cron/core/persistence.py` for store load/save with atomic write and run-history compatibility handling.
  - New `kabot/cron/core/scheduling.py` for next-run computation, due-job selection, and timer arming.
  - New `kabot/cron/core/execution.py` for job execution state/history lifecycle.
  - `kabot/cron/service.py` now delegates internal methods (`_load_store`, `_save_store`, `_recompute_next_runs`, `_get_next_wake_ms`, `_arm_timer`, `_execute_job`) to core modules while preserving public behavior and API.
  - `CronService` source reduced to 237 lines.
- Added input-language-aware fallback responses (no single-language hardcoding in agent fallback path):
  - Detects Indonesian/English/Malay/Thai/Chinese from user input and responds with matching fallback/system guidance language.
  - Added script-aware detection for Thai and Chinese input.
  - Expanded fallback catalog for `ms`, `th`, and `zh`.
- Cycle fallback now auto-assigns unique schedule title + group id:
  - Created cycles return explicit summary (`title`, `group_id`, job count, period days).
  - Supports custom multi-phase patterns beyond fixed 12-day shift (e.g. `3 hari masuk, 1 libur, 2 masuk, 1 libur`).
  - Tool enforcement now auto-disarms after the required tool has been emitted, preventing duplicate reminder scheduling.
  - Critic retry is skipped for turns that already executed tools, preventing post-tool meta/hallucinated self-critique replies.
- Expanded deterministic multilingual trigger/parse coverage:
  - Added reminder/weather/schedule-management keywords for Malay, Thai, and Chinese in `cron_fallback_nlp`.
  - Extended relative-time parsing in `kabot/cron/parse.py` for `minit`, Thai units, and Chinese units (e.g. `分钟后`).
  - Improved weather location extraction for mixed queries (`tanggal + suhu` / `right now`) so city parsing no longer keeps noise tokens like `berapa` or `right`.
- Fixed root weather-tool failure mode for noisy LLM tool arguments:
  - `WeatherTool` now normalizes incoming `location` text before fetch (`suhu di cilacap sekarang` -> `Cilacap`).
  - Weather location normalization now strips trailing city descriptors (`kota`, `city`, `kabupaten`, etc.) to improve geocoding compatibility.
  - For `simple` mode, weather retrieval now prefers Open-Meteo first (structured current weather) and uses wttr as fallback.
  - Added safer request handling (`quote_plus`, explicit User-Agent, redirect handling) and cleaner error diagnostics.
  - Added support for `png` output mode as URL passthrough for wttr.
- Improved weather reply quality to be more human-care oriented and actionable:
  - `WeatherTool` now appends a practical care tip based on parsed temperature + condition (heat/cold/rain/storm/fog), e.g. sunscreen, hydration, jacket, umbrella.
  - Added explicit extreme-heat tier (`>=36°C`) with stronger heatstroke caution and midday outdoor activity guidance.
  - Advice output is language-aware using existing fallback language detection (`id`/`en`/`ms`/`th`/`zh`) to reduce hardcoded single-language behavior.
  - Weather tool-call pipeline now forwards user message context (`context_text`) in both normal tool-call execution and deterministic fallback enforcement, so language matching stays consistent even when location is normalized.
- Reduced auto-skill false positives in chat:
  - Skills matcher now treats generic words (`tool`, `tools`, `skill`, `skills`, etc.) as stop words.
  - Prevents irrelevant auto-loaded skills (e.g. `mcporter`, `sherpa-onnx-tts`) on generic troubleshooting questions.
- Optimized cron delivery runtime to stay natural but lightweight:
  - Reminder fire path now uses a small direct `provider.chat(...)` rewrite helper instead of full `AgentLoop.process_direct(...)`.
  - Keeps AI-natural reminder phrasing while reducing per-job runtime overhead and avoiding extra tool-loop/critic/session work on delivery turns.
- Fixed Codex backend compatibility for user-only/system-less turns:
  - Added non-empty default `instructions` in request builder to avoid `{"detail":"Instructions are required"}` errors.
- Continued `AgentLoop` modular refactor:
  - Added `kabot/agent/loop_core/message_runtime.py` for message processing, approval flow, system message handling, and isolated execution.
  - Added `kabot/agent/loop_core/routing_runtime.py` for route context and per-agent model resolution.
  - `kabot/agent/loop.py` now delegates these flows via compatibility wrappers and is reduced to 633 lines.
- Added regression tests:
  - `tests/providers/test_openai_codex_backend.py` (tools forwarded + function_call parsing)
  - `tests/agent/test_router.py` (weather/reminder forced complex route)
  - `tests/agent/test_tool_enforcement.py` (required-tool detection + deterministic fallback execution)
  - `tests/agent/test_loop_facade_compat.py` (loop facade delegation compatibility)
  - `tests/agent/test_fallback_i18n.py` (multilingual fallback detection/message rendering)
  - `tests/agent/test_cron_fallback_nlp.py` (location extraction for mixed weather queries)
  - `tests/agent/test_skills_matching.py` (guard against irrelevant auto skill-loading)
  - `tests/tools/test_weather_tool.py` (location normalization + fallback path behavior + care-advice output, including extreme-heat warning)
  - `tests/cron/test_parse.py` now covers multilingual relative-time parsing
  - `tests/cron/test_callbacks.py` (cron callback/fallback delivery behavior)
  - `tests/cron/test_service_facade.py` (cron service -> cron/core delegation compatibility)
- Added centralized i18n runtime foundation:
  - New `kabot/i18n/locale.py` for language detection and `kabot/i18n/catalog.py` for translation keys.
  - `kabot/agent/fallback_i18n.py` now acts as compatibility facade over centralized i18n.
- Unified multilingual lexicon to reduce parser/routing drift:
  - New `kabot/agent/language/lexicon.py` shared by router, cron NLP fallback, and quality runtime immediate-action matcher.
- Cron tool/action responses are now user-language-aware:
  - `kabot/agent/tools/cron_ops/actions.py` now renders status/error/success text via i18n keys.
  - `CronTool` now carries per-request context text for language selection.
- Hardened required-tool guardrail against wrong-tool loops:
  - `run_agent_loop` now enforces fallback when model repeatedly calls non-required tools for weather/reminder requests.
- Weather output now includes source transparency:
  - Open-Meteo and wttr responses append source metadata before care advice.
- Added lightweight cron resource policies to keep scheduler scalable:
  - New `kabot/cron/policies.py`.
  - `CronService` now supports per-destination capacity limit and duplicate schedule rejection.
- Setup wizard now has simple-first mode selection:
  - New `Simple (Recommended)` vs `Advanced` mode in menu flow.
  - Simple mode hides advanced maintenance sections (gateway/logging/doctor) by default.
- Added new regression tests:
  - `tests/agent/test_i18n_locale.py`
  - `tests/agent/test_multilingual_lexicon.py`
  - `tests/agent/test_tool_runtime_guards.py`
  - `tests/cron/test_resource_policies.py`
  - Extended `tests/cron/test_cron_tool.py` and `tests/tools/test_weather_tool.py` for localization/source behavior.

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
