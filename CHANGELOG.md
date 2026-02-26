# Changelog

All notable changes to Kabot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.7] - 2026-02-26

### Added
- **Skills Config Canonical Helpers**:
  - Added `kabot/config/skills_settings.py` to normalize skill settings across canonical and legacy formats.
  - Added canonical handling for:
    - `skills.entries.<skill_key>`
    - `skills.allowBundled`
    - `skills.load.managedDir`
    - `skills.load.extraDirs`
  - Added helper APIs for env injection + entry updates used by CLI and setup wizard.
- **Web Search Kimi Provider**:
  - Added `kimi` provider support to `web_search` runtime.
  - Added `tools.web.search.kimi_api_key` and `tools.web.search.kimi_model` config fields.
  - Added Kimi setup prompts in setup wizard tools section.
- **Gateway HSTS Security Header**:
  - Added optional gateway security header config:
    - `gateway.http.security_headers.strict_transport_security`
    - `gateway.http.security_headers.strict_transport_security_value`
  - Webhook gateway now emits `Strict-Transport-Security` for HTTPS/forwarded-HTTPS requests when enabled.
- **Channels Wizard Security Inputs (`allowFrom`)**:
  - Added explicit `allowFrom` prompts for legacy channel setup flows:
    - Telegram, Discord, WhatsApp, Feishu, DingTalk, QQ, Email.
  - Added Slack access policy setup in wizard:
    - DM policy (`open` / `allowlist`) + `dm.allow_from`.
    - Group policy (`mention` / `open` / `allowlist`) + `group_allow_from`.
  - Added `allowFrom` prompts for channel instances (add/edit) and value parser with dedupe (comma/newline input).
- **Per-Bot Agent Model Picker in Channels Wizard**:
  - Added guided model picker for auto-created agents in channel instance flow (browse configured providers or manual input).
  - Supports dedicated model selection per bot instance without forcing global default model changes.
- **Legacy Channel AI Binding in Wizard**:
  - Added optional AI routing step after legacy channel setup (Telegram/WhatsApp/Discord/Slack/Feishu/DingTalk/QQ/Email).
  - Users can now bind channel to existing or new dedicated agent and set per-channel model from configured providers.
  - Wizard creates/updates channel-level bindings (`match.channel=<channel>`, `account_id="*"`) for clear default routing.
  - Added secure prompt behavior for existing credentials (`leave empty to keep existing`) so token values are no longer shown as defaults in prompt suffix.
- **WhatsApp Bridge UX + Runtime Auto-Start**:
  - Added QR login flow that auto-returns to setup wizard after connection confirmation (no longer requires manual Ctrl+C to continue setup).
  - Added setup prompt to start WhatsApp bridge in background immediately after setup.
  - Added bridge health helpers (`is_bridge_reachable`, `wait_for_bridge_ready`, `is_local_bridge_url`) and background launcher utility (`start_bridge_background`).
- **OpenRouter Catalog Expansion**:
  - Added curated OpenRouter model refs to the static registry for wizard browsing:
    - `openrouter/auto`
    - `openrouter/anthropic/claude-sonnet-4-5`
    - `openrouter/anthropic/claude-opus-4-5`
    - `openrouter/deepseek/deepseek-r1`
    - `openrouter/qwen/qwen-2.5-vl-72b-instruct:free`
    - `openrouter/google/gemini-2.0-flash-vision:free`
    - `openrouter/meta-llama/llama-3.3-70b-instruct:free`
    - `openrouter/moonshotai/kimi-k2.5`
    - plus related refs used in OpenRouter-based flows.
  - Added OpenRouter aliases (`openrouter`, `or-auto`, `or-sonnet`, `or-qwen-vl`) for faster model input in setup flow.

### Changed
- **Workspace Auto-Bootstrap for Persona Files**:
  - Workspace setup now auto-initializes baseline persona files (`AGENTS.md`, `SOUL.md`, `USER.md`) plus `memory/MEMORY.md` without extra manual commands.
  - Channel wizard auto-created agents now initialize their workspace templates automatically.
  - Interactive `kabot setup` now creates templates in the configured workspace path (not only default path), reducing post-setup manual fixes.
- **Skills Loader Source Precedence + Config-Aware Eligibility**:
  - `SkillsLoader` now supports layered source precedence:
    - workspace (`<workspace>/skills`) >
      workspace agents (`<workspace>/.agents/skills`) >
      personal agents (`~/.agents/skills`) >
      managed (`~/.kabot/skills` or `skills.load.managedDir`) >
      bundled (`kabot/skills`) >
      extraDirs.
  - Added managed skills support (`~/.kabot/skills`) when skills config is active.
  - Added per-skill entry semantics in runtime/listing:
    - `entries.<skill>.enabled` (disable skill)
    - `entries.<skill>.env` and `apiKey` for env requirement satisfaction.
  - Added bundled allowlist enforcement for bundled skills via `skills.allowBundled`.
- **Setup Wizard Skills Persistence**:
  - Skills env setup now writes to canonical `skills.entries.<skill_key>.env`.
  - Wizard skill env injection now reads both canonical (`entries`) and legacy flat skill env formats.
  - Skills status board now reports disabled + allowlist-blocked counts explicitly.
  - Added hybrid skills checkbox adapter (`kabot/cli/wizard/skills_prompts.py`) with safe fallback.
  - Skills dependency setup now runs in **manual planning mode**:
    - setup wizard does not execute dependency installers automatically,
    - prints per-skill install plan (and prompts node manager only when node installers are selected),
    - keeps install preferences in canonical `skills.install`.
- **Context Builder Skills Config Wiring**:
  - `ContextBuilder` now accepts skills config and passes it to `SkillsLoader`.
  - `AgentLoop` now injects runtime `config.skills` into `ContextBuilder` so prompt skill resolution follows config entries + precedence.
- **Runtime Fallback Resilience**:
  - Added implicit runtime fallback rule for OpenAI/OpenAI-Codex primary models:
    - if explicit fallback chain is empty and Groq credentials exist, Kabot now auto-injects `groq/meta-llama/llama-4-scout-17b-16e-instruct` as fallback.
- **Docs Filename Standardization**:
  - Renamed `HOW-TO-USE.md` to `HOW_TO_USE.MD`.
  - Updated primary README docs link to the new file name.
- **Setup Wizard OpenAI Post-Login Chain**:
  - OpenAI post-login default chain now appends Groq fallback when Groq credentials are configured.
- **Skills Wizard Env Setup UX**:
  - Skills setup now uses wording based on environment variables (`Configure skill environment variables`) instead of API-key-only phrasing.
  - Selected skills now prompt for all missing required env vars (not only `primaryEnv` / first env), with cross-skill dedupe so shared env vars are asked once.
- **Model Picker Credential Guardrails**:
  - `Select Default Model` now filters aliases/model browsing to providers that already have saved API key/OAuth credentials.
  - Manual model entry now blocks models from providers without saved credentials and shows a warning to login first.
  - Added explicit warning when no authenticated providers are available for default model selection.
- **Channels Wizard Multi-Bot UX**:
  - Channel instance creation/edit flow now includes security and model choices inline, reducing manual JSON edits for multi-bot setup.
  - Allows simpler setup for scenarios like bot A/B/C using different providers/models via agent binding + model override.
  - Added empty-state guidance in `Manage Channel Instances` for one-click multi-bot onboarding (`Add Instance` / `Quick Add Multiple`).
  - Renamed top menu entry to `Manage Channel Instances (Add Multiple Bots)` when instance list is empty.
- **WhatsApp Channel Startup Behavior**:
  - WhatsApp channel now attempts to auto-start local bridge (`ws://localhost/...`) when bridge is unreachable, then reconnects automatically.
  - Added throttling on bridge start attempts to avoid aggressive restart loops.

### Fixed
- **Skills Config Migration Key Integrity**:
  - Preserved constant-style env keys (e.g. `OPENAI_API_KEY`) during config camel/snake normalization and migration write-back.
  - Added migration persistence path that writes migrated config atomically with timestamped backup copy.
- **CLI Skill Env Injection Format Gap**:
  - CLI startup env injection now supports both `skills.entries` and legacy flat `skills.<name>.env`.
- **Codex Tool-Call Context Integrity (Cron/Tools)**:
  - Fixed tool-call history assembly when assistant returns both text and tool calls in one turn.
  - `process_tool_calls()` now preserves/attaches `tool_calls` on the assistant message instead of leaving only `tool` outputs.
  - Prevents ChatGPT Codex backend `400` errors like:
    - `No tool call found for function call output with call_id ...`
  - Reduces duplicate side effects (e.g. repeated reminder scheduling) caused by replays after orphaned tool-output failures.
- **OpenAI/Codex Runtime Fallback Regression**:
  - Re-enabled implicit runtime fallback injection for OpenAI/OpenAI-Codex primaries when explicit chain is empty and Groq credentials are present.
  - Added regression tests to ensure fallback is injected only for eligible OpenAI primaries and not injected for unrelated/no-credential cases.
- **Cross-Provider Fallback Credential Leak**:
  - Fixed runtime bug where fallback attempts could reuse primary provider token (e.g. OpenAI Codex JWT sent to Groq).
  - LiteLLM provider now resolves API key/API base/headers per attempted model provider in fallback chain.
  - `_make_provider()` now builds provider credential maps for primary + runtime fallback models.
- **Regression Coverage (Fallback + Channels Wizard)**:
  - Added tests for provider-specific credential use in cross-provider fallback path.
  - Added tests for `allowFrom` parsing, instance config `allowFrom` capture, and per-agent model picker behavior in channel wizard.
- **Regression Coverage (WhatsApp Bridge)**:
  - Added setup wizard test to verify QR-connect flow + optional background bridge startup path.
  - Added runtime channel tests to verify local bridge auto-start and non-local bridge skip behavior.
- **OpenRouter Manual Model Input Validation**:
  - Fixed model-format validation to accept nested provider paths (e.g. `openrouter/vendor/model:free`) instead of only two-segment IDs.
  - Provider-scoped manual picker now auto-prefixes vendor/model style input (e.g. in OpenRouter scope, `arcee-ai/trinity-large-preview:free` becomes `openrouter/arcee-ai/trinity-large-preview:free`).
  - Added regression tests for nested format validation, scoped autoprefix behavior, and OpenRouter catalog/model-status coverage.
- **Expired OAuth Token Failover Latency**:
  - Added proactive pre-check for expired `openai-codex` JWT tokens so runtime skips directly to fallback models without first waiting for repeated 401 failures.
  - Added auth-failure cooldown in `LiteLLMProvider` (`180s`) so temporarily invalid providers are not retried on every message/critic retry loop.
  - Extended failover classification to treat `invalid_or_expired_jwt` / `invalid or expired jwt` as `auth` errors.
  - Added regression tests for proactive skip, cooldown behavior, and cooldown expiry re-entry.

### Included From 2026-02-24 Batch

#### Added
- **Kabot-Aligned Provider Expansion (Setup + Runtime)**:
  - Added provider/auth coverage for `together`, `venice`, `huggingface`, `qianfan`, `nvidia`, `xai`, `cerebras`, `opencode`, `xiaomi`, `volcengine`, and `byteplus`.
  - Added additional parity providers: `synthetic`, `cloudflare-ai-gateway`, and `vercel-ai-gateway` (schema + registry + setup auth flow).
  - Added matching provider specs in runtime registry with default API bases for OpenAI-compatible gateway flows.
  - Added simple API-key handlers for each newly surfaced provider in setup auth flow.
- **Expanded Static Model Catalog**:
  - Added curated model entries across Together, Venice, Hugging Face, Qianfan, NVIDIA, OpenCode, xAI, Cerebras, Xiaomi, Volcano Engine, and BytePlus.
  - Added full Kabot parity blocks for extended refs: Together, Venice, Kilo Gateway, OpenCode Zen static fallback set, Moonshot variants, MiniMax variants, Volcengine/BytePlus coding routes, Synthetic catalog, and gateway refs for Cloudflare/Vercel.
  - Added aliases for fast model picking (`venice-opus`, `hf-r1`, `qianfan`, `nvidia`, `opencode`, `xai`, `cerebras`, `xiaomi`, `doubao`, `byteplus`).
- **Model Status Coverage**:
  - Added status catalog entries for new provider models so setup wizard can display them in model browser and picker.
  - `model_status.py` now auto-syncs `CATALOG_ONLY` from `STATIC_MODEL_CATALOG` to reduce manual drift when model lists expand.

#### Changed
- **Provider Matching Accuracy** (`config/schema.py`):
  - `_match_provider()` now prioritizes explicit model prefix matching (e.g. `together/...`) before keyword matching.
  - Prevents ambiguous cross-provider keyword collisions (for example `moonshot` substring inside Together model IDs).
- **Setup Wizard Auto Model Chain**:
  - Simple mode auto-chain now includes newly supported providers so users can connect multiple keys and instantly get primary + fallback chains without manual JSON edits.
- **Setup Wizard Maintainability Refactor**:
  - Extracted reusable wizard UI primitives to `kabot/cli/wizard/ui.py` (`ClackUI`) so terminal rendering and style tuning are centralized.
  - Extracted channel menu option composition to `kabot/cli/wizard/channel_menu.py` and wired `setup_wizard.py` to reuse it.
  - Extracted section methods to `kabot/cli/wizard/setup_sections.py` and bound them back into `SetupWizard` to decouple section logic from the orchestrator file.
  - Split extracted section methods into domain modules under `kabot/cli/wizard/sections/` (`core`, `model_auth`, `tools_gateway_skills`, `channels`, `operations`) with a thin binder aggregator.
  - Reduced `kabot/cli/setup_wizard.py` to under 1000 LOC (now ~411 lines) while preserving setup wizard behavior and test coverage.
  - Kept setup flow behavior stable while reducing coupling in `setup_wizard.py` for easier future section-level refactors.
- **Crash Recovery Routing** (`kabot/agent/loop.py`):
  - Recovery delivery no longer uses synthetic `system` outbound channel.
  - Agent now resolves target from sentinel context (`message_id` first, then `session_id`) and only sends to valid channel/chat routes.
  - Added support for instance-aware channel keys in recovery target parsing (e.g. `telegram:<instance>`).
- **Session Memory Continuity** (`kabot/agent/loop_core/session_flow.py`):
  - Added best-effort periodic conversation dump to daily notes via `context.memory.append_today(...)` on session finalization.
  - Each turn now appends compact `U:`/`A:` entries with session key for better cross-session continuity.

#### Fixed
- **Auth Alias Routing**:
  - Added compatibility aliases like `venice-ai`, `hf`, `x-ai`, and `opencode-zen` to ensure login calls resolve to the correct Kabot provider.
  - Added underscore/hyphen mapping aliases for gateway providers (`cloudflare-ai-gateway`, `vercel-ai-gateway`) across auth save/status paths.
- **Catalog Parity Gaps**:
  - Closed missing provider/model parity gaps that caused Kabot-sourced model refs to appear unsupported in Kabot setup flows.
- **Hook Event Alias Compatibility** (`kabot/plugins/hooks.py`):
  - Hook manager now normalizes lifecycle event names so legacy uppercase aliases (e.g. `ON_STARTUP`) and canonical lowercase names (e.g. `on_startup`) interoperate.
  - Prevents plugin hook misses caused by mixed alias/case usage across runtime and plugin registration.
- **UTF-8 Surrogate Safety Across Runtime + Memory + Telegram**:
  - Added centralized UTF-8 text safety helper (`kabot/utils/text_safety.py`) to normalize invalid/unpaired surrogate sequences before transport/persistence.
  - `_sanitize_error()` now guarantees UTF-8-safe output for user-facing errors (prevents UnicodeEncodeError in downstream channels).
  - `SQLiteMetadataStore.add_message()` now sanitizes message content before DB insert, preventing failures like `surrogates not allowed`.
  - Telegram send path now sanitizes outgoing content/chunks before HTML/plain-text dispatch fallback.
- **Regression Coverage**:
  - Added tests for hook alias normalization, recovery target resolution, and daily-notes session dump behavior:
    - `tests/plugins/test_hooks.py`
    - `tests/agent/test_recovery_routing.py`
    - `tests/agent/test_session_persistence_fail_open.py`
  - Added UTF-8 safety tests for error sanitization, SQLite message persistence, and text safety helper:
    - `tests/agent/loop_core/test_execution_runtime.py`
    - `tests/memory/test_sqlite_store_utf8.py`
    - `tests/utils/test_text_safety.py`

## [0.5.6] - 2026-02-24

### Added
- **Embedding Auto-Unload System**: Intelligent memory management for the sentence-transformers embedding model (`all-MiniLM-L6-v2`)
  - Auto-unload after 5 minutes idle via configurable `auto_unload_timeout` in config (default: 300s, set 0 to disable)
  - Manual unload API: `memory.unload_resources()` for explicit resource cleanup
  - Recursive PyTorch module clearing with `module.cpu()` + parameter/buffer dereferencing
  - Platform-specific memory trimming: Windows `EmptyWorkingSet`, Linux `malloc_trim`, macOS `gc.collect()`
  - Model reloads transparently on next `search_memory()` â€” zero quality/intelligence loss
  - Thread-safe with `threading.RLock` and double-check locking pattern
- **ChromaDB Segment Cache Cap**: Added `chroma_memory_limit_bytes=50MB` to `Settings()` to limit in-memory HNSW segment cache
- **Memory Statistics API**: `embeddings.get_memory_stats()` returns model state, load count, and unload count

### Changed
- **Memory Factory** (`kabot/memory/memory_factory.py`): Added `auto_unload_seconds` passthrough from config with input validation
- **Sentence Embeddings** (`kabot/memory/sentence_embeddings.py`): Complete rewrite â€” added lazy loading, timer-based auto-unload, `_unload_model_internal()` with recursive cleanup, `warmup()` for background pre-loading
- **Hybrid Memory Manager** (`kabot/memory/chroma_memory.py`): ChromaDB `PersistentClient` now uses `chroma_memory_limit_bytes` cache cap; cleaned up invalid legacy config parameters

### Fixed
- **Subprocess Communication (Windows)**: Fixed embedding worker subprocess hang on Windows due to stdin buffering
  - Changed `_embedding_worker.py` stdin reading from `for line in sys.stdin:` to `while True: readline()` for Windows subprocess pipe compatibility
  - Changed `sentence_embeddings.py` stderr handling from `subprocess.DEVNULL` to `None` to prevent pipe buffer deadlock
  - Updated all memory tests to use `_is_subprocess_alive()` instead of deprecated `_model` attribute
  - Rewrote `test_memory_leak.py` to verify subprocess lifecycle (process termination) instead of main process memory
- **Version Sync**: `__init__.py` and `pyproject.toml` version now matches git tag (was stuck at 0.5.3)
- **CHANGELOG Accuracy**: Replaced fabricated RAM metrics with empirically measured psutil RSS data

### How Auto-Unload Works
```
Kabot idle (91 MB) â†’ User sends message â†’ model loads (+359 MB = 450 MB)
                                            â†“
                   User goes quiet â†’ 5 min timer expires â†’ model unloaded (443 MB*)
                                            â†“
                   Next message â†’ model reloads (3-5s) â†’ fully functional
```
> *CPython's arena-based allocator does not return freed memory to OS. Only a process restart returns to 91 MB. This is expected Python behavior, not a leak.

### Measured RAM (empirical, psutil RSS)
| State | RAM | Component Cost |
|-------|-----|----------------|
| Python + Kabot imports (no model) | ~41 MB | Baseline |
| + ChromaDB initialized (HNSW on disk) | ~91 MB | +49 MB |
| + Embedding model loaded | ~450 MB | +359 MB (sentence-transformers) |
| After model unload + gc.collect() | ~443 MB | CPython retains memory |

### Technical Details
- Thread-safe lazy loading with `threading.RLock` + double-check locking
- Timer-based auto-unload with `threading.Timer` (resets on every embed call)
- Recursive module cleanup: `module.cpu()` â†’ clear parameters â†’ clear buffers â†’ `del` children
- Platform trimming: `ctypes.windll.kernel32.SetProcessWorkingSetSize` (Windows), `ctypes.CDLL(None).malloc_trim(0)` (Linux)
- 874 tests passing, 6 skipped

## [0.5.5] - 2026-02-24

### Added
- **Embedding Auto-Unload**: Embedding model (`all-MiniLM-L6-v2`) automatically unloads after 5 minutes idle
  - Configurable via `auto_unload_timeout` in config (default: 300s)
  - Manual unload: `memory.unload_resources()`
  - Recursive PyTorch module clearing + platform-specific memory trimming
  - Model reloads transparently on next search â€” zero quality loss
- **ChromaDB Segment Cache Cap**: Added `chroma_memory_limit_bytes=50MB` to limit in-memory segment cache

### Measured RAM (empirical, psutil RSS)
| State | RAM | Notes |
|-------|-----|-------|
| Python + imports (no model) | ~41 MB | Baseline |
| + ChromaDB initialized | ~91 MB | +49 MB for HNSW index |
| + Embedding model loaded | ~450 MB | +359 MB for sentence-transformers |
| After model unload + gc | ~443 MB | CPython allocator retains memory |

> **Note:** CPython's arena-based memory allocator does not return freed memory to the OS unless entire arenas are empty. The ~443 MB after unload is expected Python behavior, not a leak.

### Technical Details
- Thread-safe lazy loading with double-check locking
- Timer-based auto-unload with `threading.Timer`
- 874 tests passing, 6 skipped

## [0.5.4] - 2026-02-23

### Added
- **Tool Loop Detection** (`kabot/agent/loop_core/tool_loop_detection.py`): Detects stuck agents calling same tool repeatedly
  - Generic repeat detection (warning at 10, critical block at 20 identical calls)
  - Ping-pong detection (Aâ†”B alternating tool calls)
  - Sliding window of 30 calls with MD5 parameter hashing
- **Tool Policy Profiles** (`kabot/agent/tools/tool_policy.py`): Per-agent tool access control
  - 5 profiles: minimal, coding, messaging, analysis, full
  - 6 tool groups: fs, runtime, web, memory, sessions, automation
  - Owner-only tools: cron, exec, spawn
- **Failover Error Classification** (`kabot/core/failover_error.py`): Error categorization for smarter retry
  - 7 categories: billing (402), rate_limit (429), auth (401), timeout (408/503), format (400), model_not_found (404), unknown
  - Status code + error message + error code classification
- **Context Window Guard** (`kabot/agent/loop_core/context_guard.py`): Prevents crashes from tiny context windows
  - Hard block below 16K tokens, warning below 32K tokens

### Changed
- **Agent Loop**: Integrated LoopDetector â€” critical loops blocked, warnings logged
- **Tool Registry**: Policy profile filtering in `get_definitions()`
- **Resilience Layer**: Uses failover reason for smarter retry/fallback decisions

## [0.5.3] - 2026-02-23

### Added
- **Chatbot-Accessible Auto-Update System**: Users can now check for updates and trigger updates via natural language
  - `check_update` tool: Detects available updates from GitHub releases and git commits
  - `system_update` tool: Executes update (git pull or pip upgrade) with restart confirmation
  - `UpdateService`: Handles platform-specific restart logic (Windows/Linux/Mac)
  - Supports both git clone and pip install methods
  - Anti-hallucination design: Tools return structured JSON data, not prose
  - Security: Validates working tree, requires restart confirmation, no arbitrary code execution

### Changed
- **Agent Loop**: Registered CheckUpdateTool and SystemUpdateTool in agent tool registry

## [0.5.2] - 2026-02-23

### Added
- **Memory Backend Architecture**: Introduced modular memory system with `MemoryFactory` supporting multiple backends:
  - `hybrid` (default): ChromaDB + SQLite + BM25 for full semantic search
  - `sqlite_only`: Lightweight keyword-based search without embeddings (ideal for Termux/Raspberry Pi)
  - `disabled`: Stateless mode with no memory persistence
- **Memory Configuration UI**: Added interactive memory setup in `kabot config` wizard with backend selection and embedding provider options
- **New Memory Backends**: `SQLiteMemory`, `NullMemory`, and abstract `MemoryBackend` base class
- **Memory Tests**: 7 new test files covering all memory backends and integration scenarios
- **Documentation Plans**: Added architecture design docs for global market tools and memory slot system

### Changed
- **Setup Wizard Enhancement**: Added "Memory" configuration section to setup wizard with backend and embedding provider selection
- **HOW-TO-USE.md**: Updated with comprehensive memory configuration section explaining all backend options
- **Memory Module Structure**: Refactored `kabot.memory` to use factory pattern for cleaner backend instantiation

### Fixed
- **Git Tracking Cleanup**: Removed `memory_db/`, `.claude/`, `.backup/`, `MagicMock/`, and test artifacts from version control
- **Gitignore Improvements**: Added patterns for local settings, test artifacts, and user-specific data directories

## [0.5.1] - 2026-02-23

### Fixed
- **Codex 400 Error Handling**: Implemented auto-retry without tools in `execution_runtime.py` for models that don't support function calling (like chatgpt.com/codex). This allows conversational queries to still be answered naturally by these models.
- **Market Data Resilience (Stock/Crypto)**: Upgraded `StockTool` to handle multi-ticker symbols in parallel and implemented a Fast Path for market queries. Kabot now automatically detects "top 10" or Indonesian market requests and fetches live Yahoo Finance/CoinGecko data without hitting LLM tool-calling errors.
- **RAM Monitoring Routing**: Added missing Indonesian natural language patterns ("periksa ram", "cek ram", "ram pc") to fix routing to `get_process_memory`.
- **Ambiguous Keyword Conflict**: Removed the generic "ram" keyword from `SYSTEM_INFO_KEYWORDS` to ensure RAM-specific queries are always captured by the process-level monitoring tool.
- **Direct Tool Execution (Fast Path)**: Deterministic tools like `get_process_memory` and `get_system_info` now execute directly to bypass LLM tool-calling latency/errors, while still using the AI for the final formatted response.

### Performance & Optimization
- **Startup Latency Fix**: Resolved the ~20s delay during the "Starting Kabot Watchdog..." phase. This was achieved by refactoring the core dependency graph to use lazy-loading for heavy third-party libraries.
- **Lazy-Loading Architecture**:
    - Implemented PEP 562 `__getattr__` in `kabot.memory` for on-demand submodule loading.
    - Deferred initialization of `ChromaDB`, `psutil`, `rank_bm25`, and `LiteLLM` until actually needed by a specific tool or service.
    - Moved service instantiation (Status, Benchmark, Doctor) in `AgentLoop` to lazy properties.
- **Race Condition Mitigation**: Added thread locks to `SentenceEmbeddingProvider` and `HybridMemoryManager` to prevent double-loading of the 400MB+ embedding model when multiple tasks trigger initialization simultaneously.
- **Background Warmup Optimization**: Moved the embedding model pre-warming task to the absolute top of the `AgentLoop.run()` method to maximize parallel processing while the bot initializes its remaining components.

### Added - MHA Squad "Awakening"
- **Native Google Suite Integration**: Built-in support for Gmail and Google Calendar via OAuth 2.0 without relying on external `gog` CLI. Includes `GoogleAuthManager` for token storage and automatic refresh.
- **Google Drive & Docs Expansion**: Added `GoogleDriveTool` and `GoogleDocsTool` to natively search, read, write, and create files/documents on Google Cloud.
- **Auto-Onboarding Agent (CLI)**: Added `kabot train <file>` CLI command to automatically parse (`.pdf`, `.txt`, `.md`) using `DocumentParser`, chunk the text, and inject it directly into a specific agent workspace's ChromaDB memory for instant context.
- **Advanced Web Explorer (Playwright)**: Upgraded `BrowserTool` to support interactive actions: `click(selector)`, `fill(selector, text)`, and `get_dom_snapshot()`. The `get_dom_snapshot` method extracts interactive elements and returns simplified, LLM-friendly DOM maps to enable autonomous web interaction.
- **Google Auth CLI & Wizard**: Added interactive Google Suite OAuth setup directly into `kabot config` (Setup Wizard) and as a standalone `kabot google-auth` CLI command.
- **Process RAM Usage Tool**: Added `get_process_memory` for top RAM-per-process on Windows, Linux, and macOS with multilingual keyword triggers.


### Changed
- **User-Friendly Error Messages**: Model failure errors (HTTP 400, rate limits, network drops) now show clean, actionable messages with `/switch` hints instead of raw Python exceptions with internal API URLs.
- **Error Sanitization**: Added `_sanitize_error()` to strip internal URLs, API keys, and verbose tracebacks from all user-facing error messages in both simple and complex response paths.
- **Multilingual Processing Status**: Replaced hardcoded Indonesian "Sedang memproses..." status with language-neutral English "Processing your request..." for global users.
- **AI-as-Developer Execution Discipline**: Added critical system prompt rules that force the AI to write scripts on-the-fly, execute them immediately using `exec`, verify results, and schedule recurring jobs using `cron` â€” instead of just describing what to do. Includes cross-platform detection for Windows, Linux, macOS, and Termux.

### Added
- **Cross-Platform Server Monitor Tool**: New `server_monitor` tool provides real-time resource usage (CPU load %, RAM used/free GB, disk usage %, uptime, network I/O) with full support for Windows (PowerShell), Linux (bash), macOS (bash), and Termux (Android). Triggered by 40+ multilingual keywords across 7 languages (EN, ID, MS, TH, ZH, KO, JA).

### Changed
- **Startup Time Optimization (~40s â†’ ~3s to Chat-Ready)**: (1) HeartbeatService now waits 30s before first beat, preventing startup blocking. (2) SentenceTransformer embedding model pre-loads in a background thread via `warmup()`. (3) `AgentLoop.run()` kicks off `_warmup_memory()` as a non-blocking background task. Telegram is now chat-ready in ~3s instead of ~40s.
- **Zero-Latency Cold Start**: Migrated heavy LLM libraries (`litellm`, etc.) to lazy-loading scopes, dropping CLI startup time to `< 0.7s`.
- **Asynchronous BM25 Indexing**: Deferred the synchronous `BM25Okapi` indexing to trigger only upon the first explicit user `search()`, removing background startup blocking.
- **SQLite Database Tuning**: Injected PRAGMA `WAL`, `synchronous=NORMAL`, and Memory-Mapped IO pragmas to `sqlite_store.py` to massively speed up asynchronous `EpisodicExtractor` writes without locking the read loop.

## [0.5.0] - 2026-02-22

### Added - Hybrid Memory Architecture (Exceeds Mem0)

- **HybridMemoryManager:** Modular memory orchestrator replacing monolithic `ChromaMemoryManager`.
- **Smart Router:** Query-intent classifier routes to correct memory store (episodic/knowledge/hybrid). Multilingual keyword matching for 8 languages (ID, EN, ES, FR, JA, ZH, KO, TH).
- **Reranker:** Three-stage filtering pipeline with configurable threshold (â‰¥0.6), top-k (3), and hard token guard (500 tokens max). Reduces token injection by 60-72%.
- **Episodic Extractor:** LLM-based auto-extraction of user preferences, facts, and entities after each chat session. Uses existing LLM provider.
- **Memory Pruner:** Scheduled cleanup of stale facts (>30 days) and duplicate merging. Integrates with CronService.
- **Deduplicator:** BM25 + cosine similarity check prevents duplicate fact storage.
- **27 new pytest test cases** across 5 test files in `tests/memory/`.

### Changed

- `ChromaMemoryManager` renamed to `HybridMemoryManager` (backward-compatible alias preserved).
- Memory search now routes through `SmartRouter` to skip irrelevant database hits.
- Results are filtered through `Reranker` before injection into LLM context.

## [0.4.0] - 2026-02-22

### Added - Autopilot Wiring & System Events (2026-02-22)

- **Heartbeat Tasks Execution:** Heartbeat now reads `HEARTBEAT.md` and dispatches active tasks as prompts on each beat.
- **Cron â†’ System Events:** Cron callbacks now emit system events so the agent can react to scheduled job completions.
- **Heartbeat Event Publishing:** Heartbeat injector now publishes system events into the inbound pipeline for unified processing.

### Fixed & Audited - Routing Resilience & Full Roadmap Completion (2026-02-22)

- **Loop Routing Fix:** Modified `message_runtime.py` to force `run_agent_loop` for any message requiring tools or meeting complexity thresholds. This ensures deterministic tool-enforcement logic is always applied.
- **Roadmap Final Audit:** Completed 100% verification audit for 'Full-Parity', 'Kabot Design', and 'Military-Grade' implementation plans. All tasks confirmed as functional and integration-tested.


### Added & Fixed - Windows & Telegram Support (2026-02-21)

- **Windows Shell Execution:** Fixed `ExecTool` to natively use `powershell.exe` on Windows instead of `cmd.exe`.
- **System Information Tool:** Added `SystemInfoTool` to fetch detailed hardware specs (CPU, RAM, GPU, Storage, OS) across Windows, Linux, Termux, and macOS.
- **Telegram Large Messages:** Implemented automatic message splitting in `TelegramChannel` to handle responses larger than 4096 characters without breaking formatting or code blocks.
- **System Cleanup Tool:** Added `CleanupTool` (`cleanup_system`) with 3 levels (quick/standard/deep) for Windows, Linux, macOS, and Termux to free disk space (temp, cache, recycle bin, Windows Update, browser caches, DISM).
- **Improved Tool Usage Behavior:** Updated system prompt to force the LLM to proactively use tools (`exec`, `get_system_info`, `cleanup_system`) instead of telling users to run commands manually.
- **WebFetch/Setup Fixes:** Refined web fetch hash caching and chunking, and fixed setup wizard channel configuration states.

### Added - Kabot Full-Parity Enhancements (2026-02-21)

- **Sub-agent Safety Limits:**
  - Added `SubagentDefaults` config with `max_spawn_depth`, `max_children_per_agent`, and `archive_after_minutes`.
  - `SubagentManager.spawn()` now enforces max-children and nesting-depth limits.
  - Completed subagent runs now auto-archive based on configurable timeout.
- **Heartbeat Delivery and Active Hours:**
  - Added `HeartbeatDefaults` config with `target_channel`, `target_to`, and `active_hours_start/end`.
  - Heartbeat loop now skips execution outside configured active-hours window.
- **Cron Delivery Modes and Webhook:**
  - Added `CronDeliveryConfig` with `announce`, `webhook`, and `none` modes.
  - Added resolver fallback compatibility for legacy `payload.deliver` format.
  - Added webhook POST helper with optional HMAC-SHA256 signature in `X-Kabot-Signature`.
- **Telegram Inline Interactions:**
  - Added `build_inline_keyboard()` helper for inline buttons.
  - Added callback query handling path that publishes button events into `MessageBus`.
  - Added outbound metadata support for inline keyboard rendering.
- **Discord Interactive Components:**
  - Added `kabot/channels/discord_components.py` with `ButtonStyle`, `build_action_row()`, and `build_select_menu()`.
  - Added support for sending `components` in Discord outbound payload metadata.
  - Added `INTERACTION_CREATE` gateway handling and bus integration.
- **Docker Sandbox Module (Optional):**
  - Added `kabot/sandbox/` with `DockerSandbox` async command execution helper.
  - Added `Dockerfile.sandbox` image template for isolated runtime usage.
- **Security Audit Trail:**
  - Added `AuditTrail` JSONL logger (`kabot/security/audit_trail.py`) with append/query support.
  - Added regression tests in `tests/security/test_audit_trail.py`.

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
- **Setup Wizard & Auto-Start "Military-Grade" Section:**
  - Added "Advanced Tools" section to `kabot setup` for optional Perplexity, Grok, and FireCrawl keys.
  - Added **Auto-start (Enable boot-up service)** integration in `kabot setup` for 1-click persistence.
  - Automated Termux `runit` service creation via `kabot remote-bootstrap`.
  - Upgraded `get_service_status` to accurately detect active boot services uniformly across Windows, macOS, Linux, and Termux.
  - Integrated "Freedom Mode" toggle to disable HTTP guards and auto-approve commands for trusted environments.
- **Fixed:**
  - Resolved `TypeError` in `WebFetchTool` initialization that crashed the gateway process.
  - Fixed `[WinError 2]` during WhatsApp bridge setup on Windows by resolving `npm.cmd` absolute path.
  - Fixed logic bug where `kabot setup` failed to prompt for API keys of complex skills (Nano Banana, etc.).
  - Fixed `AttributeError` exception when running `kabot doctor` Health Check from setup wizard by adding `check_requirements` to the tool base class.

### Fixed - Setup Wizard Kabot Config Flow (2026-02-21)

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
  - Extended relative-time parsing in `kabot/cron/parse.py` for `minit`, Thai units, and Chinese units (e.g. `åˆ†é’ŸåŽ`).
  - Improved weather location extraction for mixed queries (`tanggal + suhu` / `right now`) so city parsing no longer keeps noise tokens like `berapa` or `right`.
- Fixed root weather-tool failure mode for noisy LLM tool arguments:
  - `WeatherTool` now normalizes incoming `location` text before fetch (`suhu di cilacap sekarang` -> `Cilacap`).
  - Weather location normalization now strips trailing city descriptors (`kota`, `city`, `kabupaten`, etc.) to improve geocoding compatibility.
  - For `simple` mode, weather retrieval now prefers Open-Meteo first (structured current weather) and uses wttr as fallback.
  - Added safer request handling (`quote_plus`, explicit User-Agent, redirect handling) and cleaner error diagnostics.
  - Added support for `png` output mode as URL passthrough for wttr.
- Improved weather reply quality to be more human-care oriented and actionable:
  - `WeatherTool` now appends a practical care tip based on parsed temperature + condition (heat/cold/rain/storm/fog), e.g. sunscreen, hydration, jacket, umbrella.
  - Added explicit extreme-heat tier (`>=36Â°C`) with stronger heatstroke caution and midday outdoor activity guidance.
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
- Added Kabot-style trusted freedom profile in setup wizard (`Tools & Sandbox`):
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

### Added - Reliability, Security, and Kabot Parity Enhancements (2026-02-19)

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
- Added Kabot-style routing field extraction in base channel handling:
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

#### Plugin Lifecycle Management (Kabot-style parity upgrade)
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
### Added
- **Memory Slot Architecture**: Users can now switch memory backends (`hybrid`, `sqlite_only`, `disabled`) via `config.json` or the interactive Setup Wizard. No code changes required.
- **MemoryBackend ABC**: Abstract base class defining the contract for all memory backends, enabling future extensibility (Redis, Mem0, etc.).
- **SQLiteMemory**: Lightweight memory backend using only SQLite (no ChromaDB or embeddings). Ideal for Termux or Raspberry Pi.
- **NullMemory**: No-op memory backend for users who want to disable memory entirely.
- **MemoryFactory**: Config-driven factory that reads `config.json["memory"]["backend"]` and instantiates the correct backend.
- **Setup Wizard Memory Menu**: New "Memory" menu option in the setup wizard for selecting backend and embedding provider.
- `GoogleAuthManager` auto-initialization check: Now handles missing OAuth `.gemini/` credentials properly on app start, prompting a smooth re-auth instead of crashing instantly.
- **Smart Gateway Binding Defaults**: Setup wizard now defaults to `lan` interface if running on a VPS/Cloud directly, and `loopback` (localhost) if running locally or behind a known proxy.
- **Fixed agent routing logic** (`kabot/agent/loop.py:_resolve_model_for_message`)
  - Corrected peer resolution for proper model selection
  - Fixed session key handling in background sessions
- **Resolved mock setup issues**
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

**Kabot Parity: 85% â†’ 100% (COMPLETE)**

This phase expands the message bus from chat-only to full system event support, enabling real-time monitoring of agent internals.

#### System Event Architecture
- **Expanded SystemEvent class** (`kabot/bus/events.py`)
- Added factory methods for lifecycle, tool, assistant, and error events
- Monotonic sequencing per run_id for event ordering
- Pattern from Kabot: src/infra/agent-events.ts

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
- **Achievement**: 100% Kabot parity reached

### References
- Pattern source: Kabot src/infra/agent-events.ts
- Commit: `25bde71` - feat(phase-14): expand event bus to full system events

---

### Fixed - Phase 13 Completion: Critical Gap Integration (2026-02-17)

**Kabot Parity: 65% â†’ 85% (ACTUALLY ACHIEVED)**

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
- Ultimate verification: `docs/kabot-analysis/ultimate-verification-gap-kabot-kabot.md`
- Commit: `2a5e276` - feat(phase-13): complete Kabot parity

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
- Implementation plan: `docs/plans/2026-02-16-kabot-parity-phase-13.md`
- Gap analysis: `docs/kabot-analysis/kabot-gap-analysis.md`
- Technical findings: `docs/kabot-analysis/deep-technical-findings.md`

---

## Previous Releases

### Phase 12 and Earlier
See git history for previous changes.


