# Changelog

All notable changes to Kabot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Runtime now hardens follow-up/tool continuity for action turns:
  - unavailable `required_tool` routes are dropped only when tool-registry availability is known, avoiding false negatives in sparse/mock runtimes while still preventing stale parser latches from forcing removed tools,
  - direct action-delivery flow (`required_tool` + `requires_message_delivery`) now archives directory artifacts before sending when `archive_path` is available, keeping artifact evidence aligned with the actually delivered file.
- Built-in finance execution lane is now disabled in the default agent tool registry:
  - `stock`, `stock_analysis`, and `crypto` are no longer registered by default in `AgentLoop`,
  - this keeps finance execution on skill/explicit-tool lanes instead of accidental parser fallback reuse.

### Fixed
- Indonesian file-delivery parsing is more robust for real chat phrasing:
  - `kirim file TELEGRAM_DEMO.md kesini` now resolves as a valid message-send request even with bare filenames,
  - concise direct-send turns like `kirim file tes.md` now map to message delivery intent (instead of being trapped on read-only file parsing),
  - `cari file ... lalu kirim ke chat ini` stays on the search lane (`find_files`) instead of prematurely collapsing into direct message-send routing,
  - `kirim file X di folder Y\ kesini` now prefers explicit filename extraction and correctly joins with folder context instead of treating delivery suffix text as part of the path.
- Relative folder navigation parsing now handles shorthand open commands with trailing slashes (`buka bot\`) more reliably.
- Message delivery now prefers explicit navigation context over stale internal paths:
  - when `last_tool_context.path` drifts to an internal temp folder (for example `.basetemp`) but `last_navigated_path` points to the actual user-opened folder, bare-filename sends like `kirim file tes.md ke sini` now resolve against the navigated folder first,
  - `list_dir` and read-file directory fallbacks now persist `last_navigated_path` so follow-up send-file turns can anchor to the folder the user just opened,
  - message fallback now also reads `last_navigated_path` from session metadata (not only inbound message metadata), so CLI/agent direct turns keep navigation continuity across turns,
  - finalized session state now copies `last_navigated_path` from inbound metadata into persisted session metadata, ensuring one-shot agent invocations still remember the last opened folder on the next turn,
  - session initialization now hydrates `last_navigated_path` back into inbound turn metadata (and seeds `last_tool_context` when missing), so follow-up file actions can reuse prior folder context without re-asking path,
  - follow-up send commands without explicit target (for example `kirim langsung`) now reuse persisted `last_delivery_path` from session context when available,
  - session state now persists and hydrates `last_delivery_path` across turns, so one-shot chat commands can still reuse the last successfully delivered file,
  - if a bare-filename send still resolves to an internal temp path outside the active navigated folder, Kabot now returns not-found instead of sending stale temp artifacts.
- Find-files fallback now respects active navigation context:
  - `find_files` root resolution now checks `last_navigated_path` before falling back to older `last_tool_context.path`, preventing context drift during search→send workflows,
  - this behavior is now aligned in both filesystem and action-request resolver paths used by the tool-enforcement facade.
- List-directory follow-up fallback no longer hijacks explicit send-file requests:
  - when action-intent inference resolves a conflicting file/send tool (for example `message`), the `list_dir` follow-up latch is skipped,
  - this prevents `kirim file tes.md kesini` from being downgraded into `list_dir` and returning false `File not found` errors.
- Read-file fallback no longer hard-fails on directory context for broad project-inspection turns:
  - when `read_file` is requested but the resolved context path is a directory, Kabot now falls back to `list_dir` (when available) instead of returning `Not a file` immediately.
- Low-information follow-ups now ignore stale assistant helper prompts more reliably:
  - assistant-style text like `Please provide the file path ... (example: config.json or C:\path\to\file.json)` is treated as stale metadata on short follow-ups,
  - placeholder path patterns such as `C:\path\to\file.json` are now filtered from explicit path extraction,
  - intent-mismatch guards now allow `message` tool execution on short send-only turns (for example `kirim langsung`) when session delivery context is present.
- Explicit send-file requests no longer get downgraded into directory-followup routing:
  - side-effect demotion now keeps parser-selected tools when concrete payload is present (for example `kirim file tes.md kesini`),
  - this prevents a stale `list_dir` follow-up latch from overriding `message` intent and returning false `File not found: tes.md` errors.

## [0.6.4] - 2026-03-13

### Changed
- External skill follow-ups now behave more like a real skill setup lane instead of falling back to generic runtime enforcement:
  - when a committed/contextual action is already on an external skill lane, Kabot no longer forces a tool call before allowing a concrete next-step reply,
  - follow-ups like `jq sudah` can now continue naturally with the next blocker or credential request instead of tripping `I couldn't verify completion because no tool or skill execution happened.`,
  - the runtime now marks these turns with `external_skill_lane`, so external-skill setup/execution stays differentiated from generic tool-backed action flow.
- Skill availability cache now refreshes when the runtime environment changes:
  - `SkillsLoader.list_skills(...)` invalidates its snapshot cache when `PATH` or other environment variables change in-process,
  - this closes a real replay bug where installing a missing CLI dependency like `jq` still left an external skill stuck in the old `unavailable` state for the next turn.
- OpenClaw-style skill invocation policy is now wired into real Kabot behavior instead of staying as inert frontmatter:
  - skills now expose `user-invocable`, `disable-model-invocation`, `command-dispatch`, `command-tool`, and `command-arg-mode` through Kabot's skill status/runtime metadata,
  - slash-command surfaces now hide skills marked `user-invocable: false`,
  - Telegram native skill commands now honor `command-dispatch: tool` + `command-tool` by seeding a direct tool-execution lane instead of always rephrasing the request back through the model,
  - the execution runtime now has a fast path for these skill-command tool dispatches, so eligible slash-invoked skills can bypass model generation and execute the target tool directly,
  - skills marked `disable-model-invocation: true` are now excluded from auto skill summaries, auto matching, and normal model prompt exposure while remaining available through explicit user invocation flows.
- External skills now become a more reliable execution lane instead of just passive prompt candidates:
  - when exactly one eligible non-builtin external skill clearly matches the turn, Kabot now promotes it into `forced_skill_names`, routes the turn through the agent loop, and injects an explicit execution note to follow that skill first,
  - when a skill is already explicitly forced/requested, the context builder now skips auto-matching extra skills on top of it, keeping the prompt closer to a single-skill OpenClaw-style execution contract.
- External-skill setup continuity is now more honest and more actionable:
  - when exactly one non-builtin external skill is the clear best match but it is not yet executable, Kabot now still locks onto that skill as the active lane instead of silently dropping back to generic behavior,
  - the runtime now injects a dedicated setup note with concrete blockers like missing CLI tools or env vars, so replies can tell the user the next real prerequisite to fix,
  - this makes public skills that are installed but not fully ready behave more like a guided setup lane rather than a failed match.
- Substantive new requests now break stale assistant-offer continuity more reliably:
  - turns like `cek saldo futures binance sekarang` and `cek harga btc sekarang` are now treated as fresh requests instead of accidentally inheriting an older assistant offer,
  - this closes a real replay bug where an installed external finance skill session could still drift into unrelated `find_files` follow-up logic from a previous turn.
- Public skill-catalog flow is now closer to a registry-style experience:
  - Kabot now supports `kabot skills search <query>`, `kabot skills info <slug>`, and `kabot skills install <slug>` with `--catalog-source` pointing to the builtin starter catalog, a local JSON file, or a JSON URL,
  - catalog entries can resolve to `git`, local `path`, or remote bundle `url` install specs, so public-skill installs no longer have to start from raw `--git` / `--path` arguments,
  - `kabot skills install` also now accepts `--url` directly for `.skill` / `.zip` archives from any host,
  - Kabot now records installs in lockfiles and supports `kabot skills list` plus `kabot skills update <slug>|--all`, making external/public skills behave more like a reusable registry install instead of a one-shot copy,
  - Kabot now also supports `kabot skills pack`, `kabot skills publish`, and `kabot skills sync` for a generic local JSON-catalog workflow, so skills can be bundled, shared, and re-indexed without depending on a specific website domain,
  - `skills publish` emits versioned `.skill` bundles plus catalog entries, while `skills sync` scans local roots and skips invalid skill folders instead of aborting the entire batch,
  - workspace installs are tracked in `<workspace>/.kabot/skills-lock.json` while managed installs are tracked in `~/.kabot/skills-lock.json`,
  - this keeps Kabot aligned with a source-agnostic public skill flow while keeping local `.skill` / `.zip` bundles and unpacked folders fully supported.
- Built-in finance tools are now explicitly archived as legacy fallbacks:
  - `stock`, `crypto`, and `stock_analysis` are now documented and described as legacy built-in fallbacks rather than the preferred first stop,
  - Kabot's public docs now steer users toward workspace/managed finance skills first, with the built-ins preserved for exact identifier lookups and compatibility.
- OpenClaw-style external skill intake is broader now:
  - `kabot skills install` now accepts `--path` for local skill folders and packaged `.skill` / `.zip` bundles, not just `--git`,
  - local installs reuse the same copy + validation flow as git installs, so shared skills can come from downloads or external catalogs without manual copying,
  - external skills that declare metadata under `metadata.openclaw` are now accepted by Kabot's skill loader alongside `metadata.kabot`.
- Skill-first finance routing is stronger:
  - when an eligible non-builtin external skill clearly matches a finance request, built-in `stock`, `stock_analysis`, and `crypto` tools are now treated as fallback instead of being forced immediately,
  - finance-oriented external skills now match better without relying on explicit ticker-parser wins first, which keeps the runtime closer to a skill-first external pack model.
- Telegram now has a first-step preview lifecycle closer to a draft-driven chat flow:
  - `draft_update` and `reasoning_update` no longer reuse the same mutable bubble as `status_update`,
  - Telegram keeps a dedicated preview message for partial answer text, separate from the queued/thinking status bubble,
  - when the final reply is a simple text response, Kabot now edits that existing preview into the final message instead of always deleting interim state and sending a brand-new message,
  - when preview materialization is not possible (for example media-only delivery), stale preview bubbles are cleaned up before the final result is sent.
- Knowledge-first and tool-demotion routing are now more grounded:
  - educational prompts like `explain Earth` or `tell me everything you know about Earth` no longer get mistaken for live web research just because words like `know` accidentally contain a live-search marker such as `now`,
  - after a search tool returns a setup-hint, follow-ups like `just explain`, `use English`, and `don't use web search` now explicitly break out of the stale `web_search` latch and route back to a normal model answer,
  - skill-creation continuity is now more semantic, so follow-ups like `struktur skillsnya gimana`, `flow skillnya gimana`, and `template skillnya dong` stay attached to the active skill-creation workflow instead of drifting into generic chat.
- The built-in `skill-creator` scaffolding is now closer to a full skill package lifecycle:
  - new skills created via `scripts/init_skill.py` now scaffold `assets/` alongside `SKILL.md`, `references/`, and `scripts/`,
  - scaffolded `SKILL.md` files now include top-level `name` and `description` frontmatter plus explicit sections for references, scripts, and assets,
  - the skill now ships `scripts/quick_validate.py` for lightweight structure/frontmatter validation and `scripts/package_skill.py` for bundling portable `.skill` archives,
  - skill-creator guidance now explicitly teaches when to use `assets/`, how to validate a skill, and how to package it for sharing.
- Hybrid memory retrieval is now properly end-to-end instead of silently dropping valid facts during reranking:
  - remembered facts written through the Chroma + SQLite + BM25 stack now keep their fused retrieval score all the way into the reranker,
  - fused candidate scores are normalized before reranking, so the reranker threshold no longer wipes out legitimate matches just because raw reciprocal-rank-fusion scores are numerically tiny,
  - this fixes cases where memory subprocesses, embeddings, and BM25 indexing were all working, but `search_memory(...)` still returned no results for facts that had just been remembered.
- Personal-memory recall is now more grounded and less echo-prone:
  - explicit recall turns like `what do you remember about me` / `apa yang kamu ingat tentang saya` now prioritize stable conversational profile facts before generic hybrid-search matches,
  - user-profile facts such as preferred form of address are injected into memory-recall context in a structured way,
  - recall no longer surfaces the user's own memory-recall prompt as if that were the remembered fact.
- Conversational identity/profile memory is now much more grounded:
  - turns like `call me ...` / `panggil aku ...` now persist a lightweight user profile into session metadata and `USER.md` instead of getting lost in generic chat flow,
  - self-identity follow-ups like `who am I?` / `siapa aku?` can now reply directly from that stored profile,
  - explicit memory-save turns no longer collide with `get_process_memory`, so prompts like `tolong simpan di memori` route to `save_memory` while process/RAM inspection prompts still go to `get_process_memory`,
  - bootstrap onboarding now respects persisted user profile fields too, so `USER.md` is no longer overwritten back to blank values after a successful conversational preference update.
- Deterministic memory writes stay grounded but now answer more naturally:
  - `save_memory` still executes through the deterministic direct-tool path,
  - but its user-facing response is now summarized by the model instead of exposing raw tool text like `[OK] preference saved ...`,
  - this keeps the runtime evidence-backed while making chat flow feel closer to a natural assistant.
- Telegram command parity is now much closer to a skill-first workspace model:
  - command-surface merging for Telegram now flows through a shared command-surface builder instead of duplicating static/router/skill merge logic inside the channel itself,
  - Telegram channels now receive the live `CommandRouter` and active `AgentLoop` from gateway runtime instead of only static channel config,
  - slash command handling no longer stops at `/start`, `/reset`, and `/help`; registered router commands now execute through a generic Telegram command handler,
  - workspace skills now surface as Telegram slash commands too, so commands like `/cek_runtime_vps` can appear in the bot menu and route into the agent as skill-first requests,
  - `/help` now lists workspace skill commands without hiding them behind the full merged command menu,
  - Telegram command registration now normalizes router command names into Telegram-safe slash commands, keeps menu ordering stable, and can still include workspace skills even when no router commands are present,
  - Telegram command sync now caches the last successful command-menu hash and skips redundant `set_my_commands` calls on restart,
  - when Telegram rejects a command payload with `BOT_COMMANDS_TOO_MUCH`, Kabot now retries with a smaller capped menu instead of failing hard on the first attempt.
- Built-in `/help` is now more registry-driven too:
  - when command help runs with an active agent/workspace, it now formats a merged command surface from router commands plus workspace skill commands instead of showing router commands alone,
  - help output now keeps admin-only command hints visible and separates skill commands into their own section,
  - this makes non-Telegram help output closer to the same command surface Telegram sees.
- Dashboard/gateway status payloads now expose the same merged command surface too:
  - dashboard status now includes a serializable `command_surface` snapshot built from static commands, router commands, and workspace skill commands,
  - this keeps dashboard UI consumers aligned with the same command registry shape used by Telegram menus and built-in `/help`,
  - command-surface dashboard helpers are now re-exported through `kabot.cli.commands` like the other dashboard helper seams,
  - the gateway dashboard now renders a dedicated `Commands` panel from that merged surface, so the operator UI can inspect the same slash-command registry seen by Telegram and `/help`.
- Follow-up continuity is less sticky around stale update flows:
  - parser-resolved tool requests like `periksa status server sekarang` now replace stale pending update follow-up state instead of inheriting the older `check_update` context,
  - assistant-offer follow-ups can now infer concrete runtime checks such as process inspection from the promised offer context when a concrete request was captured,
  - generic chat offers no longer over-escalate into action/tool flows just because the assistant sentence contains vague verbs like `kasih` or time phrases such as `60 seconds`,
  - natural Indonesian process-inspection prompts such as `cek langsung proses yang paling makan CPU/RAM` and `cek proses teratas yang makan resource` now resolve to `get_process_memory` instead of falling through to generic chat or manual command suggestions.
- Skill prompting is now more OpenClaw-style and less parser-heavy:
  - ordinary auto-matched skills are no longer injected into the prompt as full `SKILL.md` bodies,
  - Kabot now exposes an English summary-first `## Skills (mandatory)` block with `<available_skills>` entries and asks the model to read one `SKILL.md` only when it clearly applies,
  - explicitly forced/requested skills still load their full body so grounded workflows like weather and skill-creation follow-ups stay stable,
  - this reduces prompt bloat and shifts more skill selection toward the model instead of hard-coded parser paths.
- Bootstrap onboarding now behaves much more like a workspace-driven first-run ritual instead of a static reminder:
  - fresh workspace templates now use more persona-driven `SOUL.md`, `IDENTITY.md`, `USER.md`, and `BOOTSTRAP.md` text inspired by a more natural onboarding flow,
  - fresh workspaces now also seed `TOOLS.md`, so local environment-specific notes are first-class workspace memory instead of an optional manual file,
  - fresh workspaces now derive a stable per-workspace `starter spark`, so different installs/workspaces begin with slightly different default personality hints instead of every new bot sounding identical,
  - that starter spark is deterministic for the same workspace path, so reinstalling or reseeding the same workspace does not randomly rewrite the bot's initial character,
  - legacy workspaces now backfill missing bootstrap files like `IDENTITY.md` the moment `ContextBuilder` opens the workspace, so older installs no longer stay stuck on pre-parity file layouts,
  - `SOUL.md`, `IDENTITY.md`, `USER.md`, and `TOOLS.md` now load as a high-priority `Workspace Persona & Local Truth` block before generic profile guidance,
  - that high-priority workspace block now survives even compact/probe prompts, while bulky supplemental files like `AGENTS.md` and `BOOTSTRAP.md` stay out of compact mode,
  - this makes workspace-defined tone, user identity, and local aliases influence the assistant more directly instead of competing with generic defaults later in the prompt,
  - first-run onboarding answers can now be captured across multiple chat turns and persisted into `IDENTITY.md` and `USER.md`,
  - permissive onboarding parsing now accepts numbered answers and labeled free text such as `Nama saya: ...` or `Timezone: WIB`,
  - once minimum onboarding details are complete, `BOOTSTRAP.md` is automatically removed so the workspace stops behaving like a fresh agent on later turns,
  - bootstrap persistence stores partial progress in session metadata, so identity questions and later user-profile questions can complete across multiple replies instead of needing a single rigid form.
- Conversation tone and skill-authoring guidance are less stiff:
  - the default CHAT profile now pushes harder toward grounded, specific, human-sounding replies instead of template-heavy helper phrasing,
  - the built-in `skill-creator` skill now favors natural discovery and concise planning language instead of exposing rigid internal phase labels to the user.
- Fresh workspaces now support bootstrap-style onboarding context:
  - workspace template generation now seeds `IDENTITY.md` and `BOOTSTRAP.md` alongside the existing bootstrap files,
  - bootstrap parity defaults/schema now treat those files as first-class workspace state,
  - context building now injects `BOOTSTRAP.md`, so onboarding guidance can actually steer `/start` and other first-run turns.
- Telegram startup and delivery are now more grounded:
  - when a workspace still has `BOOTSTRAP.md`, Telegram `/start` is forwarded into the normal agent lane instead of being swallowed by a static welcome, allowing workspace bootstrap instructions to drive first-run setup,
  - Telegram final text replies and document sends now honor `OutboundMessage.reply_to` through `reply_to_message_id`, so replies can attach to the exact triggering message instead of floating as generic chat posts.
- Web-search capability availability is now more explicit and grounded:
  - `web_search` no longer silently falls back to Google News RSS for broad non-news queries when all search-provider API keys are missing,
  - no-key fallback is now limited to clear news/live-news style searches, preserving useful RSS behavior for headlines while avoiding fake "general web search" coverage,
  - broader searches without Brave/Perplexity/Grok/Kimi credentials now return a concrete setup hint that points users to search API key configuration and suggests `web_fetch` for direct page retrieval,
  - when `web_search` is invoked through the normal LLM tool-call loop and returns a provider/setup hint, runtime now passes that hint straight back to the user instead of letting the model improvise an unsupported answer from memory.
- Chat-level exec approvals no longer depend on legacy slash approval turns:
  - pending shell approvals now prompt users to confirm naturally in conversation, such as `ya jalankan sekarang` or `jangan jalankan`,
  - message runtime now resolves pending exec approvals from the current session's chat turn instead of requiring a slash command handshake,
  - the legacy pending approval queue and firewall stay in place for safety/audit, but the conversational UX no longer loops on slash-command approval retries.
- Weather follow-up continuity is more robust for forecast-style turns:
  - short follow-ups like `prediksi 3-6 jam ke depan` now stay attached to the last clean weather location instead of degrading into a location-less chat reply,
  - weather follow-ups grounded to an existing weather context now override competing parser latches such as `cron`, so phrases like `prediksi 3-6 jam kedepan` no longer create reminder jobs by mistake,
  - Open-Meteo-backed hourly forecast execution is now available for near-term requests, and short repeats like `prediksi` reuse the grounded weather context instead of falling back to current-weather-only output,
  - weather location extraction now rejects forecast-only phrasing such as `prediksi 3-6 jam ke depan` as a fake place name,
  - weather turns now force-load the `weather` skill into context and bypass the skill-skipping fast path so grounded location/forecast rules actually reach the model.
- The built-in `weather` skill is now aligned around Open-Meteo as the primary source:
  - the skill guide now follows a richer operational structure with explicit when-to-use, not-to-use, location-grounding, primary/fallback provider guidance, and quick response rules,
  - the skill guide now also includes response templates for current weather, rain/next-hours, daily forecast, and missing-location prompts so weather answers stay compact and grounded,
  - Open-Meteo is now documented as the default source for current conditions and forecasts, while `wttr.in` is framed as a fallback / quick-readable output path,
  - the weather tool description shown to the model/runtime now also states that Open-Meteo is the primary source with `wttr.in` fallback.
- Stock routing now avoids Meta Threads/API false positives:
  - queries about `Meta Threads` integration/API setup no longer collapse into the `META` stock ticker path unless the user is clearly asking about the market symbol.
- Skill/runtime continuity is more explicit:
  - `forced_skill_names` are now loaded into prompts as requested skill content instead of only being recorded in turn metadata,
  - server runtime prompts like `status server gimana` and `status server vps kabot` now stay pinned to `server_monitor` when that tool is available,
  - the default `AgentLoop` tool registry now actually includes `server_monitor`, so real agent runs no longer lose runtime-status prompts to live-research `web_search` fallback just because the tool was absent from the registry,
  - short confirmations after an assistant-committed server-status action now reuse the committed request text to infer `server_monitor` instead of falling back to generic chat,
  - active skill-creation workflows now stay latched on substantive discovery answers such as numbered scope replies, so the agent can move on to planning instead of restarting discovery from the top,
  - once a skill workflow is already in `approved`, later short follow-ups like `lanjut` keep that approved state instead of falling back to a pre-approval planning note,
  - after a skill has already been created and the assistant offers to use it, follow-ups like `lanjut pakai skillnya`, `lanjut`, or even short shorthand like `lanj` now pivot out of `skill-creator`, force-load the just-created skill from the recent `skills/.../SKILL.md` path, and clear the stale creation latch for that turn,
  - ultra-short referential follow-ups like `apa itu` now resolve against the latest assistant answer when recent context is available, instead of dropping into a generic literal-definition turn.
- Real workflow smoke coverage now also guards server-status follow-ups:
  - the smoke matrix includes a multi-turn `status server gimana -> ya cek status server sekarang` transcript,
  - this catches regressions where server-status prompts accidentally fall back to `Results for:` web search output or generic `I couldn't verify completion...` non-execution responses.
- Real workflow smoke coverage now also guards weather forecast follow-ups:
  - the smoke matrix includes a multi-turn `cuaca cilacap -> interpret suhu -> prediksi 3-6 jam -> prediksi` transcript,
  - this catches regressions where forecast follow-ups degrade into answer-reference chat text, current-weather fallbacks, or accidental cron job creation.

## [0.6.3] - 2026-03-12

### Added
- **Python-Native MCP Foundation**:
  - Added a new typed `mcp` config section to the root schema so Kabot can describe MCP servers natively without routing everything through a skill prompt.
  - Added an initial `kabot.mcp` package scaffold with:
    - immutable MCP server definitions,
    - a namespaced MCP capability registry using `mcp.<server>.<tool>` names,
    - a session-scoped runtime skeleton for attached MCP servers,
    - transcript-safe synthetic error result helpers for future MCP repair logic,
    - real Python MCP transport wrappers for `stdio` and `streamable_http`,
    - a tool adapter plus registry bridge so MCP tools can be exported into Kabot's `ToolRegistry` without auto-enabling them in the main loop yet.
  - Added session-bound MCP runtime state helpers so each Kabot conversation can resolve the correct MCP transport set without leaking tool execution across sessions.
  - Added gated `AgentLoop` wiring for MCP so enabled sessions can:
    - attach configured MCP servers,
    - discover namespaced MCP tools,
    - expose those tools to the model only when the session actually has MCP enabled,
    - execute MCP tool calls through session-local runtime binding instead of global mutable state.
  - Added a real Python stdio MCP end-to-end test using a tiny local `FastMCP` server, plus `AgentLoop` integration coverage proving explicit MCP tool-use prompts reach the LLM/tool loop without forcing ordinary chat turns into tool mode.
  - Added implementation and design docs for the full-Python MCP direction:
    - `docs/plans/2026-03-11-kabot-python-mcp-design.md`
    - `docs/plans/2026-03-11-kabot-python-mcp-implementation.md`
  - Added a user-facing `kabot mcp` CLI surface with:
    - `kabot mcp status`
    - `kabot mcp example-config`
    - `kabot mcp inspect <server>` for live MCP capability inspection
  - Added `doctor smoke-agent --smoke-mcp-local-echo` plus a local Python MCP echo smoke case for end-to-end MCP validation without npm.
  - Extended the Python-native MCP runtime with real `resources` and `prompts` support:
    - stdio and streamable HTTP transports can now list resources, read resource contents, list prompts, and fetch prompt payloads through the official Python MCP SDK,
    - session-scoped MCP runtimes now normalize those capabilities into typed descriptors instead of keeping them as raw SDK objects,
    - real stdio end-to-end coverage now verifies a local Python MCP server can expose tools, resources, and prompts together through Kabot's runtime.
  - Added explicit MCP prompt/resource context support for the agent:
    - users can now explicitly refer to an MCP prompt or resource and have Kabot pull that context into the current turn without forcing a tool call,
    - MCP capability snapshots and prompt/resource fetches are now cached per session runtime to avoid repeated round-trips for the same server during a conversation.
  - Added lean-context handling for explicit MCP prompt/resource turns:
    - explicit MCP context now tells the context builder to skip expensive auto-skill discovery and bulky memory blocks when the user already supplied the exact MCP prompt/resource they want Kabot to use,
    - MCP explicit turns still keep their explicit context note and normal chat behavior, but no longer pay the full GENERAL prompt assembly cost by default.

### Changed
- Large runtime entry files are now slimmer without changing the tested routing/runtime behavior:
  - `message_runtime.py` is now a small facade over the extracted `process_flow` runtime, which keeps monkeypatch-sensitive globals synchronized while cutting the entry file down to a small orchestration surface,
  - `execution_runtime.py` is now a matching facade over the extracted agent-loop runtime, with the same compatibility treatment for patched globals used in tests,
  - `execution_runtime_parts/helpers.py` was split into grouped `artifacts`, `intent`, `observability`, and `persistence` modules,
  - `execution_runtime_parts/agent_loop.py` is now below 1000 lines after extracting the status/draft/reasoning/interruption runtime into `progress.py` and moving `process_tool_calls(...)` into `tool_processing.py`,
  - the execution runtime facade now syncs monkeypatched translator/logger globals into the extracted progress and tool-processing modules too, so existing compatibility tests keep working after the split,
  - `message_runtime_parts/helpers.py` now delegates extracted answer-reference and context-note logic into smaller modules instead of keeping all continuity helpers in one large file,
  - `message_runtime_parts/process_flow.py` is now down to 1255 lines after extracting answer-reference/offer-follow-up continuity handling into `continuity_runtime.py` and moving final turn metadata assembly into `turn_metadata.py`, while keeping the same stateful follow-up contract for short confirmations, committed actions, answer-reference turns, and runtime metadata fields,
  - the message runtime facade now also syncs monkeypatch-sensitive logger globals into the extracted `continuity_runtime` module so compatibility tests keep seeing the same patched logging surface after the split,
  - `tool_enforcement_parts/core.py` is now down to 641 lines after extracting shared regex/common helpers, filesystem path resolution, action-request parsing, history-driven routing, and fallback-support utilities into dedicated modules,
  - the split `tool_enforcement` core now re-exports the same helper contract the wrapper expects, so deterministic fallback paths like `write_file`, `message/archive_path`, and cron management keep their prior behavior while the code is easier to audit,
  - `tool_enforcement.py` is now a 172-line facade that re-exports the extracted helpers and keeps only monkeypatch-sensitive compatibility sync for `_filesystem_home_dir`-driven wrappers plus the deterministic fallback entrypoint,
  - wrapper compatibility now includes a focused regression test proving `_extract_message_delivery_path(...)` still respects a monkeypatched facade home directory after the split,
  - delivery-path parsing now strips channel-delivery tails such as `ke chat ini` / `chat here` before relative-directory fallback runs, which prevents requests like `kirim folder desktop ke chat ini` from hallucinating `Desktop/kirim` or `Desktop/desktop ke chat ini`,
  - `tool_enforcement.py` now keeps only the monkeypatch-sensitive compatibility layer locally while reusing canonical multilingual filesystem regexes from the extracted core module, which fixed mojibake regressions for `æ¡Œé¢` / `ãƒ‡ã‚¹ã‚¯ãƒˆãƒƒãƒ—` / `à¹€à¸”à¸ªà¸à¹Œà¸—à¹‡à¸­à¸›` follow-ups,
  - direct `list_dir` execution now records the requested directory path itself as follow-up context instead of accidentally reusing the first listed file, which fixes multilingual folder-navigation smoke flows such as `æ˜¾ç¤ºæ¡Œé¢æ–‡ä»¶å¤¹å†…å®¹ -> è¡¨ç¤º ãƒ•ã‚©ãƒ«ãƒ€ bot`.
  - filesystem path extraction no longer treats slash-separated control hints like `↑/↓` as real filesystem paths, so game-upgrade follow-ups stop hallucinating `read_file` targets such as `/↓`,
  - explicit file-analysis mode now only extracts file paths from the user's raw turn instead of synthetic `[Committed Action Context]` / `[Assistant Promise]` sections, which prevents short follow-ups like `yes continue` from being hijacked into stale `read_file` flows just because the assistant promise mentioned filenames.

- Continuity parity is now much more explicit and observable across the runtime:
  - message routing now records a first-class `turn_category` (`chat`, `action`, `contextual_action`, `command`) instead of leaving short follow-ups to weak parser guesses,
  - durable session snapshots now backstop history hydration across normal, isolated, slash, and system-origin turns so recent context survives fresh loop instances and fail-open history gaps,
  - layered context assembly now gives bounded priority to recent history, recent answer/tool context, saved memory facts, and learned execution hints before weaker fallback heuristics,
  - long-running execution can now detect pending same-session user messages, inject a compact interruption note, and send a real intermediate acknowledgment through the message lane,
  - completion is now governed by unified evidence metadata (`completion_evidence`) so direct create/find/generate/send paths must have real artifact and delivery proof instead of trusting plain-text success claims,
  - smoke and dashboard observability now expose `turn_category`, continuity source, pending interrupt count, and completion evidence so parity/debug work can be validated from runtime output instead of inference alone.
- `KABOT_CONFIG` now overrides the default config path, which lets MCP smoke runs and isolated CLI sessions use temporary config files safely while preserving the active base config.
- Filesystem search and same-channel file delivery are now more reliable for explicit local-file requests:
  - added a generic `find_files` tool for file/folder lookup before read/send actions,
  - explicit `kirim file ... ke chat ini` requests now prefer real existing relative paths from the current working directory before falling back to the agent workspace path,
  - bare filenames can inherit the last resolved path from a prior `find_files` step, so `find -> send` flows stop re-failing on `File not found`,
  - natural phrases such as `folder kerja saat ini`, `current folder`, and `working directory` now resolve to the current process directory during deterministic filesystem search.
- Multi-step `find -> send` file requests now have a deterministic workflow lane:
  - turns like `cari file report.pdf lalu kirim ke chat ini` can execute `find_files` first, capture the resolved absolute path, and immediately hand off to `message`,
  - guarded tool-call validation now allows the right workflow tools (`find_files`, `message`) for delivery-backed file requests instead of blocking them behind stale single-tool expectations such as `read_file`,
  - if delivery still cannot be proven, Kabot keeps failing honestly instead of claiming the file was sent.
- Create/generate-and-send artifact requests now stay AI-driven instead of collapsing into the wrong send-first path:
  - prompts like `buat file ... lalu kirim ke chat ini` now prefer `write_file` first, with delivery enforced afterward, instead of jumping straight to `message`,
  - prompts like `generate gambar ... lalu kirim ke chat ini` now keep `image_gen` as the primary execution tool while still marking delivery as required when the user explicitly asks to send the result.
- Delivery recovery is now less hardcoded to built-in tools:
  - direct deterministic lanes can send freshly created files and generated images immediately after `write_file` or `image_gen` succeeds,
  - runtime can now reuse any captured local result path from prior tool execution, not only `find_files`/`write_file`/`image_gen`, which makes future MCP media tools and custom artifact generators easier to deliver through the same `message(files=...)` path,
  - generic artifact-path extraction now understands structured tool results (`dict`/`list`/JSON strings) and relative output paths such as `outputs/promo.mp4`, which makes MCP/video/audio-style tools much less likely to lose their delivery target just because they returned metadata instead of a plain sentence,
  - artifact-path extraction now also reads output paths embedded inside `exec` command arguments such as Playwright `page.screenshot(path=...)`, which gives screenshot/video shell workflows a real delivery target instead of losing the file after the command succeeds,
  - `find_files -> message` delivery now keeps working even when search returns multiple matches by carrying forward the primary resolved path instead of falling back to the raw file list,
  - real CLI smoke now confirms `create -> send`, `find -> send`, and honest `generate -> send` blocker paths through the new `--delivery-cases` matrix instead of relying only on unit tests.
- Command approval flow is now durable across CLI/agent process restarts:
  - pending `exec` approvals are now persisted on disk instead of living only in one in-memory `ExecTool` instance,
  - persisted approval IDs can now resolve the queued command from a fresh agent process, which fixes loops where users had already sent the approval turn but Kabot responded with `No matching pending command approval found.`,
  - real CLI verification now succeeds end-to-end for a persisted approval followed by a fresh approval turn in a new agent process.
- Follow-up continuity is now more AI-first across generic tools, not only parser-known domains:
  - short follow-ups can reuse the most recent real tool execution context (`last_tool_execution`) as a continuation source,
  - MCP tool follow-ups can continue even before the tool name is re-derived from keyword parsers or eagerly present in the base tool registry,
  - explicit fresh requests still break continuity so file/config/path turns do not inherit stale tool execution state.
- Low-information continuity resolution now prefers richer conversational evidence before weak parser guesses:
  - recent answer references can clear parser-selected tools when the user is clearly referring to the last assistant answer,
  - recent tool execution now outranks older user intent for vague follow-ups like `cek lagi dong`,
  - recent user intent can now outrank weak direct-tool guesses like `update dong` when the current turn carries no real tool payload,
  - fast direct-tool routing now still loads recent history for continuity-worthy follow-ups instead of skipping memory too early.
- Follow-up continuity now emits a debuggable `continuity_source` across runtime metadata and smoke-friendly logs:
  - message runtime metadata now records whether the current turn was grounded by `parser`, `answer_reference`, `tool_execution`, `user_intent`, or a stronger session continuity path,
  - low-information contextual follow-ups such as `kalau untuk bepergian bagaimana` can now stay attached to the recent assistant answer topic instead of being treated as a brand-new generic question,
  - runtime observability events and plain logs now include the resolved continuity source so field debugging no longer has to infer why a follow-up continued or reset.
- Referential option follow-ups in real CLI sessions now stay grounded across more multilingual forms:
  - compact Chinese and Thai ordinal clarifications such as `ç¬¬äºŒä¸ªæ˜¯ä»€ä¹ˆï¼Ÿç®€çŸ­å›žç­”ã€‚` and `à¸‚à¹‰à¸­à¸—à¸µà¹ˆà¸ªà¸­à¸‡à¸„à¸·à¸­à¸­à¸°à¹„à¸£ à¸•à¸­à¸šà¸ªà¸±à¹‰à¸™à¹†` now resolve as answer-reference continuity instead of losing context and asking the user to resend the list,
  - option-reference extraction now tolerates short referential questions in unsegmented scripts without weakening path/URL payload guards for genuinely new requests,
  - answer-reference turns now ignore stale non-offer pending intent context and can inject the exact referenced item from the previous assistant answer, reducing cases where the model repeated the whole list or drifted back to the original tool request,
  - highly grounded answer-reference turns can now short-circuit to a direct fast reply when the exact referent is already known, so replies like `ç¬¬äºŒä¸ªæ˜¯ä»€ä¹ˆï¼Ÿ`, `à¸‚à¹‰à¸­à¸—à¸µà¹ˆà¸ªà¸­à¸‡à¸„à¸·à¸­à¸­à¸°à¹„à¸£`, and `ãã‚Œã£ã¦ã©ã†ã„ã†æ„å‘³ï¼Ÿ` stay anchored to the previous answer instead of inventing a fresh interpretation.
- Filesystem follow-up fallback is now less hallucination-prone when an answer-reference is already stronger:
  - `list_dir` fallback no longer overrides a recent-assistant-answer reference for short multilingual referential turns,
  - Thai follow-ups that point to a numbered item from a previous directory listing now stay on the selected item instead of re-running the directory listing because a stale path fallback looked plausible.
- `kabot.cli.agent_smoke_matrix` now supports multi-turn continuity smoke coverage:
  - smoke cases can run follow-up prompts in the same session and assert the final `continuity_source`,
  - added multilingual non-finance continuity cases plus an MCP local-echo follow-up continuity case,
  - workflow smoke can now cover create/continue/upgrade transcripts such as the ping-pong web game regression, and forbidden output markers like `File not found: /↓` are checked across the whole transcript instead of only the last turn.
  - new `--continuity-cases` flag makes those extra follow-up smoke scenarios opt-in for focused audits,
  - continuity smoke cases can now assert positive and forbidden output fragments, which catches semantic regressions where the runtime keeps the right `continuity_source` but the final answer still repeats the wrong list items or explains the user's follow-up phrase instead of the referenced result.
- Dashboard runtime status now exposes the latest continuity/routing snapshot:
  - dashboard payloads include a `recent_turn` summary with session key, continuity source, routing profile, and required-tool hints,
  - the runtime page renders that snapshot above the raw JSON payload so field debugging no longer requires opening logs first.
- Runtime meta-feedback detection now matches full markers instead of loose substrings, so natural turns like `cek lagi dong` no longer get misclassified as `lag/slow` complaints and blocked from continuity reuse.
- Explicit MCP prompt/resource references now outrank generic file-analysis heuristics, so URIs like `memory://field-guide` are treated as MCP resources when the user clearly says `resource ... dari server ...` instead of being hijacked as ordinary file-path analysis.
- Explicit MCP prompt/resource turns now pass a dedicated `mcp_context_mode` budget hint into the context builder, allowing lean GENERAL prompt assembly without pretending the turn is a generic low-information probe.
- Answer-reference continuity now suppresses stale non-offer pending intent context once the runtime has already grounded the turn on the latest assistant answer, preventing cases where referential multilingual follow-ups were still contaminated by old tool/file continuation text during broad suite execution.
- Assistant follow-up continuity now also captures committed action promises such as `aku akan buat file...` or `saya akan kirim hasilnya`, so short confirmations like `lanjut` and `ya lakukan` stay attached to the promised task instead of being hijacked by stale reminder/system/tool continuity from earlier turns.
- Committed-action continuity is now a first-class runtime lane instead of being treated like a generic assistant offer:
  - promise-style assistant replies now persist as `assistant_committed_action` with the originating user request text, not just the promise sentence itself,
  - low-information approvals such as `ya`, `buat sekarang`, `lanjutkan`, and similar follow-ups now prioritize that committed action over stale parser guesses or older tool execution,
  - committed-action follow-ups are forced onto the agent/tool loop with explicit grounding notes so the model is pushed to actually perform the promised work instead of paraphrasing it or claiming completion without evidence.
- Generic side-effect and artifact-generation requests are now escalated into the agent loop earlier, even when no deterministic parser tool matches:
  - requests to create, generate, export, send, or save files/media/artifacts now avoid the shallow simple-chat lane,
  - media-generation turns mentioning providers such as `Imagen` or `Nanobanana` now stay in AI-driven execution mode instead of being treated as ordinary advice/chat turns,
  - this hardening applies broadly across file creation, image/video generation, and other tool-or-skill-backed output tasks rather than only finance or weather follow-ups.
- Coding/build follow-ups are now less likely to drift into generic chat or wrong-tool blockers:
  - concrete build requests like `bikin landing page ...` can now promote the route into `CODING` even when no single deterministic tool is obvious yet,
  - short confirmations of committed coding work such as `YA` after `aku akan bikin landing page ...` now stay in a coding execution lane instead of being hijacked by stale generic follow-up context,
  - guarded tool validation now allows normal coding workflow tools like `read_file`, `list_dir`, `write_file`, `edit_file`, and `exec` during coding execution continuity instead of blocking them for lacking explicit lexical payload in short follow-up turns.
- Natural delivery shorthand is now recognized more often in multilingual chat:
  - phrases like `ss kirim sini`, `ke sini`, `kesini`, and `di sini` now count as real delivery intent when the turn already contains a file/media artifact subject,
  - coding/media requests that use that shorthand now mark `requires_message_delivery` earlier, so Kabot keeps pushing toward real send evidence instead of stopping at a local path or guessed completion text.
- Action-backed generation/file requests now resolve to concrete execution tools more often instead of stopping at a generic â€œcomplexâ€ route:
  - side-effect turns with explicit writable file targets such as `.smoke_tmp/example.txt` can now infer `write_file` directly after weak parser guesses are cleared,
  - image-generation requests can now infer `image_gen` from natural prompts like `generate gambar ... pakai imagen`,
  - registered media/MCP tools can now be selected by provider/media hints (for example `nanobanana` + `video`) even when the user does not type the full `mcp.server.tool` alias.
- Deterministic action fallback is now stricter about evidence and better at simple artifact creation:
  - explicit relative-dot paths such as `.smoke_tmp/file.txt` are now preserved end-to-end instead of collapsing to the basename,
  - `write_file` fallback can now extract simple inline content like `berisi HALO_KABOT` and create the requested artifact without waiting for the model to improvise a tool call,
  - direct action tools like `write_file` and `image_gen` now update follow-up execution context immediately after execution, which keeps later confirmations grounded in real tool output.
- Real one-shot agent runs are now less likely to â€œhaluâ€ on file/media requests:
  - if a concrete action request maps to a supported tool, runtime can bypass the fragile text-only LLM step and execute it directly,
  - if image generation is requested but the configured provider is unavailable, Kabot now fails honestly with the provider/tool limitation instead of pretending the artifact already exists.
- Reminder routing is now less eager around schedule-as-document prompts:
  - requests like `buat file Excel jadwal lari 8 minggu` no longer get misclassified as cron/reminder intent just because they contain `jadwal` plus a duration,
  - assistant promises about creating schedule documents or spreadsheets now keep their continuity path, so real CLI turns like `lanjut` stay attached to the promised file task instead of falling into reminder-time parsing.
- General-knowledge chat is now less likely to be hijacked into stock fallback:
  - bare fact questions like `jam berapa`, `IQ manusia berapa`, and `EQ manusia berapa` no longer become fake company-name lookups just because they contain `berapa`,
  - stock name fallback is now more conservative for short all-caps tokens and generic multi-word phrases, so Kabot only forces stock tools when there is stronger market evidence instead of guessing from generic nouns.
- Quoted or pasted assistant context is now less likely to hijack unrelated tools:
  - long user turns that paste a previous answer and end with a new request now bias routing toward the trailing request instead of domain words inside the pasted block,
  - personal HR-zone calculations and memory-save requests with birth years no longer get forced into `web_search` just because they contain `sekarang` or a four-digit year,
  - weather routing is now more resistant to non-location phrases like `di atas 160 bpm`, and semantic arbitration can clear stale weather parsing when the actual request is a fitness/HR calculation.
- Conversation persistence and memory-backed continuity are now more durable across fast paths:
  - pending background memory writes are drained briefly before a new turn reads conversation history, which makes short follow-ups less likely to miss the immediately previous turn and fall back to stale parser/tool guesses,
  - one-shot/direct runtime cleanup now waits for queued memory writes instead of dropping them on shutdown, improving the odds that every user/assistant turn really lands in session memory,
  - slash-command replies now use the same session init/finalize persistence path as normal chat turns, so command interactions like `/status` also appear in conversation memory instead of bypassing it.
- System-origin chat callbacks now use the same memory-backed lifecycle as normal turns more often:
  - routed `system` messages (for example cron-style callbacks that target a real channel/chat) now enter the origin session through the normal init/finalize persistence path instead of only updating transient in-memory session history,
  - persisted system turns are annotated as `[System: ...] ...`, which keeps reminder/callback context visible to later follow-ups without pretending those messages came from a normal user turn,
  - real runtime verification now confirms those system-origin turns land in session memory and remain visible after resource cleanup.
- Contextual answer-reference follow-ups now beat stale tool/user continuation more often when the user is clearly elaborating on the assistant's latest answer:
  - natural prompts like `kalau untuk bepergian bagaimana` can now stay attached to the previous assistant weather answer instead of snapping back to the older raw weather tool intent,
  - stale non-offer pending follow-up state no longer blocks this grounded answer-reference path when the new turn is clearly asking `for X, how about it?`,
  - real CLI smoke now confirms this continuity path resolves as `answer_reference` instead of re-running `weather` for the wrong target.
- `kabot.cli.agent_smoke_matrix` now has official multilingual memory follow-up probes:
  - new `--memory-cases` runs explicit memory-save then recall flows across Indonesian, Chinese, and Thai prompts/follow-ups,
  - these smoke cases exercise fresh-process continuity on the same session ID so regressions where turns stop landing in usable memory become visible before field reports do.
- Short memory-recall turns are now less likely to pretend earlier context is unavailable:
  - explicit recall prompts like `what is my preference code?`, `kode preferensiku apa?`, and `æˆ‘åˆšæ‰è®©ä½ è®°ä½çš„ä»£ç æ˜¯ä»€ä¹ˆï¼Ÿ` now skip the fragile no-history fast lane and force enough context/history to answer from the current session,
  - router fast heuristics now keep those recall prompts in `GENERAL` instead of letting words like `code/ä»£ç /kode` promote them into accidental `CODING` classification.

## [0.6.2] - 2026-03-10

### Fixed
- **Ollama Provider Integration (#2)**:
  - Added dedicated `ollama` provider specification to the model registry to prevent local Ollama URLs from being incorrectly routed through the `vLLM` LiteLLM backend, which caused 404 Not Found errors on model lookups.
  - Fixed `ollama_url.py` auth handler to correctly use the `"ollama"` provider key instead of reusing `"vllm"`.
  - Added an auto-discovery plugin for Ollama models on startup, so models installed locally (`http://localhost:11434/api/tags`) automatically appear in the Kabot model list.

- **Chat Continuity Hardening**:
  - Short contextual follow-ups like `ya lanjut`, `lanjut rencana`, `yang formal gimana`, `trend nya naik?`, `naik ya`, and `kenapa` now prefer recent conversational context instead of being hijacked by stale tool history.
  - Assistant offer follow-ups now keep their pending offer context even when the runtime chooses the safer full-context lane, so numbered choices and brief confirmations stay connected to the previous answer.
  - Bare numeric replies and ordinal follow-ups such as `2`, `nomor 3`, `yang ketiga gimana`, and `lanjut yang tadi` now stay grounded to the latest assistant option prompt instead of echoing the number back or asking for context that was already present.
  - User-authored option prompts like `Kalau mau, aku bisa kasih 3 opsi...` are now treated as quoted choice prompts that require a follow-up selection, preventing Kabot from auto-picking an option on the user's behalf.
  - Multilingual quoted option prompts and selections now stay grounded across Chinese, Japanese, and Thai flows, so replies such as `ç¬¬äºŒä¸ª`, `2ç•ª`, and `à¸‚à¹‰à¸­ 2` keep following the last option prompt instead of resetting or asking for already-known context.
  - Assistant option blocks that use East Asian numbering styles such as `1ï¼‰` without spaces are now preserved as real option prompts, so multilingual numbered follow-ups no longer lose the choice list during continuity recovery.
  - Referential follow-ups such as `å†ç®€çŸ­ä¸€ç‚¹`, `è¿™æ˜¯ä»€ä¹ˆæ„æ€`, `ã‚‚ã£ã¨çŸ­ã`, `ãã‚Œã©ã†ã„ã†æ„å‘³`, `à¸ªà¸±à¹‰à¸™à¸à¸§à¹ˆà¸²à¸™à¸µà¹‰`, and `à¸«à¸¡à¸²à¸¢à¸„à¸§à¸²à¸¡à¸§à¹ˆà¸²à¹„à¸‡` now inherit the most recent assistant answer as explicit answer-reference context, letting Kabot shorten or explain the last reply instead of falling back to generic translation/help text.
  - Referential follow-ups can now keep the most recent assistant answer context even when an assistant-offer continuation is still pending, so turns like `ç¬¬äºŒä¸ª -> å†ç®€çŸ­ä¸€ç‚¹ -> è¿™æ˜¯ä»€ä¹ˆæ„æ€` stay on the same answer instead of asking the user to resend it.
  - Quoted option prompts now inject a stronger `User-Provided Option Prompt` note that tells the model the list came from the user and must not be auto-completed in-character, reducing cases where Kabot picked an option by itself in multilingual chats.
  - Short assistant-offer confirmations such as `ya`, `ya berikan`, and `ya lanjut` now inject an explicit acceptance note into the current turn so the model continues the promised answer instead of drifting into unrelated tools or topics.
  - Recent stock quote follow-ups can now promote into contextual stock analysis using the latest stock context instead of falling back to generic "need more context" replies.
  - Explicit stock trade-plan requests such as `Buatkan 3 skenario trading AAPL: breakout, pullback, invalidation` now resolve to `stock_analysis` instead of degrading into plain quote lookups.
  - Referential stock follow-ups like `lanjut yang tadi` now keep the prior analysis intent instead of snapping back to the last raw stock quote context.
  - Deterministic stock-analysis fallback now serializes `days` as a string to match the tool schema, fixing follow-up errors like `Invalid parameters for tool 'stock_analysis': days should be string`.
  - Short hostile meta feedback like `tolol` or `goblok jawab apa loh` now carries a feedback note that tells the model to acknowledge frustration briefly, avoid joking, and restate the last answer more directly instead of resetting or becoming flippant.
- **Weather Follow-up Accuracy**:
  - Explicit new weather locations now beat stale last-weather context, so turns like `suhu di purwokerto sekarang berapa` no longer reuse a previous city just because the prompt is short.
  - Weather location normalization now cleans `+`-joined text such as `Cilacap+Utara`, allowing fallback variants to reach Open-Meteo correctly before falling back to other providers.
  - Follow-up weather chats now stay grounded to the right city and source more consistently, with live smoke verification confirming `Source: Open-Meteo (current_weather)` for cases such as `cuaca cilacap utara sekarang berapa` and `berapa suhu di purwokerto`.

- **Weather Provider Priority**:
  - Weather resolution now tries all normalized location variants against Open-Meteo before accepting a `wttr.in` success, so queries like `cuaca cilacap utara sekarang berapa` no longer stop early on a less-preferred source when `Cilacap` already resolves correctly in Open-Meteo.
- **Skill Runtime Reliability**:
  - The bundled `github` skill now explicitly tells the model to use the shell/exec command tool for `gh ...` commands and not to hallucinate a standalone `gh` tool call, fixing multilingual smoke failures that previously tripped model fallback with `tool ... was not in request.tools`.
- **Smoke Harness Accuracy**:
  - `agent_smoke_matrix` now computes weekday expectations from the current `Asia/Jakarta` date instead of hardcoding Monday strings, making multilingual temporal smoke cases valid across real calendar days.
  - Smoke prompt text for Chinese, Japanese, and Thai is now stored with Unicode-safe escapes so CLI smoke runs no longer degrade into `????` prompts on Windows.
  - Smoke expectation matching is now case-insensitive and separator-tolerant, so healthy skill replies like `BlueBubbles` or `Test-Driven Development` are not falsely marked as failures just because the output uses title case or spaces instead of slug-style names.
  - Per-case subprocess timeouts are now captured as failed smoke results instead of aborting the entire matrix, so broad all-skill audits can finish and report the real outliers instead of crashing on the first slow skill.

## [0.6.1] - 2026-03-09

### Fixed
- **PyPI Runtime Packaging**:
  - Added missing runtime dependency `psutil` to package metadata so clean PyPI installs can execute `python -m kabot.cli.commands` without `ModuleNotFoundError`.
  - Verified the fix with a fresh virtual environment install from PyPI-style artifacts before cutting the patch release.

## [0.6.0] - 2026-03-09

### Added
- **Dashboard UI Improvements**:
  - Added fixed max-height and scrollbar to the **Runtime Details** panel.
  - Ensured all JSON previews are concise and scrollable to prevent page bloating.
- **Real-time System Metrics**:
  - Implemented `psutil` collection for CPU and RAM percentage.
  - Added `shutil.disk_usage` for real disk metrics (Windows/Linux/Mac).
  - Metrics bar now shows actual values, PID, memory usage, and OS info.
  - Alerts banner now triggers based on real high-usage thresholds (>90%).
- **Interactive Settings Panels**:
  - Replaced broken Tailwind settings UI with modern inline CSS components.
  - Added **Token Mode** toggle cards: "Verbose" (boros) and "Compact" (hemat).
  - Translated all settings UI to **English**.
  - Action buttons now in a grid with icons and descriptions.
  - Automatic success/error message clearing for a cleaner experience.

- **Dashboard Feature Parity**:
  - **6 Themes**: 3 dark (Midnight, Charcoal, Ocean) + 3 light (Snow, Cream, Mint) â€” switchable from header dropdown, persisted in localStorage.
  - **Top Metrics Bar**: Live CPU, RAM, disk usage with color-coded progress bars, gateway status badge, uptime counter, version display.
  - **Header Bar**: Bot logo, status dot with pulse animation, auto-refresh countdown (60s), theme picker.
  - **Alerts Banner**: Smart alerts for high CPU/RAM/disk (>90%), gateway offline status, custom alerts from `status_provider`.
  - **System Health Stat Cards**: 6 cards showing status, uptime, sessions, nodes, channels, cron jobs count.
  - **Cost & Usage Panel**: Today's cost, all-time cost, projected monthly, input/output token usage table.
  - **SVG Charts Panel**: Model usage bar chart generated from `status_provider` data.
  - **Channels Panel**: Channel name, type, state with colored badges.
  - **Cron Jobs Panel**: Job name, schedule, state, last/next run times.
  - **Available Models Grid**: Per-provider model listing with configured/available badges and tag-style model names.
  - **Skills List**: Registered skills with active/disabled state badges.
  - **Cron Operator Actions**: Cron panel now shows last status, duration, and inline `Run`, `Enable/Disable`, and `Delete` actions via HTMX partial refresh.
  - **Dashboard Action Buttons Fixed**: Replaced broken Tailwind CSS utility classes (`py-1`, `px-2`, `text-xs`, `bg-red-500`, `bg-slate-600`, `bg-emerald-500`, `mr-2`) with proper inline CSS styles â€” all action buttons across Sessions (Clear/Delete), Nodes (Restart/Stop/Start), Cron (Run/Enable-Disable/Delete), and Skills (Enable-Disable/Save Key) panels are now fully interactive and visually differentiated (accent/danger/success colors).
  - **Real-Time Uptime Counter**: Overview uptime stat card now ticks every second client-side (JS `setInterval`) instead of waiting for the 5-second panel refresh, matching the metrics bar responsiveness without extra HTTP requests.
  - **Skills Operator Actions**: Skills panel now shows env readiness, inline `Enable/Disable`, and `Save Key` actions for API-key based skills.
  - **Sub-Agent Activity Panel**: Added dashboard panel for recent subagent runs with status and duration snapshots.
  - **Git Log Panel**: Added dashboard panel for recent workspace commits.
  - **Expanded Cost/Chart Monitoring**: Cost panel now includes per-model breakdown, while charts can render both cost history and model usage from enriched status payloads.
  - **Dashboard Interaction Bug Fix**: Fixed a client-side JavaScript auto-refresh loop in `dashboard.html` that indiscriminately overwrote all elements with `.hx-get` attributes every 5 seconds, which previously broke interactivity for chart time filters (`7d`, `30d`, `all`) and prevented POST forms like the `sessions.delete` button from retaining state.
  - **Real Multi-Model Usage Accounting**: Dashboard cost panels now seed every active runtime model in the chain even before first usage, config/runtime summaries expose the full model chain, and transcript cost parsing now respects nested usage payloads plus explicit per-turn cost totals instead of assuming only one primary model path.
  - **Usage Window Tabs**: Cost and chart panels now support `7d`, `30d`, and `All Time` window switching with HTMX-persisted panel refresh, while runtime payloads expose pre-aggregated `usage_windows` so auto-refresh stays fast even as history grows.
  - **Sticky Chat UX**: Dashboard chat now restores the active tab after browser reload using URL-hash + local tab persistence, and chat logs auto-stick to the latest message after HTMX/SSE updates so operators do not need to scroll back down manually.
  - **Settings Panel Hardening**: Settings/engine wrapper panels now load with `outerHTML` placeholders to avoid duplicate HTMX targets, skill toggles follow the real config `disabled` flag instead of readiness state, and read-only tokens now surface explicit operator-write requirements instead of showing dead action buttons.
  - **Dashboard History Cleanup**: Chat history payloads preserve real metadata when present without injecting empty `metadata: {}` into every message.
  - **Operator Feedback UX**: Dashboard action results now render friendly success/error summaries with expandable JSON details, while `Sessions`, `Nodes`, and `Chat` also show consistent read-only notices and fully disable write inputs when the token lacks `operator.write`.
  - **Live Dashboard Performance Pass**: Dashboard snapshots are now cached briefly per burst so HTMX partials stop rebuilding expensive monitoring payloads on every request, the page refresh loop is centralized instead of every panel polling independently, the metrics bar updates once per second, and dashboard chat now fast-acks sends while SSE delivers the actual conversation stream.
  - **Responsive Design**: Mobile/tablet support with hamburger menu, collapsible sidebar, adaptive grid layouts.
  - **Auto-Refresh**: Countdown refresh now updates global bars plus the currently visible dashboard panels in place, so operators stay on the active tab instead of getting bounced back through a full page reload.
  - 9 new GET `/dashboard/partials/*` routes serving HTMX fragments.

### Fixed
- **Comprehensive Chat Model Tracking**: Resolved an issue causing Cost & Usage tracker panels on the dashboard to ignore model overrides (such as openrouter models or custom providers) used in the web chat. LLM responses returning native Pydantic objects or missing usage properties entirely are now safely parsed and tracked, ensuring that *all* models, including overrides and custom endpoints, correctly appear in model usage charts and cost aggregation.

### Added
- **Documentation**: Added comprehensive guide for Auto-start (background daemon) and Tailscale tunneling to `HOW_TO_USE.MD`, including native security middleware explanations and Windows troubleshooting.
- **Native Tailscale Security Middleware**: Kabot's Gateway now features an IP-level Tailnet middleware. When `gateway.tailscale` is enabled in the configuration, the `webhook_server` natively drops any incoming UI/Webhook connection (`403 Forbidden`) that does not originate from Localhost (`127.0.0.1`, `::1`) or the secure Tailscale subnet (`100.x.x.x`). This enforces a stricter tailnet-first security posture, ensuring that even if port 18790 is exposed via `0.0.0.0`, malicious public traffic is immediately blocked before touching the application logic.

### Changed
- One-shot CLI session behavior is now safer for ad-hoc probes:
  - `kabot agent -m ...` without an explicit `--session` now resolves to an ephemeral one-shot session ID instead of silently reusing `cli:default`,
  - interactive mode and explicitly provided session IDs keep their previous behavior,
  - this prevents follow-up contamination where a brand-new one-shot prompt accidentally inherits stale filesystem or weather context from an older ad-hoc run.
- Agent CLI smoke coverage is now easier to rerun across Windows, macOS, and Linux shells:
  - new module `python -m kabot.cli.agent_smoke_matrix` runs multilingual temporal/filesystem cases through list-argument subprocess calls instead of brittle shell strings,
  - it supports explicit skill smoke cases via `--skill ...` and broad skill discovery via `--all-skills`,
  - JSON output is now Unicode-safe even on legacy Windows consoles, so multilingual smoke results do not crash when stdout is still using `cp1252`,
  - the official `kabot doctor smoke-agent` surface now wraps that runner directly, including threshold gates for `context_build_ms` and `first_response_ms` so latency regressions can fail health checks on demand,
  - README now documents `kabot doctor smoke-agent` examples, and the first repo-wide lint cleanup batch reduced Ruff findings from `508` to `402` without changing runtime behavior.
- Narrow temporal chat prompts can now complete locally without waiting for the answer model:
  - new `kabot/agent/loop_core/message_runtime_parts/temporal.py` generates local fast replies for tiny day/date/time/timezone prompts such as `hari apa sekarang`, `besok hari apa`, `ä»Šå¤©æ˜ŸæœŸå‡ `, `ä»Šæ—¥ã¯ä½•æ›œæ—¥`, and `à¸•à¸­à¸™à¸™à¸µà¹‰à¸§à¸±à¸™à¸­à¸°à¹„à¸£`,
  - `process_message()` now uses that helper before context assembly or LLM execution when the turn is clearly simple, has no required tool, and is not inside another guarded workflow,
  - temporal matching now prioritizes the actual question type over trailing timezone hints, so prompts like `hari apa sekarang? ... pakai WIB ya` answer the weekday instead of being misclassified as timezone-only,
  - real CLI smoke on Windows now shows these prompts returning in roughly `first_response_ms=136-283`, while direct filesystem prompts still keep their own fast direct-tool path.
- One-shot runtime is now faster before the main answer model even runs:
  - `IntentRouter` now short-circuits obvious multilingual temporal/day-time prompts (`hari apa sekarang`, `ä»Šå¤©æ˜ŸæœŸå‡ `, `à¸•à¸­à¸™à¸™à¸µà¹‰à¸§à¸±à¸™à¸­à¸°à¹„à¸£`, `ä»Šæ—¥ã¯ä½•æ›œæ—¥`) to `GENERAL` + simple flow without paying an extra routing LLM call,
  - `process_message()` now also skips `router.route()` entirely for fast direct-tool turns once `required_tool` already resolved to deterministic direct tools such as `list_dir` or `get_process_memory`, so direct filesystem/system queries stop wasting a classification hop before the real tool executes,
  - real CLI smoke now shows filesystem prompts like `ãƒ‡ã‚¹ã‚¯ãƒˆãƒƒãƒ—ã®botãƒ•ã‚©ãƒ«ãƒ€ã®ä¸­ã€æœ€åˆã®5ä»¶ã ã‘è¦‹ã›ã¦ã€‚` dropping from multi-second routing overhead to roughly `first_response_ms=175`, while lightweight temporal prompts shave off the old pre-route classification delay as well.
- CLI multilingual input is now more resilient to shell/codepage damage across Windows-hosted terminals and still safe for POSIX shells:
  - new text-safety repair logic performs a narrow best-effort fix for common mojibake patterns caused by UTF-8 text being mis-decoded as Latin-1/CP1252 before Python receives `argv`,
  - one-shot and interactive `kabot agent` entrypoints now normalize incoming CLI text through that repair step without altering already-clean Unicode input,
  - regression tests now lock repaired Chinese/Japanese/Thai-style prompts at the CLI boundary, while real subprocess smoke confirms garbled direct args can still recover into correct multilingual agent understanding.
- Simple no-tool responses now start with a text-only LLM attempt before sending tool definitions:
  - `run_simple_response()` now calls the shared model-fallback helper with `include_tools_initial=False`, so lightweight chats such as time/day questions avoid paying the first-attempt tool payload cost,
  - the shared fallback state machine still preserves the same model-chain, auth-rotation, and text-only retry behavior for complex/tool-capable flows because the default path remains `include_tools_initial=True`,
  - regression coverage now locks both sides: simple-response turns must start text-only, while the normal tool-capable fallback path still keeps its existing behavior.
- Lean probe context for one-shot GENERAL chats is now more faithful to the real runtime path:
  - `ContextBuilder` now strips appended runtime `[System Note: ...]` blocks before deciding whether a probe turn is still a lightweight temporal/day-time chat,
  - this fixes a regression where natural prompts like `hari apa sekarang? jawab singkat, pakai WIB ya.` were getting their injected temporal note counted as part of the user turn, which re-enabled full auto-skill scanning and memory-context injection,
  - local CLI smoke now shows that temporal one-shot probes keep compact runtime context without auto-loading unrelated skills, while explicit skill prompts still load their matched skill context,
  - the regression is locked by `tests/agent/test_context_builder.py::test_context_builder_probe_mode_keeps_temporal_system_note_turns_lean`.
- Lean temporal probe context is now also cheaper on cold start:
  - `SkillsLoader.get_always_skills()` no longer routes through full `list_skills(filter_unavailable=True)` validation just to discover always-loaded skills,
  - the loader now scans skill frontmatter directly with a short cache while still honoring precedence, `disabled` entries, builtin allowlists, OS/bin/env requirements, and env/API-key values supplied from `skills.entries`,
  - local CLI smoke for `kabot agent -m \"hari apa sekarang? jawab singkat, pakai WIB ya.\" --logs` dropped `context_build_ms` from the previous ~`841ms` path to about `128ms`, while explicit skill turns still keep their richer skill-loading path,
  - regression coverage now locks this behavior in `tests/agent/test_skills_entries_semantics.py`.
- CLI one-shot agent runs are now lighter and easier to validate locally:
  - `kabot agent -m ...` now constructs `AgentLoop` with `lazy_probe_memory=True`, so probe-style one-shot runs start with lightweight SQLite-backed history and only boot the heavy hybrid memory backend if semantic memory tools are actually used,
  - the new `kabot.memory.lazy_probe_memory.LazyProbeMemory` backend preserves session history writes and recent context immediately while deferring Chroma/embedding startup until `search_memory`, `remember_fact`, or graph-memory access needs it,
  - `python -m kabot.cli.commands ...` no longer trips a circular import after the CLI refactor because the running `__main__` module is now aliased back to `kabot.cli.commands` for the extracted helper modules,
  - filesystem list-dir fallback is now more tolerant of mixed-language special-directory prompts like `desktopã®bot folder ...` by normalizing mixed separators and ignoring bogus relative candidates such as `3 item aja`.
- Temporal and correction-style chat turns now preserve local runtime context more reliably:
  - compact fast-path chats that ask about day/date/time or timezone now keep a system prompt with explicit local timezone labels instead of sending only the raw user turn,
  - short memory-commit turns such as `simpan` now bypass the raw no-history fast path so recent conversation context can still be seen by the model,
  - `suppress_required_tool_inference` now also blocks the live web-search safety latch in execution runtime, preventing correction/meta-feedback turns containing words like `sekarang` from being hijacked into `web_search`.
- Repo-wide sub-1000 refactor campaign now uses package folders for new extractions instead of adding more flat sibling modules:
  - `kabot/agent/loop.py` now delegates compatibility and thin runtime wrappers through `kabot/agent/loop_parts/`,
  - `kabot/agent/cron_fallback_nlp.py` is now a facade over `kabot/agent/cron_fallback_parts/intent_scoring.py` and `kabot/agent/cron_fallback_parts/constants.py`,
  - `kabot/agent/loop_core/execution_runtime.py` now imports shared helper functions from `kabot/agent/loop_core/execution_runtime_parts/helpers.py` plus LLM/simple-response flow from `kabot/agent/loop_core/execution_runtime_parts/llm.py`,
  - `kabot/agent/loop_core/message_runtime.py` now imports helper/state logic from `kabot/agent/loop_core/message_runtime_parts/helpers.py`, `kabot/agent/loop_core/message_runtime_parts/followup.py`, and tail/system flows from `kabot/agent/loop_core/message_runtime_parts/tail.py`,
  - these extractions preserve existing facades and monkeypatch targets through re-export/proxy wiring, so runtime behavior and test hooks stay intact while the new files live under dedicated refactor folders.
- The current refactor batch brought the last oversized runtime source files below `1000` lines without changing behavior:
  - `kabot/agent/loop.py` -> `723`
  - `kabot/agent/cron_fallback_nlp.py` -> `562`
  - `kabot/agent/cron_fallback_parts/intent_scoring.py` -> `632`
  - `kabot/agent/loop_core/execution_runtime.py` -> `774`
  - `kabot/agent/loop_core/message_runtime.py` -> `865`
- Large test modules are now also split into folder-based chunks so the workspace mainline has no Python file above `1000` lines:
  - `tests/agent/loop_core/test_message_runtime.py` -> themed files such as `test_message_runtime_basics.py`, `test_message_runtime_pending_file_context.py`, `test_message_runtime_skill_workflows.py`, and `test_message_runtime_fast_paths_and_status.py`
  - `tests/agent/loop_core/test_execution_runtime.py` -> themed files such as `test_execution_runtime_simple_and_guards.py`, `test_execution_runtime_tool_calls_and_skill_phases.py`, and `test_execution_runtime_direct_paths_and_research.py`
  - `tests/agent/test_tool_enforcement.py` -> `test_tool_enforcement_routing_and_aliases.py` and `test_tool_enforcement_fallback_and_navigation.py`
  - `tests/gateway/test_webhooks.py` -> `test_webhooks_ingress_and_auth.py` and `test_webhooks_dashboard_panels.py`
  - final workspace check excluding `.worktrees` now reports `TOTAL_GT_1000 0`.
  - Gateway regression coverage for nodes actions is now less brittle:
    - `tests/gateway/test_webhooks_cases/test_webhooks_dashboard_panels.py` now verifies disabled `Start`/`Stop` buttons by behavior (`disabled` state in rendered button markup) instead of pinning the exact CSS class string, which had already diverged from the inline-styled UI.
- Repo-wide sub-1000 refactor campaign continued without behavior changes:
  - `kabot/cli/commands.py` is now a thin facade (`409` lines) that re-exports command groups from dedicated helper modules such as `commands_setup.py`, `commands_gateway.py`, `commands_agent_command.py`, `commands_models_auth.py`, `commands_approvals.py`, and `commands_system.py`,
  - `kabot/agent/skills.py` now keeps `SkillsLoader` focused while multilingual matching constants/helpers live in `kabot/agent/skills_matching.py`,
  - `kabot/agent/tools/stock.py` now keeps tool runtime classes focused while symbol/alias extraction helpers live in `kabot/agent/tools/stock_matching.py`,
  - setup wizard sections `channels.py`, `model_auth.py`, and `tools_gateway_skills.py` now delegate large helper blocks to sibling `*_helpers.py` modules while preserving the same bound section methods and test monkeypatch targets,
  - `tests/agent/tools/test_stock.py` was split so extractor coverage now lives in `tests/agent/tools/test_stock_extractors.py`,
  - this batch brought the following files below `1000` lines: `kabot/cli/commands.py`, `kabot/agent/skills.py`, `kabot/agent/tools/stock.py`, `kabot/cli/wizard/sections/channels.py`, `kabot/cli/wizard/sections/model_auth.py`, `kabot/cli/wizard/sections/tools_gateway_skills.py`, and `tests/agent/tools/test_stock.py`.
- `kabot/cli/commands.py` has started being split into dedicated helper modules:
  - dashboard payload/runtime helper functions now live in `kabot/cli/dashboard_payloads.py`,
  - `commands.py` still re-exports the same helper names so existing CLI/gateway call sites and tests stay behavior-compatible,
  - this is a refactor-only first cut to reduce `commands.py` safely before moving larger command groups.
- File-path and storage-analysis routing are now less brittle and less likely to hallucinate stale tool context:
  - intent matching no longer treats latin keywords as blind substrings, so terms like `space` stop falsely matching inside paths such as `workspace`,
  - explicit file-path questions like `C:\...\landing_hacker.html font pada web ini` now stay out of stale `system info` follow-up flow and instead add a runtime note telling the model to `read_file` before answering about that file,
  - requests to find large files/folders now stop being forced into `cleanup_system` or generic `get_system_info`, letting the agent inspect disk usage directly instead of repeating cleanup,
  - session follow-up tests now lock these cases so new file-analysis turns and large-file scan turns clear old pending tool state cleanly.
- Chat-driven skill creation is now more natural and multilingual without becoming rigid:
  - semantic matching for `skill-creator` now catches broader phrasing such as new capabilities, integrations, and plugins across Indonesian, English, Thai, Japanese, and Chinese,
  - runtime now force-loads `skill-creator` context when the turn clearly asks to create/update a skill, instead of depending only on brittle keyword overlap,
  - skill-creation turns now carry a hidden workflow note that keeps the model in discovery/planning mode until explicit plan approval, preventing premature file creation while preserving conversational tone,
  - skill-creator docs now align with real runtime behavior by targeting workspace `skills/` directories and documenting env-based API secrets instead of hardcoded credentials.
- Explicit skill-use turns are now leaner and more reliable in CLI/runtime:
  - prompts like `please use the weather skill for this request` no longer drag the full `Available Skills` catalog into every GENERAL turn just because they mention the word `skill`,
  - task-specific `Auto-Selected Skills` are now placed ahead of long bootstrap/reference sections in the system prompt, so token-budget truncation preserves the active skill context instead of cutting it off,
  - multilingual explicit skill requests verified through `kabot agent -m ... --logs` stay AI-driven across English, Indonesian, Chinese, Thai, and Japanese prompt styles without falling back into unwanted parser-forced catalog/help flows,
  - CLI regression coverage now locks this behavior so explicit skill prompts keep their system prompt and skip the heavyweight catalog summary unless the user is actually asking about the skill catalog itself,
  - cold explicit skill turns now also avoid building the full keyword/body skill index when the prompt is a lightweight direct skill-use request such as `Please use the weather skill for this request.`, instead resolving the named skill through a narrow fast path while preserving the older full-index path for broader descriptive prompts,
  - local CLI smoke now shows that explicit skill `context_build_ms` drops from the previous ~`1148ms` path to about `143ms`, while the helper extraction for this optimization lives under `kabot/agent/skills_parts/` so `kabot/agent/skills.py` stays below `1000` lines.
- CLI one-shot probe turns are now lighter and more workspace-consistent:
  - `kabot agent -m ...` probe-mode system prompts now use a compact GENERAL prompt that skips heavy bootstrap/reference sections like large `AGENTS.md` files while still preserving active skill context,
  - probe-mode regression coverage now locks the compact prompt behavior at the actual CLI `agent -m ... --logs` entrypoint,
  - CLI and gateway `AgentLoop` construction now always pass the active loaded config into runtime, and `AgentLoop` reuses that provided config for memory initialization instead of silently reloading global defaults, preventing one-shot runs from drifting back to `~/.kabot/workspace` paths.
- Manual skill scaffolding is now workspace-first instead of builtin-first:
  - `kabot/skills/skill-creator/scripts/init_skill.py` now resolves the active workspace `skills/` directory before falling back to repo builtin skills,
  - running the scaffold script from a workspace root with `skills/` now lands new skills in the same place that chat-driven `skill-creator` and `SkillsLoader` already expect,
  - script output/help text was clarified so it no longer implies that user-created skills belong in the builtin package folder.
- Skill-creation execution now has a runtime approval latch instead of relying only on prompt instructions:
  - session metadata tracks `skill_creation_flow` stages (`discovery` -> `planning` -> `approved`) across short natural follow-ups,
  - assistant responses that present concrete skill file plans now promote the flow into `planning`,
  - short natural approvals like `oke lanjut` only unlock file-writing/runtime execution after a plan has actually been presented,
  - destructive tool calls (`write_file`, `edit_file`, `exec`) are now blocked during unapproved skill-creation turns, so the model stays conversational without being allowed to jump straight into coding.
- External skill install/update requests now use the same guarded conversational workflow:
  - `skill-installer` gets semantic intent priority for natural requests such as installing from GitHub/repo URLs or listing curated installable skills,
  - chat-driven install/update flows now reuse the same `discovery -> planning -> approved` latch before executing file or command mutations,
  - short multilingual approvals like `oke lanjut` can continue an install flow naturally, but only after a written plan has been shown.
- Skill workflow phases are now more visible across runtime status lanes and dashboard chat:
  - approval turns now publish an explicit `approved` status before execution begins,
  - dashboard chat history now preserves message metadata for runtime status events,
  - status-like dashboard bubbles now render phase badges such as `approved` instead of flattening everything into plain assistant text.
- **Refactored `webhook_server.py` into handler mixin modules**:
  - Reduced `webhook_server.py` from 1425 lines to ~120 lines (init + route registration + start only).
  - Created 8 handler modules in `kabot/gateway/handlers/`: `_base.py`, `dashboard.py`, `chat.py`, `sessions.py`, `nodes.py`, `config.py`, `control.py`, `webhooks.py`.
  - Uses mixin composition pattern â€” each module contributes handler methods via Python multiple inheritance.
  - Zero behavior change â€” pure code-move refactoring â€” all 31 gateway tests pass unmodified.
- **Fixed chat delay after sending**:
  - Restored HTMX polling interval (`every 3s`) on chat-log div with the new kb-bubble styled renderer.

- Setup wizard Google/Skills boundaries are now explicit:
  - main menu now labels Google as native auth (`no npm`) and Skills as configuration plus install plans,
  - Google wizard section now explicitly states that native Google auth does not require npm, Node.js skill installs, or `gog`,
  - Skills wizard section now explicitly states that it prepares manual dependency plans and that native Google setup lives in the separate Google Suite menu,
  - skill dependency choices now use human-readable requirement hints such as `needs env`, `needs binary`, `needs oauth`, `needs node package`, and `install via brew`,
  - built-in skill syncing wording was clarified so copying `SKILL.md` definitions into the workspace is no longer described like runtime dependency installation.
- **Dashboard UI separated into section template files**:
  - Each section tab is now its own HTML file in `kabot/gateway/templates/sections/` (`overview.html`, `chat.html`, `engine.html`, `settings.html`).
  - `dashboard.html` is now a layout shell only; section content injected at serve-time via `__SECTION_*__` token replacement in `handle_dashboard`.
  - `pyproject.toml` updated to include `kabot/gateway/templates/**/*.html` in build artifacts.
  - All 31 gateway tests continue to pass after this refactoring.
- **Chat UI model configuration improvements**:
  - Added "Save Configuration" button to the chat settings dropdown with brief "Saved!" confirmation and auto-close behavior.
  - Changing provider now clears the model input so the datalist refreshes with only provider-matching models.
  - Fixed HTMX `hx-include` to ensure provider/model/fallbacks are serialized on form submit even when outside the `<form>` tag.

- Semantic-first routing now suppresses stale deterministic tool forcing in more natural chat flows:
  - advice/recommendation turns (for example sunscreen/product guidance) no longer get re-forced into weather just because the sentence contains hot-weather wording,
  - short meta feedback like `kok lama` now clears stale pending stock/tool follow-up instead of accidentally continuing the previous action,
  - execution runtime now respects upstream semantic suppression so `message_runtime` decisions are not immediately overridden again from raw text.
- Structured last-tool context is now persisted and reused more safely:
  - weather and stock follow-ups can reuse prior resolved context without requiring the user to restate ticker/location every turn,
  - stock quote conversion follow-ups like `jadikan idr harganya` now work from structured context even when only the earlier quote symbol was known,
  - weather follow-up location context now resists degradation from short wind/follow-up turns.
- Filesystem routing is now much more reliable across Windows, macOS, and Linux style directory requests:
  - deterministic routing now treats folder-navigation prompts as `list_dir` instead of misclassifying `file/folder` phrases into `read_file("/folder")`,
  - path extraction now recognizes Windows drive paths (`C:\\...` and `C:/...`), UNC paths, POSIX paths (`/var/log`), and home-relative aliases like `Desktop`, `Downloads`, and `Documents`,
  - multilingual directory prompts now recognize common Indonesian, English, Chinese, Japanese, and Thai folder/location phrases for listing and follow-up navigation,
  - multilingual relative follow-ups like `è¡¨ç¤º ãƒ•ã‚©ãƒ«ãƒ€ bot` and `à¹€à¸›à¸´à¸” à¹‚à¸Ÿà¸¥à¹€à¸”à¸­à¸£à¹Œ bot` now count as fresh `list_dir` payloads, so session follow-up enrichment no longer drags old folder prompts back into the current turn,
  - directory follow-ups like `ya tampilkan` can reuse the last resolved folder path from session context instead of losing navigation state between turns,
  - `list_dir` now uses the same direct fast-path execution flow as other deterministic tools, so folder listings return immediately without waiting for an extra summarization pass,
  - natural location questions like `lokasimu sekarang dimana` now stay AI-driven while receiving exact workspace and last navigated path context, so the assistant can answer naturally without accidentally falling back into stale folder-list actions.
- Natural-name and multilingual extraction were tightened:
  - stock company-name extraction now trims trailing question noise (`Microsoft right now` -> `Microsoft`) so natural English company queries resolve more reliably,
  - free-style Indonesian phrasing like `bro kira-kira saham microsoft sekarang berapa ya?` now resolves to the intended company instead of falling back to rigid ticker prompts,
  - strong primary listings now auto-win for clear global-company matches (`Microsoft` -> `MSFT`) while genuinely ambiguous cases like Toyota still stay explicit,
  - compact Japanese/Chinese/Thai weather phrasing now strips weather/time filler words more cleanly during location extraction,
  - multilingual wind follow-ups now carry the previous weather location more reliably across non-Latin scripts,
  - native-script weather lookups for common cities like `æ±äº¬`, `åŒ—äº¬`, and `à¸à¸£à¸¸à¸‡à¹€à¸—à¸ž` now fall back to provider-friendly aliases (`Tokyo`, `Beijing`, `Bangkok`) before failing.
- Weather alias learning is now persisted in a separate user dictionary file instead of bloating main config:
  - successful native-script weather resolutions can auto-write learned aliases into `~/.kabot/weather_aliases.json`,
  - custom user alias overrides are merged from that dedicated file at runtime,
  - `config.json` stays focused on settings rather than growing into a multilingual alias store.
- CLI one-shot probe path is now cleaner and faster:
  - sentence-embedding worker startup no longer leaks Hugging Face progress/warning noise into terminal output,
  - LiteLLM message-sanitization debug output no longer prints raw `DEBUG:` lines to stdout,
  - `kabot agent -m ...` no longer starts the cron scheduler for ordinary non-reminder prompts,
  - one-shot CLI probe turns now run in lightweight probe mode so deferred hybrid-memory persistence/warmup does not keep the process alive after the answer is already ready.
- Weather follow-ups are now materially less rigid in natural chat:
  - short context-carrying turns like `berangin apa ga?` now reuse the last weather location instead of falling back to generic chat or web search,
  - attached Indonesian location forms like `dibandung` are normalized into a valid place lookup,
  - weather responses now include wind speed and direction in the Open-Meteo path for follow-up questions about wind.
- Update-vs-weather intent disambiguation is now stricter:
  - phrases like `cek update real time kondisi cuaca ... di Bandung` no longer misroute into Kabot update tooling just because they contain `cek update`,
  - weather structural payload wins when the sentence clearly asks for live weather data.
- Stock/FX follow-up continuity is now safer:
  - follow-ups like `jadikan idr harganya` reuse the previously resolved symbol instead of demanding a fresh ticker,
  - raw follow-up enrichment now avoids duplicate/noisy stock payload composition when combining current turn with prior symbol context.
- General advice queries are no longer over-forced into live web search:
  - research-route fallback now only auto-forces `web_search` for genuinely live/current-events style prompts,
  - general advice prompts like sunscreen/product guidance stay in normal LLM answer flow.
- Image-generation skill failure is now explicit and multilingual when provider config is missing:
  - missing API key/provider state returns a clear setup error instead of vague failure text,
  - error strings are catalog-driven across supported locales.
- **Documentation**: Modernized `README.md` design with "for-the-badge" shields, Table of Contents, and collapsible details for advanced sections to improve scannability.
- Stock/FX conversational routing is now less rigid on natural follow-ups:
  - stock tracking/history prompts (`pergerakan`, `track`, `1 bulan`, etc.) are now routed to `stock_analysis` instead of quote-only `stock`,
  - short ambiguous follow-ups no longer override a valid carried stock query unless the new turn contains explicit stock payload,
  - natural FX phrasing (`1 usd berapa rupiah`, `kurs usd ke idr`) now resolves to Yahoo pair `USDIDR=X` without requiring explicit ticker input.
- Added CLI doctor routing sanity mode:
  - new command surface: `kabot doctor routing`,
  - runs deterministic routing + guard matrix checks (news/weather/stock/crypto/update/reminder/non-action + wrong-tool blocks),
  - intended as quick pre-deploy validation for regression detection in tool selection behavior.
- Context-budget orchestration is now load-aware during message build:
  - `process_message` passes `budget_hints` (`load_level`, history pressure, fast-path flags) into `ContextBuilder.build_messages(...)`,
  - `TokenBudget` accepts component overrides and normalizes distribution safely.
- Context truncation now writes a compact continuity fact into memory:
  - when old history is dropped, context builder exposes a summary fingerprint,
  - runtime persists a deduplicated `context_compression` fact (`remember_fact`) so long conversations keep intent continuity with lower token cost.
- Tool-result context is now hard-capped per channel before re-injecting into LLM context:
  - large tool outputs are clipped by channel budget (Telegram/WhatsApp stricter than CLI),
  - prevents oversized tool payloads from flooding follow-up context and degrading responsiveness.
- Runtime token mode is now user-configurable from both setup and direct CLI config:
  - setup wizard (`kabot config` -> `Tools & Sandbox`) exposes `Runtime Token Mode (BOROS/HEMAT)`,
  - direct quick toggle is available via `kabot config --token-mode boros|hemat`,
  - direct saver alias is available via `kabot config --token-saver/--no-token-saver`,
  - default remains `boros`.
- CLI one-shot reminder waiting is now scoped to reminders created in the current turn:
  - existing old reminders no longer trigger repeated `Reminder scheduled for later...` notices on unrelated chat requests.
- Weather execution now retries compact location variants when free-form location text is long/noisy:
  - e.g. `Purwokerto Jawa Tengah` now transparently falls back to `Purwokerto`/comma variants before failing,
  - improves natural-language weather reliability without requiring rigid location format.
- Pending follow-up execution is now safer on acknowledgement replies:
  - short gratitude/closure messages (e.g. `thanks`, `makasih`, `terima kasih`) no longer force stale pending tool/intent execution,
  - pending follow-up metadata is cleared on closing acknowledgement turns to prevent repeated accidental tool runs.
- Pending follow-up execution now also ignores short greeting/opening small-talk turns:
  - short greetings like `halo/hi/hello/selamat pagi` are treated as fresh chat openers,
  - stale pending reminder/tool state is cleared instead of being auto-continued.
- Pending follow-up continuation is now stricter for non-confirmation short turns:
  - carry-over tool/intent continuation now activates on short confirmations only (e.g. `ya`, `gas`, `lanjut`), not generic short chat,
  - short interrogative prompts (e.g. `saranmu apa`) are treated as new requests, preventing stale tool continuation bleed from previous turns (stock/weather/etc.).
- Closing acknowledgement turns are now also excluded from history-based follow-up tool inference:
  - short gratitude replies (e.g. `oke makasih ya`, `iya makasih`) no longer infer previous reminder intents from recent conversation history,
  - prevents false cron fallback replies like reminder-time parsing errors after reminder completion.
- Dashboard surface is upgraded toward control flow while keeping Kabot's lightweight SSR+HTMX stack:
  - added dashboard panels for `Chat`, `Sessions`, `Nodes`, and `Config` on `/dashboard`,
  - chat panel now includes auto-refresh live log (`/dashboard/partials/chat/log`) to show recent conversation state without full page reload,
  - added SSE live stream endpoint for chat panel (`GET /dashboard/api/chat/stream`) with read-scope auth,
  - added dashboard APIs:
    - `GET /dashboard/api/chat/history`
    - `GET /dashboard/api/chat/stream`
    - `GET /dashboard/api/sessions`
    - `GET /dashboard/api/nodes`
    - `GET /dashboard/api/config`
    - `POST /dashboard/api/chat`
    - `POST /dashboard/api/config`
  - added dashboard partial actions:
    - `POST /dashboard/partials/sessions`
    - `POST /dashboard/partials/chat`
    - `POST /dashboard/partials/config`
  - added session-management write surface for operator flows:
    - `POST /dashboard/api/sessions` for structured `sessions.clear` / `sessions.delete` actions,
    - Sessions panel now exposes inline clear/delete actions (write-scope gated, no full page reload),
    - runtime control actions extended with `sessions.clear` and `sessions.delete`.
  - added node-management write surface for operator flows:
    - `POST /dashboard/api/nodes` for structured `nodes.start` / `nodes.stop` / `nodes.restart` actions,
    - Nodes panel now exposes inline start/stop/restart actions for channel nodes (write-scope gated, no full page reload),
    - runtime control action catalog now includes `nodes.start`, `nodes.stop`, and `nodes.restart`.
  - Nodes panel action UX is now state-aware:
    - `Start` is disabled when node state is already `running`,
    - `Stop` is disabled when node state is already `stopped`,
    - helps reduce accidental no-op control clicks in operator dashboard flow.
  - Sessions/Nodes action responses now re-render full panel fragments:
    - action forms target panel containers (`#panel-sessions`, `#panel-nodes`) directly,
    - operator sees updated table/state immediately after POST action (without waiting periodic poll tick).
  - added runtime gateway control handler actions:
    - `runtime.ping`
    - `chat.send`
    - `sessions.list`
    - `channels.status`
    - `config.set_token_mode`
  - dashboard status provider now includes enriched runtime payload (`sessions`, `nodes`, safe `config` snapshot, channel status map).
- Dashboard parity work now goes deeper into monitoring/operator flows:
  - added `POST /dashboard/partials/cron` and `POST /dashboard/partials/skills` for inline HTMX operator actions,
  - added runtime dashboard control support for `cron.enable`, `cron.disable`, `cron.run`, `cron.delete`, `skills.enable`, `skills.disable`, and `skills.set_api_key`,
  - added enriched dashboard payload fields for `cost_history`, per-model costs, `cron_jobs_list`, `skills`, `subagent_activity`, and `git_log`,
  - dashboard control capability metadata now advertises cron/skills actions for operator clients.
- Dashboard Chat panel now supports per-turn model/provider routing (operator flow):
  - added provider selector fed from runtime provider registry snapshot,
  - added model override input (`provider/model` or alias),
  - model suggestions now refresh automatically based on selected provider (with merged shortlist fallback when provider is empty),
  - replaced plain fallback text-only input with interactive fallback builder (add/remove model chips, serialized as fallback chain),
  - fallback builder now includes provider-aware model suggestions and keyboard-friendly add/remove interactions,
  - added channel/chat target passthrough fields for advanced control routing.
- Dashboard chat API/action payloads now forward model routing args end-to-end:
  - `provider`, `model`, `fallbacks`, `channel`, and `chat_id` are forwarded by `/dashboard/partials/chat` and `/dashboard/api/chat`,
  - runtime control action `chat.send` now composes provider+model safely and passes optional fallback chain to agent runtime.
- Runtime model selection now supports per-message override metadata:
  - `process_direct(...)` accepts `model_override` and `fallback_overrides`,
  - routing resolver prioritizes `msg.metadata.model_override` / `msg.metadata.model_fallbacks` over routed agent defaults for that turn only,
  - `/model ...` directives now persist model override into message metadata so directive path and dashboard path share one routing mechanism.
- Added explicit design + implementation planning docs for semantic-first routing rollout (without architectural rewrite):
  - `docs/plans/2026-03-05-semantic-intent-routing-design.md`
  - `docs/plans/2026-03-05-semantic-intent-routing-implementation.md`
- Planning baseline now formalizes `semantic-intent -> deterministic fallback` routing order, web search/fetch orchestration rules, and API-skill preflight hardening phases.
- Consolidated all current uncommitted changes under the next release track `0.6.0` (unreleased).
- This section is now the canonical pending-release notes for the next repo/PyPI publication.
- Deterministic tool/error responses are now more consistently multilingual and less hardcoded across fallback paths:
  - moved remaining literal fallback prompts for `web_search` into i18n keys (`web_search.need_query`, `web_search.need_topic`),
  - web-search empty-result fallback is now catalog-driven and localized (`web_search.no_results`) instead of fixed English literal,
  - stock/weather/crypto tool-level failure responses now use i18n catalog keys instead of inline literals (`stock.fetch_failed`, `weather.fetch_failed`, `crypto.fetch_failed`, etc.),
  - Meta Graph tool errors are now catalog-driven (`meta.missing_access_token`, `meta.unsupported_action`, `meta.error`) with locale-aware wording.
- Additional core-tool user-facing errors are now i18n-driven (reduced hardcoded English in cross-channel/tool-call paths):
  - filesystem tools (`read_file`, `write_file`, `edit_file`, `list_dir`) now emit catalog-based errors for not-found, permission, parse/replace mismatch, and list/read/write failures,
  - message tool now localizes missing target / missing callback / send-failure responses,
  - speedtest tool now localizes runtime failure + missing dependency + execution error responses.
- Knowledge/memory tool error paths are now catalog-driven and multilingual:
  - `knowledge_learn` now localizes file-not-found, extraction-failure, empty-readable-text, and long-term-memory save-failure responses (`knowledge.*`),
  - memory tools now localize missing memory-manager and exception failures (`memory.*`) instead of returning hardcoded English error strings,
  - memory UX responses now also use i18n keys for save-success/save-failed, empty-memory-search hints, and empty reminder list output.
- News-vs-market routing is now safer for conversational geopolitical queries:
  - strong geo-conflict topics (`iran/israel/war/conflict/...`) now boost `web_search` when users ask live/current context,
  - stock company-name fallback no longer triggers for those geo-conflict prompts (prevents misroute to stock ticker guidance),
  - feedback/meta chat containing `berita/news` (e.g. â€œkenapa jawabnya...â€) now scores as soft chat instead of forcing web search.
- Google News RSS fallback quality improved:
  - added lightweight relevance filtering by query terms to suppress clearly unrelated headlines in fallback result lists,
  - explicit `google_news_rss` provider selection is now recognized directly in provider picker (no unknown-provider fallback warning).
- Follow-up intent handling is now structural and multilingual:
  - removed hardcoded short-confirmation token catalogs in runtime flow,
  - replaced with low-information turn detection (length/payload-shape based),
  - explicit current-turn tool intent now overrides pending follow-up context,
  - added script-aware guard for non-whitespace languages (CJK/Thai/Arabic) so substantive short native-text requests are not misclassified as lightweight follow-ups.
- Deterministic tool fallback now prefers fresh raw user input over stale `required_tool_query` metadata when both map to the same required tool (prevents stale context bleed for weather/stock requests).
- Deterministic fallback now prioritizes short-turn raw payload when it contains concrete tool entities:
  - stock follow-ups like `adaro mana` no longer reuse stale previous ticker list metadata,
  - crypto follow-ups like `ethereum berapa` no longer reuse older multi-coin query metadata,
  - keeps continuation responsive while reducing rigid stale-context behavior.
- Deterministic router and direct-tool execution now include update intents:
  - `check_update` and `system_update` can be selected from natural user prompts,
  - update actions can run via required-tool fallback without forcing rigid command phrasing.
- Update runtime flow is stricter and more transparent:
  - installed version resolution now reads package metadata (`kabot` first, then `kabot-ai` fallback),
  - version comparisons normalize `v`-prefixed tags (`v0.6.0` == `0.6.0`),
  - post-update pip path verifies installed version against latest release and emits explicit mismatch failure if not actually latest,
  - tool payload now includes `notify_user` / `notify_message` for reliable post-update user notification.
- Weather intent extraction is more conversationally robust:
  - handles natural phrasing like `gimana suhu ...`, `kalau suhu ...`, and confirmation-prefixed requests (`ya coba cek ...`),
  - strips conversational prefixes before location resolution so users do not need rigid location-only input.
- Weather location extraction now supports non-Latin city names more reliably (e.g. `æ±äº¬`) and removes multilingual weather terms before final location normalization.
- Weather fetch timeout is tightened to a shared 3s request timeout to reduce long waits on failing providers.
- Deterministic fallback now has a generic stale-metadata guard (not stock-only):
  - short low-information follow-ups (e.g. `ya/ok/gas`) no longer reuse long assistant-style metadata blobs as fresh tool input,
  - web-search fallback now asks for clear topic/keywords when stale metadata is dropped.
- Weather tool latency path is reduced:
  - Open-Meteo and wttr providers now run in parallel for `simple` mode,
  - shared provider timeout tightened to 3s per request to reduce long tail waits.
- Stock deterministic fallback is now more natural-language tolerant and no longer uses invalid hardcoded placeholder symbols:
  - removed `TOP10_ID` fallback path that caused noisy fetch failures,
  - added IDX alias mapping for common conversational terms (`bca/bri/mandiri` -> `BBCA.JK/BBRI.JK/BMRI.JK`),
  - if user asks list/ranking style stock queries without explicit tickers, fallback now routes to `web_search` instead of forcing broken stock symbols,
  - added localized guidance (`stock.need_symbol`) when ticker data is truly missing.
- Follow-up inference is now safer on short confirmations (`ya/iya/gas`):
  - pre-context continuation no longer treats arbitrary assistant output as user query context,
  - assistant history is only eligible when it matches a short follow-up offer pattern,
  - prevents stale assistant paragraphs from being re-parsed into invalid stock symbols.
- Stock fallback now guards stale verbose metadata for short confirmations:
  - when confirmation is very short but carried `required_tool_query` is long/noisy, fallback prefers fresh raw input,
  - bare-token parsing is stricter to avoid regular words becoming ticker symbols.
- Runtime status locale is now pinned across phases:
  - message runtime persists `runtime_locale` into turn metadata,
  - execution runtime consumes that locale for `thinking/tool/done/error` phase text,
  - reduced mixed-language status flips in multilingual chats.
- Cross-runtime status duplication guard:
  - message runtime marks turns that already emitted initial status lane,
  - execution runtime suppresses duplicate initial `thinking` phase for those turns (prevents double "Processing your request..." bubbles).
- Outbound status/send race guard is now extended to additional channels:
  - added per-chat send-lock serialization for Bridge WebSocket, WhatsApp, QQ, Feishu, and DingTalk channel send paths,
  - prevents concurrent status/final-message interleaving from creating stale/duplicate progress behavior.
- Added abort shortcuts for safer interaction control:
  - recognizes standalone stop intent across slash + natural phrasing (`/stop`, `stop action`, `please stop`, `do not do that`, multilingual variants),
  - accepts trailing punctuation in stop requests (`STOP!!!`),
  - clears pending follow-up tool/intent context immediately to prevent stale continuation after user cancellation,
  - returns localized stop acknowledgement via i18n (`runtime.abort.ack`).
- Channel typing keepalive is now hardened to avoid silent stalls:
  - Telegram and Discord typing loops now include max-duration TTL guard and repeated-failure breaker,
  - typing loop tasks now self-clean from per-chat task maps after exit (no stale task handle retention),
  - prevents indefinite looping during transport instability while allowing automatic restart from status pulses.
- Discord status lane now explicitly ensures typing keepalive while progress updates are sent (`queued/thinking/tool`), improving responsiveness parity with Telegram/behavior.
- Stock tool now has defensive symbol extraction at tool layer (not only router layer):
  - mixed natural-language input is filtered to valid ticker candidates only,
  - plain confirmation/chat text is rejected with a clear ticker guidance error,
  - avoids per-word Yahoo fetch spam when upstream routing payload is noisy or stale.
- Stock company-name fallback parser is now stricter on generic advice/small-talk phrases:
  - conversational prompts like `saranmu apa` no longer become fake company-name candidates,
  - reduces accidental stock fetch attempts when user asks general advice after prior finance turns.
- Semantic-first stock routing is now less dependent on weak keyword parsing:
  - weak generic triggers like `price/harga/market` were removed from the global stock intent lexicon and no longer force `stock` by themselves,
  - stock name-candidate extraction now requires stronger market/value/company structure for multi-word phrases, reducing false positives from non-market chat (`gejolak politik`, product advice, etc.),
  - single-token novice lookups (`toyota`, `sap`) remain supported so user flow stays flexible and not rigid-format.
- Deterministic required-tool routing now uses a scored intent layer (structure + confidence), not pure keyword matching:
  - added `score_required_tool_intents(...)` to rank candidates by multilingual lexical + structural signals,
  - added confidence/ambiguity gating to avoid forcing tools on unclear short chat text,
  - added structural stock detection for explicit ticker symbols (e.g. `BBRI BBCA BMRI`, `BBCA.JK`) even when user omits `saham/stock` keywords,
  - improved live-research routing for time-sensitive prompts (e.g. `latest ... 2026 now`) while suppressing false web-search routing on local system-operation requests (`cek free space`, etc.).
- Follow-up tool continuation now uses a dedicated history-inference helper (loop facade + runtime integration):
  - `AgentLoop._infer_required_tool_from_history(...)` added for deterministic, testable multi-turn continuation behavior,
  - recent user intent scanning now skips assistant turns and ultra-short confirmation-only user turns,
  - continuation prefers newest substantive user intent (e.g., latest stock query) instead of older stale tool intents.
- Intent scorer now supports conservative typo-tolerant matching for Latin-script terms:
  - added bounded edit-distance matching (`<=1`) for single-word intent terms (reminder/weather/cleanup/system/monitor/search),
  - added conservative fuzzy matching for multi-word Latin phrases (e.g. `check update`, `disk cleanup` variants),
  - keeps multilingual exact matching for non-Latin scripts unchanged,
  - improves natural routing on common typo variants (`ingatkn`, `temprature`, `bersihkn`) without widening false positives aggressively.
- Reminder intent now supports time-action structure even without explicit reminder keyword:
  - detects patterns like `in 10 minutes ...` / `2 menit lagi ...` as cron intent when no stronger competing domain marker is present,
  - guarded against question-style and cross-domain text to avoid over-triggering.
- Update-intent disambiguation is now safer:
  - check/update prompts with explicit check verbs now prioritize `check_update`,
  - generic non-update prompts starting with `cek/check` no longer get misrouted into update tools.
- Stock fallback routing now reuses the same symbol parser as the stock tool:
  - removed duplicated ticker extraction logic from `tool_enforcement` fallback,
  - uses shared `extract_stock_symbols(...)` from `stock` tool as single source of truth,
  - keeps deterministic behavior while reducing hardcoded drift between routing and tool execution paths.
- Stock ticker extraction now filters file-like suffixes to prevent filename misrouting:
  - inputs such as `config.json` / `config.yaml` are no longer interpreted as stock tickers,
  - deterministic tool routing no longer misclassifies config-file requests as `stock` intents.
- Stock intent scoring now suppresses explicit non-action control phrases:
  - prompts like `stop bahas saham` / `bukan tentang saham` no longer force stock tool execution,
  - reduces rigid keyword-trigger behavior in multilingual conversational feedback turns.
- Non-action/meta-feedback suppression is now applied more broadly across deterministic routing:
  - weather/crypto/news/system-monitor/cleanup lexicon-only intents are suppressed on short negation-topic turns (e.g. `stop bahas cuaca`, `jangan bahas crypto`, `bukan tentang berita`),
  - prevents tool forcing when users are correcting context instead of requesting action.
- Pending follow-up continuation now also clears on short non-action feedback turns:
  - turns like `stop bahas ...` no longer inherit stale `pending_followup_tool` context,
  - avoids accidental tool execution loops after user correction messages.
- Pending follow-up continuation is now blocked on explicit fresh-request payload turns:
  - short turns containing file/config/path/URL payloads (e.g. `baca file config.json`) no longer inherit stale `pending_followup_tool` / `pending_followup_intent`,
  - runtime clears stale pending continuation state on those explicit new requests to prevent cross-intent misrouting (stock/news/reminder/tool carry-over).
- Stock intent scoring now also reuses the shared stock parser:
  - cron/intents scorer (`required_tool_for_query`) now consumes stock candidates from `extract_stock_symbols(...)`,
  - removes parser drift between routing score and execution fallback.
- Stock parser fallback is now stricter for unknown bare symbols:
  - unknown bare ticker fallback now requires explicit uppercase token input,
  - prevents casual lowercase single words (e.g. `hai`) from being misread as stock symbols.
- Crypto-vs-stock disambiguation is now safer for mixed natural prompts:
  - explicit crypto symbols (`btc/eth/...`) now provide strong crypto intent score so prompts like `harga btc terbaru` route to `crypto` instead of `stock`,
  - stock symbol scoring now ignores crypto-symbol tokens,
  - stock company-name fallback is suppressed when crypto domain markers are present.
- Added tool-call intent guard in execution runtime to prevent cross-intent hallucinated tool execution:
  - deterministic tool calls are now validated against current turn intent/payload before execution (`stock`, `crypto`, `cron`, `weather`, `get_system_info`, `get_process_memory`, `cleanup_system`, `speedtest`, `server_monitor`, `check_update`, `system_update`),
  - mismatched calls are blocked and fed back to the model as structured tool-result warnings instead of running the wrong tool,
  - guard logic reuses semantic required-tool scoring + structural payload checks (multilingual), reducing brittle keyword-only misroutes,
  - prevents regressions where general chat/file-read/news turns were accidentally routed into stock/reminder/weather/update flows.
- Web-search guard now follows explicit search intent instead of running on generic advice chat:
  - `web_search` joins guarded tool calls and only executes when current query has clear search/news/live-research intent,
  - generic advice prompts (e.g. sunscreen recommendations) no longer get forced into noisy `No results` search paths.
  - when runtime already pins `required_tool=web_search`, execution is allowed directly so multilingual/non-Latin search turns are not blocked by lexical marker heuristics.
- Guard model coverage now extends to API-skill style tool invocations:
  - image-generation family tools (e.g. `image_gen`) and TTS/voice family tools (e.g. `tts`, `text_to_speech`) now pass the same intent/payload guard before execution,
  - non-matching turns are blocked as `TOOL_CALL_BLOCKED_INTENT_MISMATCH` instead of executing the wrong skill/tool,
  - protects cross-skill fallback behavior when user intent is unrelated (e.g. market/news chat should not trigger image/TTS APIs).
- Stock tool-call guard now also blocks explicit non-action stock feedback turns:
  - turns like `stop bahas saham` are no longer treated as actionable stock payload at execution-guard stage,
  - closes a gap where non-action stock-topic feedback could bypass guard and execute stock tool.
- Stock alias coverage now includes `adaro` -> `ADRO.JK` for natural IDX phrasing.
- Stock novice-name resolver now supports broader natural company references without rigid ticker input:
  - added common Indonesian company phrase aliases (e.g., `bank rakyat indonesia`, `bank central asia`, `bank mandiri`, `bank negara indonesia`, `adaro energy indonesia`, `toba bara`),
  - added `toba` -> `TOBA.JK`,
  - stock alias parser now resolves alias mentions by in-text order (stable multi-symbol extraction from free-form sentences),
  - optional alias extension file is supported (`~/.kabot/stock_aliases.json` or `KABOT_STOCK_ALIASES_PATH`) so user-created skills can add new company aliases without core-code edits.
- Stock parser now tolerates single-character typo on explicit IDX symbols with `.JK` suffix (e.g. `AADRO.JK` -> `ADRO.JK`).
- Stock global-name resolution is now more novice-friendly and less country-hardcoded:
  - stock tool now attempts Yahoo symbol search when user gives company names instead of ticker format,
  - supports natural prompts like `toyota sekarang berapa` without requiring explicit `7203.T`,
  - keeps strict small-talk guard so non-market chat (`umur kamu berapa`) does not trigger symbol search/fetch.
- Stock name resolution now handles non-Latin company queries more robustly:
  - non-Latin compact company names (e.g. `ãƒˆãƒ¨ã‚¿`) are now preserved as search candidates instead of being dropped by ASCII-only tokenization,
  - improves global novice flow where users type company names in native scripts without ticker suffix.
- Stock intent lexicon/value markers expanded for multilingual market phrasing (Thai/Japanese/Chinese/Korean) to reduce rigid language dependence.
- Stock symbol discovery fallback is now more resilient and market-aware:
  - Yahoo symbol search now falls back across `query2` -> `query1` -> `autoc` endpoints before giving up,
  - ambiguous global company name matches are ranked by market hints in user text (e.g. `jepang/japan/tokyo` prefers `.T`),
  - keeps deterministic novice flow while reducing failed lookups on single-endpoint outages.
- Stock tool now asks a one-step clarification for ambiguous cross-market company names:
  - if a novice query resolves to multiple plausible listings without market hint (e.g. ADR vs local listing), Kabot asks which ticker/market the user means,
  - avoids silently choosing wrong exchange while staying concise/user-friendly.
- Ambiguous stock clarification is now locale-aware:
  - clarification prompt uses i18n catalog and follows detected user language (e.g. Indonesian phrasing for `... berapa sekarang`),
  - added `stock.ambiguous_symbol` translation entries (`en`, `id`, `ms`).
- Stock name resolver now caches repeated query results in-memory (TTL + bounded size):
  - repeated novice queries in the same runtime avoid redundant Yahoo symbol-search calls,
  - cache stores both resolved symbol list and ambiguity prompt candidates.
- Locale detector improved for Indonesian daily phrasing in short queries (`berapa`, `sekarang`, `harga`) to reduce accidental English fallback.
- ID/MS locale disambiguation for fallback i18n was rebalanced to reduce mixed-Malay false Indonesian detection:
  - removed overly generic Indonesian bias marker (`tolong`),
  - added Malay action marker (`tetapkan`) for reminder-style phrasing.
- Semantic-routing core code was lint-hardened without behavior changes:
  - normalized import ordering and removed dead imports in `loop.py` and `cron_fallback_nlp.py`,
  - replaced lambda resolver fallback in `tool_enforcement.py` with explicit helper function,
  - renamed function-scope all-caps locals in runtime files to comply with naming lint while preserving logic,
  - fixed follow-up path references in `message_runtime.py` after local variable rename.
- High-traffic tool modules were lint-hardened without functional behavior changes:
  - import/style cleanup in `stock.py`, `speedtest.py`, `update.py`,
  - `update.py` no longer uses bare `except` in git-cleanliness check helper.
- CLI + memory support modules were lint-hardened without functional behavior changes:
  - normalized import/style cleanup across `commands.py`, `bridge_utils.py`, memory backend/factory/vector-store helpers, and related tests,
  - `setup_wizard.py` section binding import now uses a local binder helper (removes late module import pattern),
  - `memory/__init__.py` keeps lazy export behavior via `_MODULE_LOCKS` + `__getattr__` without unused TYPE_CHECKING import block.
- Providers/core/utils support area was lint-hardened without functional behavior changes:
  - import/style cleanup in `litellm_provider.py`, `update_service.py`, `doctor.py`, `skill_validator.py`, `workspace_templates.py`,
  - aligned related providers/core tests with import-order and unused-import constraints.
- Setup wizard compatibility surface now explicitly retains `Prompt` export for test/monkeypatch and legacy caller stability after lint cleanup.
- Stock intent scoring now supports value-query phrasing with company-name candidates:
  - `required_tool_for_query` can classify concise company-name prompts without explicit `stock/saham` keyword when structure indicates market-price intent,
  - includes personal-chat guardrails to reduce false-positive stock routing.
- Deterministic stock fallback now aligns with the stock tool name-resolver path:
  - when no explicit ticker is found, fallback first checks company-name candidates before invoking stock tool,
  - low-information or non-market chat text still returns ticker guidance directly (no blind stock execution).
- Crypto deterministic fallback and tool execution now support multi-asset requests:
  - fallback extracts multiple coin IDs from natural phrases (e.g. `bitcoin dan ethereum`),
  - crypto tool accepts comma-separated CoinGecko IDs (`bitcoin,ethereum`) and returns combined output in one response.
- Weather intent/location parsing is now more conversational for degree phrasing:
  - added multilingual weather markers for `derajat/degree/celsius/fahrenheit`,
  - weather location extraction now strips those markers so prompts like `purwokerto berapa derajat sekarang` map cleanly to `Purwokerto`.
- Telegram status bubble lifecycle is hardened against stale duplicates:
  - when status edit fails with non-transient error, old status bubble is tracked as stale,
  - final response now best-effort cleans tracked stale status bubbles in addition to the active status bubble.
- Discord and Slack status bubble lifecycle now follows the same stale-cleanup model:
  - non-transient status-edit/update failures mark prior status bubble as stale,
  - final response path now cleans both active + stale status bubbles best-effort,
  - reduces cross-channel "status nyangkut" differences versus Telegram.
- Runtime keepalive cadence is faster for perceived responsiveness:
  - first keepalive pulse delay reduced (`2.5s -> 1.0s`),
  - keepalive interval tightened (`5.0s -> 4.0s`).
- Keepalive status dedupe is now channel-capability aware:
  - keepalive bypass is opt-in per channel instead of global behavior,
  - Telegram/Discord/Bridge WebSocket keep keepalive passthrough for typing/activity continuity,
  - non-typing channels (e.g. WhatsApp/QQ/Feishu/DingTalk) now dedupe repeated keepalive status text to avoid user-facing progress spam.
- Runtime keepalive emission is now channel-aware:
  - message runtime only starts periodic keepalive loop on passthrough-capable channels,
  - passthrough capability is resolved from live channel adapter wiring (`channel_manager`) with safe fallback by channel family,
  - non-passthrough channels keep queued/thinking/done lifecycle without periodic keepalive spam.
- Gateway startup now wires `ChannelManager` into `AgentLoop` so runtime status policy can follow real channel capabilities.
- Tool-call progress updates now emit explicit status metadata:
  - tool execution status messages from `process_tool_calls` now include `phase=tool` and `lane=status`,
  - prevents ambiguous status classification as default `thinking` in channel lifecycle handlers.
- Status-lane policy is now capability-aware (mutable vs non-mutable channels):
  - added channel capability contract (`_uses_mutable_status_lane`) with default-safe `False`,
  - mutable-lane channels (Telegram/Discord/Slack/Bridge adapters) keep full phase lifecycle UX,
  - non-mutable channels now emit minimal phase status (queued + tool-level progress) to reduce duplicate/noisy interim messages.
- Gateway method-scope governance is now centralized and stricter:
  - replaced scattered per-handler scope checks with route-policy evaluation (`method + path` rules),
  - added hierarchical scope compatibility (`operator.*`, `<family>.admin`, `operator.write -> operator.read`),
  - added dedicated dashboard control surface scopes (`operator.write`) separate from read-only dashboards (`operator.read`).
- Lightweight dashboard control surface is now available for operator flows:
  - added `GET /dashboard/api/control` capability metadata,
  - added `POST /dashboard/api/control` for structured control actions,
  - added HTMX control partial (`/dashboard/partials/control`) with safe action normalization and explicit error contracts (`invalid_action`, `control_unavailable`, `control_failed`),
  - control execution path supports sync/async handlers without changing existing gateway wiring.
- Dashboard access UX is now simpler for browser users with gateway auth enabled:
  - dashboard routes now accept token query auth (`/dashboard?token=...`) in addition to bearer headers,
  - dashboard HTML preserves query-token for HTMX partial/control refresh routes,
  - query-token auth is restricted to `/dashboard*` only and is not accepted for webhook ingress routes.

### Verified
- Focused RED->GREEN verification for newly added coverage:
  - `pytest -q tests/agent/test_context_builder.py tests/agent/loop_core/test_message_runtime.py::test_process_message_persists_context_truncation_summary_and_passes_budget_hints tests/agent/loop_core/test_execution_runtime.py::test_process_tool_calls_applies_channel_hard_cap_to_tool_result`
  - Result: `10 passed`.
- Targeted runtime/context regression sweep:
  - `pytest -q tests/agent/loop_core/test_message_runtime.py tests/agent/loop_core/test_execution_runtime.py tests/agent/test_context_builder.py`
  - Result: `77 passed`.
- Lint check for touched runtime/context files:
  - `ruff check kabot/agent/context.py kabot/agent/loop_core/message_runtime.py kabot/agent/loop_core/execution_runtime.py tests/agent/test_context_builder.py tests/agent/loop_core/test_message_runtime.py tests/agent/loop_core/test_execution_runtime.py`
  - Result: `PASSED`.
- Added semantic-intent routing verification log for this phase:
  - `docs/logs/2026-03-05-semantic-intent-routing-verification.md`
- Added runtime-token-mode CLI config verification:
  - `pytest -q tests/cli/test_config_runtime_mode.py`
  - Result: `3 passed`.
- Additional focused regression sweep after token-mode CLI + acknowledgement follow-up guard:
  - `pytest -q tests/agent/loop_core/test_message_runtime.py::test_process_message_short_followup_does_not_force_pending_cron_after_user_acknowledgement tests/cli/test_config_runtime_mode.py tests/cli/test_setup_wizard_tools_menu.py tests/config/test_runtime_resilience_schema.py tests/config/test_loader_meta_migration.py tests/agent/test_context_builder.py tests/agent/loop_core/test_execution_runtime.py`
  - Result: `61 passed`.
- Lint check for touched runtime/CLI/test files:
  - `ruff check kabot/cli/commands.py kabot/agent/loop_core/message_runtime.py tests/cli/test_config_runtime_mode.py tests/cli/test_setup_wizard_tools_menu.py tests/config/test_runtime_resilience_schema.py tests/config/test_loader_meta_migration.py tests/agent/test_context_builder.py tests/agent/loop_core/test_execution_runtime.py tests/agent/loop_core/test_message_runtime.py`
  - Result: `PASSED`.
- Dashboard parity verification (web UI + control helpers):
  - `pytest -q tests/gateway/test_webhooks.py tests/cli/test_gateway_dashboard_helpers.py tests/cli/test_gateway_tailscale_runtime.py tests/cli/test_config_runtime_mode.py tests/cli/test_setup_wizard_tools_menu.py`
  - Result: `52 passed`.
- Follow-up acknowledgement regression verification:
  - `pytest -q tests/agent/loop_core/test_message_runtime.py tests/agent/loop_core/test_execution_runtime.py tests/agent/test_tool_enforcement.py`
  - Result: `121 passed`.
- Dashboard model/provider override + routing metadata verification:
  - `pytest -q tests/agent/loop_core/test_execution_runtime.py tests/agent/loop_core/test_message_runtime.py tests/agent/test_tool_enforcement.py tests/agent/test_agent_model_switching.py tests/cli/test_gateway_dashboard_helpers.py tests/gateway/test_webhooks.py`
  - Result: `165 passed`.
- Lint check for dashboard/runtime control touched files:
  - `ruff check kabot/gateway/webhook_server.py kabot/cli/commands.py tests/gateway/test_webhooks.py tests/cli/test_gateway_dashboard_helpers.py tests/cli/test_config_runtime_mode.py tests/cli/test_setup_wizard_tools_menu.py`
  - Result: `PASSED`.
- Additional lint check for dashboard model-routing path:
  - `ruff check kabot/cli/commands.py kabot/gateway/webhook_server.py kabot/agent/loop.py kabot/agent/loop_core/routing_runtime.py kabot/agent/loop_core/message_runtime.py tests/cli/test_gateway_dashboard_helpers.py tests/gateway/test_webhooks.py tests/agent/test_agent_model_switching.py tests/agent/loop_core/test_message_runtime.py`
  - Result: `PASSED`.
- End-to-end runtime regression sweep for mixed chat flows + guard path:
  - `pytest tests/agent/test_tool_enforcement.py tests/agent/loop_core/test_message_runtime.py tests/agent/loop_core/test_execution_runtime.py`
  - Result: `137 passed`.
- Expanded runtime regression after non-action stock-guard hardening:
  - `pytest tests/agent/test_tool_enforcement.py tests/agent/loop_core/test_message_runtime.py tests/agent/loop_core/test_execution_runtime.py`
  - Result: `138 passed`.
- Lint baseline check:
  - `ruff check kabot tests`
  - Result: `FAILED` (`140` findings; repo-wide existing lint debt, not fully remediated in this batch).
- Focused lint check for touched locale/i18n files:
  - `ruff check kabot/i18n/locale.py tests/agent/test_fallback_i18n.py tests/agent/test_i18n_locale.py`
  - Result: `PASSED`.
- Additional targeted lint check for semantic-routing core:
  - `ruff check kabot/agent/cron_fallback_nlp.py kabot/agent/loop_core/tool_enforcement.py kabot/agent/loop_core/message_runtime.py kabot/agent/loop_core/execution_runtime.py kabot/agent/loop.py`
  - Result: `PASSED`.
- Additional targeted lint check for high-traffic tools:
  - `ruff check kabot/agent/tools/stock.py kabot/agent/tools/speedtest.py kabot/agent/tools/update.py tests/agent/tools/test_stock.py tests/agent/tools/test_update.py tests/tools/test_weather_tool.py tests/tools/test_web_fetch.py`
  - Result: `PASSED`.
- Additional targeted lint check for channel lifecycle parity area:
  - `ruff check kabot/channels/telegram.py kabot/channels/discord.py kabot/channels/slack.py kabot/channels/bridge_ws.py kabot/channels/whatsapp.py kabot/channels/qq.py kabot/channels/feishu.py kabot/channels/dingtalk.py tests/channels/test_telegram_typing_status.py tests/channels/test_discord_typing_status.py tests/channels/test_status_updates_cross_channel.py`
  - Result: `PASSED`.
- Additional targeted lint check for CLI + memory support area:
  - `ruff check kabot/cli/commands.py kabot/cli/bridge_utils.py kabot/cli/setup_wizard.py kabot/memory/__init__.py kabot/memory/chroma_memory.py kabot/memory/memory_backend.py kabot/memory/memory_factory.py kabot/memory/vector_store.py tests/cli/test_setup_wizard_default_model.py tests/cli/test_setup_wizard_memory.py tests/memory/test_auto_unload.py tests/memory/test_hybrid_auto_unload.py tests/memory/test_memory_backend.py tests/memory/test_memory_factory.py tests/memory/test_memory_leak.py tests/memory/test_null_memory.py tests/memory/test_sqlite_memory.py`
  - Result: `PASSED`.
- Additional targeted lint check for providers/core/utils support area:
  - `ruff check kabot/providers/litellm_provider.py kabot/services/update_service.py kabot/utils/doctor.py kabot/utils/skill_validator.py kabot/utils/workspace_templates.py tests/providers/test_litellm_provider_resolution.py tests/providers/test_registry.py tests/core/test_daemon.py tests/core/test_failover_error.py`
  - Result: `PASSED`.
- Broad regression suite:
  - `pytest -q tests/agent tests/channels tests/tools tests/gateway`
  - Result: `494 passed`.
- Additional focused regression suite after lint hardening:
  - `pytest -q tests/agent/test_cron_fallback_nlp.py tests/agent/test_tool_enforcement.py tests/agent/loop_core/test_message_runtime.py tests/agent/loop_core/test_execution_runtime.py tests/agent/test_fallback_i18n.py tests/agent/test_i18n_locale.py`
  - Result: `130 passed`.
- Additional tools-focused regression suite after lint hardening:
  - `pytest -q tests/agent/tools/test_stock.py tests/agent/tools/test_update.py tests/tools/test_weather_tool.py tests/tools/test_web_fetch.py tests/tools/test_web_fetch_guard.py tests/tools/test_meta_graph_tool.py`
  - Result: `62 passed`.
- Additional channel parity regression suite after lint hardening:
  - `pytest -q tests/channels/test_telegram_typing_status.py tests/channels/test_discord_typing_status.py tests/channels/test_status_updates_cross_channel.py`
  - Result: `35 passed`.
- Additional CLI/memory regression suite after lint hardening:
  - `pytest -q tests/cli/test_setup_wizard_default_model.py tests/cli/test_setup_wizard_memory.py tests/memory/test_auto_unload.py tests/memory/test_hybrid_auto_unload.py tests/memory/test_memory_backend.py tests/memory/test_memory_factory.py tests/memory/test_memory_leak.py tests/memory/test_null_memory.py tests/memory/test_sqlite_memory.py`
  - Result: `56 passed`.
- Additional providers/core regression suite after lint hardening:
  - `pytest -q tests/providers/test_litellm_provider_resolution.py tests/providers/test_registry.py tests/core/test_daemon.py tests/core/test_failover_error.py`
  - Result: `51 passed`.
- Global lint sweep:
  - `ruff check --fix kabot tests` followed by `ruff check kabot tests`
  - Result: `PASSED` (all global lint findings cleared).
- Final broad regression suite after global lint cleanup:
  - `pytest -q tests/agent tests/channels tests/tools tests/gateway tests/cli tests/memory tests/core tests/providers tests/config`
  - Result: `906 passed`.
- Full repository test sweep:
  - `pytest -q`
  - Result: `1332 passed, 6 skipped`.
- Targeted multilingual hardcoded-string regression suite:
  - `tests/agent/tools/test_stock.py`
  - `tests/tools/test_weather_tool.py`
  - `tests/tools/test_meta_graph_tool.py`
  - `tests/agent/test_tool_enforcement.py`
  - Result: `94 passed` (targeted run).
- Additional core-tool i18n regression suite:
  - `tests/tools/test_tool_i18n_errors.py`
  - Result: `4 passed` (targeted run).
- Additional knowledge/memory + web_fetch i18n regression suite:
  - `tests/tools/test_knowledge_memory_i18n.py`
  - `tests/tools/test_web_fetch_i18n.py`
  - `tests/tools/test_web_fetch.py`
  - `tests/tools/test_web_fetch_guard.py`
  - `tests/tools/test_memory_search.py`
  - Result: `23 passed` (targeted run).
- Additional routing/news-fallback regression suite:
  - `tests/agent/test_tool_enforcement.py`
  - `tests/agent/tools/test_web_search.py`
  - `tests/agent/test_cron_fallback_nlp.py`
  - Result: `63 passed` (targeted run).
- Combined targeted multilingual + tool-fallback verification:
  - `tests/agent/tools/test_stock.py`
  - `tests/tools/test_weather_tool.py`
  - `tests/tools/test_meta_graph_tool.py`
  - `tests/agent/test_tool_enforcement.py`
  - `tests/tools/test_tool_i18n_errors.py`
  - Result: `98 passed` (targeted run).
- Additional stock/crypto parser and fallback verification:
  - `tests/agent/tools/test_stock.py`
  - `tests/agent/test_tool_enforcement.py`
  - `tests/agent/test_cron_fallback_nlp.py`
  - Result: `66 passed` (targeted, including ADRO alias + IDX typo tolerance + multi-crypto fallback/tool behavior).
- Additional short-followup payload + non-Latin weather-location regression verification:
  - `tests/agent/test_tool_enforcement.py`
  - `tests/agent/test_cron_fallback_nlp.py`
  - `tests/agent/tools/test_stock.py`
  - `tests/tools/test_weather_tool.py`
  - Result: `84 passed` (targeted).
- Additional stock global-resolver fallback/disambiguation verification:
  - `tests/agent/tools/test_stock.py`
  - `tests/agent/test_tool_enforcement.py`
  - `tests/agent/test_cron_fallback_nlp.py`
  - Result: `82 passed` (targeted split runs: `26 + 56`).
- Additional ambiguous-listing clarification verification:
  - `tests/agent/tools/test_stock.py`
  - `tests/agent/test_tool_enforcement.py`
  - `tests/agent/test_cron_fallback_nlp.py`
  - Result: `83 passed` (targeted split runs: `27 + 56`).
- Additional locale-aware ambiguity + resolver cache verification:
  - `tests/agent/tools/test_stock.py`
  - `tests/agent/test_tool_enforcement.py`
  - `tests/agent/test_cron_fallback_nlp.py`
  - `tests/agent/loop_core/test_message_runtime.py`
  - `tests/agent/loop_core/test_execution_runtime.py`
  - Result: `152 passed` (targeted combined run).
- Added regression tests to lock behavior for:
  - low-information follow-up inference without keyword dependency,
  - explicit tool query overriding stale pending follow-up tool context,
  - weather/stock fallback preferring fresh raw user query over stale resolved metadata,
  - conversational weather location extraction (`gimana/kalau/ya coba cek` patterns),
  - update intent routing + update tool response formatting/version checks,
  - standalone stop/abort shortcut detection + pending follow-up cleanup path,
  - script-aware non-Latin follow-up handling,
  - locale propagation into execution-phase status text,
  - duplicate-initial-thinking suppression for status updates.
- Relevant suites executed:
  - `tests/agent/loop_core/test_message_runtime.py`
  - `tests/agent/loop_core/test_execution_runtime.py`
  - `tests/agent/test_cron_fallback_nlp.py`
  - `tests/agent/test_tool_enforcement.py`
  - `tests/agent/tools/test_update.py`
  - Result: `100 passed` (targeted runtime/fallback/update coverage).
- Additional post-fix tool/skills verification:
  - `tests/tools`
  - `tests/agent/tools`
  - `tests/agent/test_tool_enforcement.py`
  - `tests/agent/test_tool_name_uniqueness.py`
  - `tests/agent/test_tool_runtime_guards.py`
  - `tests/agent/loop_core/test_tool_loop_detection.py`
  - `tests/test_tool_validation.py`
  - `tests/agent/test_skills_entries_semantics.py`
  - `tests/agent/test_skills_loader_precedence.py`
  - `tests/agent/test_skills_matching.py`
  - `tests/agent/test_skills_requirements_os.py`
  - `tests/config/test_skills_settings.py`
  - `tests/cli/test_skills_commands.py`
  - `tests/cli/test_setup_wizard_skills.py`
  - Result: `167 passed` (tools + skills targeted verification).
- Additional regression for confirmation/follow-up safety:
  - `tests/agent/loop_core/test_message_runtime.py`
  - `tests/agent/test_tool_enforcement.py`
  - Result: `60 passed` (follow-up inference + deterministic tool fallback).
- Additional regression verification after stale-metadata/weather/channel fixes:
  - `tests/agent/test_cron_fallback_nlp.py`
  - `tests/tools/test_weather_tool.py`
  - `tests/agent/test_tool_enforcement.py`
  - `tests/agent/loop_core/test_message_runtime.py`
  - `tests/channels/test_telegram_typing_status.py`
  - `tests/agent/loop_core/test_execution_runtime.py`
  - `tests/channels/test_discord_typing_status.py`
  - `tests/channels/test_status_updates_cross_channel.py`
  - `tests/channels/test_bridge_ws_channel.py`
  - `tests/channels/test_whatsapp_bridge_runtime.py`
  - Result: `165 passed` (targeted).
- Additional hardening verification for typing + stock parser guard:
  - `tests/channels/test_telegram_typing_status.py`
  - `tests/channels/test_discord_typing_status.py`
  - `tests/agent/tools/test_stock.py`
  - `tests/agent/test_tool_enforcement.py`
  - `tests/channels/test_status_updates_cross_channel.py`
  - `tests/agent/loop_core/test_message_runtime.py`
  - `tests/agent/loop_core/test_execution_runtime.py`
  - Result: `138 passed` (targeted, combined run batches).
- Additional intent scorer verification:
  - `tests/agent/test_cron_fallback_nlp.py`
  - `tests/agent/test_tool_enforcement.py`
  - `tests/agent/loop_core/test_message_runtime.py`
  - Result: `72 passed` (targeted, post-intent-scorer run).
- Additional history-inference regression verification:
  - `tests/agent/test_cron_fallback_nlp.py`
  - `tests/agent/test_loop_facade_compat.py`
  - `tests/agent/test_tool_enforcement.py`
  - `tests/agent/loop_core/test_message_runtime.py`
  - Result: all passed (targeted, post-follow-up-inference helper integration).
- Additional typo-tolerance + multilingual routing verification:
  - `tests/agent/test_tool_enforcement.py`
  - `tests/agent/test_cron_fallback_nlp.py`
  - `tests/agent/loop_core/test_message_runtime.py`
  - `tests/agent/test_loop_facade_compat.py`
  - Result: all passed (targeted, post-typo-tolerant intent scorer + time-action reminder inference update).
- Additional gateway governance + dashboard control verification:
  - `tests/gateway/test_webhooks.py`
  - `tests/gateway/test_webhooks_meta.py`
  - `tests/gateway`
  - Result: `24 passed` (targeted, post-route-scope-policy + control-surface update).
- Additional novice stock-alias regression verification:
  - `tests/agent/tools/test_stock.py`
  - `tests/agent/test_tool_enforcement.py`
  - Result: targeted pass (`7 passed` + `4 passed` + `1 passed` + combined `7 passed`), including TOBA alias, long company-phrase extraction, custom alias file support, and stock intent detection for novice company names.
- Additional stock-parser unification regression verification:
  - `tests/agent/test_tool_enforcement.py`
  - `tests/agent/tools/test_stock.py`
  - Result: `52 passed` (targeted, post shared symbol-parser refactor).
- Additional dashboard query-auth regression verification:
  - `tests/gateway/test_webhooks.py`
  - `tests/gateway/test_webhooks_meta.py`
  - `tests/gateway`
  - Result: `26 passed` (targeted, post dashboard query-token auth + dashboard-only restriction).
- Additional natural-intent + Telegram status lifecycle verification:
  - `tests/agent/test_cron_fallback_nlp.py`
  - `tests/tools/test_weather_tool.py`
  - `tests/agent/test_tool_enforcement.py`
  - `tests/channels/test_telegram_typing_status.py`
  - `tests/agent/tools/test_stock.py`
  - Result: `83 passed` (targeted, post weather degree parsing + stock scorer/parser unification + stale status cleanup + keepalive tuning).
- Additional cross-channel status-bubble parity verification:
  - `tests/channels/test_discord_typing_status.py`
  - `tests/channels/test_status_updates_cross_channel.py`
  - `tests/channels/test_telegram_typing_status.py`
  - Result: `33 passed` (Discord + Slack + Telegram status lifecycle parity).
- Additional keepalive dedupe parity verification:
  - `tests/channels/test_discord_typing_status.py`
  - `tests/channels/test_telegram_typing_status.py`
  - `tests/channels/test_status_updates_cross_channel.py`
  - Result: `35 passed` (keepalive passthrough only on typing/activity-capable channels; dedupe on non-typing channels).
- Additional runtime keepalive policy verification:
  - `tests/agent/loop_core/test_message_runtime.py`
  - `tests/agent/loop_core/test_execution_runtime.py`
  - `tests/channels/test_status_updates_cross_channel.py`
  - `tests/channels/test_telegram_typing_status.py`
  - `tests/channels/test_discord_typing_status.py`
  - Result: `98 passed` (runtime keepalive loop only on passthrough-capable channels, with phase/status behavior preserved across tool and channel paths).
- Additional status-phase metadata verification:
  - `tests/agent/loop_core/test_message_runtime.py`
  - `tests/agent/loop_core/test_execution_runtime.py`
  - `tests/channels/test_status_updates_cross_channel.py`
  - `tests/channels/test_telegram_typing_status.py`
  - `tests/channels/test_discord_typing_status.py`
  - Result: `99 passed` (keepalive channel-awareness + explicit `tool` phase status metadata across runtime and channel dispatch).
- Additional mutable-lane policy verification:
  - `tests/agent/loop_core/test_message_runtime.py`
  - `tests/agent/loop_core/test_execution_runtime.py`
  - `tests/channels/test_status_updates_cross_channel.py`
  - `tests/channels/test_telegram_typing_status.py`
  - `tests/channels/test_discord_typing_status.py`
  - Result: `102 passed` (non-mutable channels avoid thinking/done spam while mutable channels preserve full interactive status lifecycle).
- Additional global stock-name resolver + intent regression verification:
  - `tests/agent/test_cron_fallback_nlp.py`
  - `tests/agent/test_tool_enforcement.py`
  - `tests/agent/tools/test_stock.py`
  - Result: `74 passed` (targeted, including Yahoo company-name lookup fallback + deterministic fallback guard + non-keyword stock intent routing).

## [0.5.8] - 2026-03-04 (P0 Delta)

### Added
- **Untrusted Context Guard (Prompt Injection Boundary)**:
  - Added explicit untrusted metadata boundary in context assembly:
    - system prompt now includes `Untrusted Context Safety` rules,
    - runtime now injects `[UNTRUSTED_CONTEXT_JSON] ... [/UNTRUSTED_CONTEXT_JSON]` as data-only context.
  - Runtime now passes normalized untrusted payload into context builder:
    - channel/chat/sender routing fields,
    - queue-merge metadata,
    - raw transport metadata snapshot (`metadata.raw`) when present.
- **Reasoning Lane Updates**:
  - Added dedicated outbound `reasoning_update` lane in execution runtime.
  - Runtime now emits lane metadata on progress events:
    - `status_update` -> `lane=status`,
    - `draft_update` -> `lane=partial`,
    - `reasoning_update` -> `lane=reasoning`.
- **Lightweight Gateway Dashboard (SSR + HTMX)**:
  - Added minimal web dashboard routes:
    - `/dashboard`
    - `/dashboard/partials/summary`
    - `/dashboard/partials/runtime`
    - `/dashboard/api/status`
  - Dashboard is server-rendered and HTMX-driven (no SPA runtime dependency).
  - Added runtime status provider wiring from `kabot gateway`:
    - model,
    - channels enabled,
    - cron jobs,
    - uptime,
    - host/port/tailscale mode.
- **Gateway Method-Scope Governance (Baseline)**:
  - Added scoped bearer-token format:
    - `gateway.auth_token = "<token>|scope1,scope2,..."`
  - Added per-route scope checks:
    - webhook ingress (`/webhooks/trigger`, `/webhooks/meta` POST): `ingress.write`,
    - dashboard/API status: `operator.read`.
  - Backward compatibility preserved for plain tokens (no scopes specified): full access as before.
- **PyPI Trusted Publisher Workflow**:
  - Added GitHub Actions trusted publishing workflow at:
    - `.github/workflows/workflow.yml`
  - Workflow uses OpenID Connect (OIDC) with:
    - `id-token: write`
    - environment `pypi`
    - publish trigger on tags (`v*`) and manual dispatch.

### Changed
- **Channel Progress Compatibility**:
  - Base channel progress parser now accepts `reasoning_update` as progress payload.
- **Multilingual/Encoding Hardening**:
  - Rebuilt shared multilingual lexicon with valid UTF-8 entries (Thai/Chinese terms no longer mojibake).
  - Reworked quality runtime refusal patterns to remove corrupted strings and improve multilingual matching quality.
  - Added mojibake detection fallback in i18n translator:
    - if locale string appears transcoding-corrupted, Kabot falls back to English template safely.
  - Added Indonesian colloquial locale markers (`lumayan`, `ternyata`, `banget`, etc.) so casual Indonesian chat no longer falls back to English status text too often.
  - Added session-level runtime locale stickiness for status updates:
    - short follow-ups (`ya`, `ok`, `gas`) keep prior detected locale instead of re-detecting to English each turn.
- **Gateway Startup Responsiveness (Watchdog Path)**:
  - `kabot gateway` now emits an immediate bootstrap line (`Booting kabot gateway...`) before heavy runtime imports.
  - Added preflight bind check before runtime initialization:
    - detects occupied gateway port early,
    - exits fast with code `78` (no long init wait before fail).
  - Added bootstrap phase visibility:
    - runtime module load duration,
    - bootstrap-ready duration.
  - Deferred heavy optional tool pack (Google Suite + GraphMemory) to background load after loop start, reducing cold import pressure on initial startup path.
  - Deferred `WebhookServer` import/build from gateway bootstrap path into runtime startup phase, so channel and agent startup no longer wait on `aiohttp` import cost.
  - Gateway runtime tasks now start (`agent`, `channels`, event dispatcher) before webhook server initialization, improving perceived readiness on slow disks.
  - Reduced eager import pressure in `AgentLoop` by moving heavy tool imports to local registration path and switching `kabot.agent` package exports to lazy attribute resolution.
- **Telegram Polling Conflict Hardening**:
  - Added explicit polling error callback for Telegram channel runtime.
  - `telegram.error.Conflict` now triggers controlled channel shutdown (single-shot) instead of repeated default traceback spam.
  - Telegram stop path is now defensive (best-effort updater/app/shutdown sequence) to avoid noisy teardown failures.
  - Telegram progress status updates now handle `Message is not modified` safely:
    - keep existing mutable status bubble,
    - do not emit duplicate â€œProcessing your requestâ€¦â€ status messages.
- **Cross-Channel Mutable Status Hardening (Telegram/Slack/Discord)**:
  - Telegram mutable status lifecycle now keeps status-id state on transient update/delete failures:
    - prevents orphan + duplicate progress bubbles on temporary network hiccups,
    - allows next keepalive/final pass to reconcile the same status message.
  - Slack status updates now treat `message_not_modified` as no-op and keep existing mutable status message.
  - Slack transient update/delete failures no longer force immediate new status bubble creation.
  - Discord status updates now evaluate HTTP status codes for update/delete lifecycle:
    - transient `429/5xx` keeps current mutable status id (prevents duplicate bubbles),
    - `404` clears stale status id and recreates cleanly on next status update.
  - Added/updated channel regression tests for these behaviors.
- **LiteLLM Lazy Runtime Stability**:
  - Fixed lazy exception symbol initialization in `LiteLLMProvider.chat`, preventing `TypeError: catching classes that do not inherit from BaseException` when `_execute_model_call` is monkeypatched or short-circuited.
  - `chat()` now guarantees runtime exception classes are initialized before fallback/error handling.
- **PyPI Packaging and Upgrade Naming Alignment**:
  - Renamed project package in `pyproject.toml`:
    - from `kabot-ai` to `kabot`.
  - Updated install and update flows to use `kabot` package name:
    - `install.sh`
    - `install.ps1`
    - docs quickstart/how-to references.
  - Runtime updater now attempts:
    - `kabot` first,
    - falls back to legacy `kabot-ai` for backward compatibility.


### Verified
- Added/updated regression tests for:
  - untrusted-context propagation and guard behavior,
  - reasoning lane publication,
  - scoped gateway auth + dashboard access control,
  - mojibake fallback in i18n.
- Relevant suites executed:
  - `tests/agent/loop_core/test_message_runtime.py`
  - `tests/agent/loop_core/test_execution_runtime.py`
  - `tests/agent/test_loop_facade_compat.py`
  - `tests/agent/test_tool_enforcement.py`
  - `tests/agent/test_multilingual_lexicon.py`
  - `tests/cli/test_gateway_port_guard.py`
  - `tests/cli/test_gateway_tailscale_runtime.py`
  - `tests/channels/test_status_updates_cross_channel.py`
  - `tests/channels/test_telegram_typing_status.py`
  - `tests/agent/test_i18n_locale.py`
  - `tests/gateway/test_webhooks.py`
  - `tests/gateway/test_webhooks_meta.py`
  - `tests/i18n/test_catalog_mojibake.py`
  - `tests/providers/test_litellm_provider_resolution.py`

## [0.5.8] - 2026-03-03

### Added
- **Parity Diagnostics Command**:
  - Added `kabot doctor --parity-report` for ops-focused parity visibility.
  - Added `--parity-json` output mode for automation pipelines:
    - write parity payload to file path, or
    - stream raw JSON to stdout via `--parity-json -`.
  - Report now includes:
    - runtime resilience snapshot,
    - fallback state machine presence checks,
    - adapter registry summary,
    - migration status summary,
    - WhatsApp bridge health probe,
    - effective skills source precedence roots.
- **Runtime Observability Config (Typed)**:
  - Added `runtime.observability`:
    - `enabled`
    - `emitStructuredEvents`
    - `sampleRate`
    - `redactSecrets`
- **Runtime Quota Config (Typed)**:
  - Added `runtime.quotas`:
    - `enabled`
    - `maxCostPerDayUsd`
    - `maxTokensPerHour`
    - `enforcementMode` (`warn|hard`)
- **Runtime Queue Config (Typed)**:
  - Added `runtime.queue`:
    - `enabled`
    - `mode` (`off|debounce`)
    - `debounceWindowMs`
    - `maxPendingPerSession`
    - `dropPolicy` (`drop_oldest|drop_newest`)
    - `summarizeDropped`
- **Security Trust Mode Config (Typed)**:
  - Added `security.trustMode`:
    - `enabled`
    - `verifySkillManifest`
    - `allowedSigners`
- **Skills Onboarding Config (Typed)**:
  - Added `skills.onboarding`:
    - `autoPromptEnv`
    - `autoEnableAfterInstall`
    - `soulInjectionMode` (`disabled|prompt|auto`)
- **Wizard One-Shot External Skill Onboarding**:
  - Skills setup wizard can now install an external skill directly from git in one flow:
    - repo install,
    - onboarding auto-enable,
    - required env key prompts,
    - optional SOUL persona injection.
  - Implemented in `kabot config -> Skills` interactive flow for TTY sessions.
  - Added persona preview + dual-target injection in prompt mode:
    - preview snippets before apply,
    - optional inject to `SOUL.md`,
    - optional inject to `AGENTS.md`.
  - Added multi-skill repo UX fallback:
    - when repo contains multiple `SKILL.md` candidates, wizard now prompts candidate subdir selection and retries install automatically.
  - Added pre-clone candidate discovery:
    - wizard inspects repo candidates before install,
    - allows choosing subdir upfront to avoid first-attempt failure/retry on multi-skill repositories.
  - Candidate discovery now includes metadata-aware ranking:
    - extracts skill name/description from `SKILL.md`,
    - prioritizes conventional folders (`skill/`, `skills/*`, shallower paths),
    - displays richer candidate labels in wizard chooser.
  - Added AGENTS persona template assistant in onboarding prompt-mode:
    - optional helper shown when injecting to `AGENTS.md`,
    - supports template styles:
      - `skill` (use skill-provided snippet),
      - `minimal`,
      - `strict`,
      - `tools`,
      - `custom` one-line routing policy,
    - auto-derives capability summary from skill metadata (`SKILL.md` frontmatter/body) when building templates,
    - preserves safe fallback to original skill snippet when canceled/back.
- **Channel Adapter Feature Flags (Config Surface)**:
  - Added `channels.adapters` map for adapter feature-flag overrides from config.
  - Channel manager now initializes adapter registry with these flags for runtime parity checks.
- **Soak Gate Foundation (Alpha)**:
  - Added soak gate evaluator utility: `kabot/utils/soak_gate.py`.
  - `kabot doctor --parity-report` now includes `soak_gate` status by reading `~/.kabot/logs/soak_latest.json`.
  - Gate checks include:
    - runtime duration threshold,
    - duplicate side-effect count,
    - tool protocol break count,
    - `p95_first_response_ms` soft limit.
- **Wave 2 Adapter Promotion (Stage 1)**:
  - Promoted `signal`, `matrix`, and `teams` from planned placeholders to runtime-loadable production adapters.
  - Added typed config models:
    - `channels.signal`
    - `channels.matrix`
    - `channels.teams`
  - Added bridge channel implementations:
    - `kabot/channels/signal.py`
    - `kabot/channels/matrix.py`
    - `kabot/channels/teams.py`
  - Added shared websocket bridge runtime for these adapters:
    - `kabot/channels/bridge_ws.py`
- **Wave 2 Adapter Promotion (Stage 2)**:
  - Promoted additional production adapters:
    - `google_chat`
    - `mattermost`
    - `webex`
    - `line`
  - Added typed config models:
    - `channels.google_chat`
    - `channels.mattermost`
    - `channels.webex`
    - `channels.line`
  - Added bridge channel implementations:
    - `kabot/channels/google_chat.py`
    - `kabot/channels/mattermost.py`
    - `kabot/channels/webex.py`
    - `kabot/channels/line.py`
- **Wave 1 Implementation Notes**:
  - Added `docs/plans/2026-03-02-kabot-0.5.8-wave1-implementation.md`.

### Changed
- **Gateway Port Source-of-Truth Alignment**:
  - `kabot gateway` now resolves runtime port from `config.gateway.port` when `--port` is not provided.
  - CLI `--port` remains a one-run explicit override.
  - Removes prior config/runtime mismatch where wizard-saved gateway port could be ignored at startup.
- **Tailscale Runtime Activation (No Longer Config-Only Placeholder)**:
  - Gateway startup now resolves tailscale mode from existing config fields:
    - `bind_mode=tailscale` -> `tailscale serve --bg --yes <port>`
    - `gateway.tailscale=true` (non-tailscale bind) -> `tailscale funnel --bg --yes <port>`
  - When tailscale exposure is enabled, runtime host is forced to `127.0.0.1` to avoid accidental wide bind with overlay exposure.
  - If tailscale setup fails while `bind_mode=tailscale`, gateway startup now fails fast with explicit error (instead of silently continuing as mock-like behavior).
  - Successful setup prints resolved HTTPS endpoint when MagicDNS is available.
- **Interactive Run Lifecycle (Cross-Channel)**:
  - Runtime now emits multilingual phase status updates consistently for:
    - `queued`
    - `thinking`
    - `tool`
    - `done`
    - `error`
  - Added runtime keepalive pulse during long-running turns:
    - after initial queued status, Kabot now emits periodic `thinking` status updates with `metadata.keepalive=true` until completion,
    - closes "silent" windows during long context build / tool / LLM execution.
  - Status dedupe now explicitly allows keepalive pulses to pass through:
    - repeated keepalive updates are no longer dropped by base channel dedupe cache,
    - bridge adapters can continue emitting activity typing hints on each pulse.
  - Status text lookup is now centralized in `kabot.i18n.catalog` (`runtime.status.*`) instead of inline runtime string maps, so language behavior is config/catalog-driven and no longer hardcoded per module.
  - Queue merge status (`queued_merged`) is now translated through i18n as well.
  - System identity prompt guidance was made language-neutral (removed Indonesian-only hardcoded examples).
  - Added draft-preview lifecycle on complex retries:
    - runtime emits `draft_update` when self-eval/critic requests a retry,
    - draft updates are deduped and use the same mutable progress lane as status updates,
    - final non-progress reply clears the mutable draft/progress indicator.
  - Added per-chat status dedupe in `BaseChannel` to suppress repeated/no-op phase messages.
  - Channel-specific status handling now follows one lifecycle pattern:
    - Telegram/Discord/Slack keep a mutable status message (edit-in-place, then cleanup on final reply),
    - Feishu renders status updates as lightweight text payloads,
    - bridge adapters emit best-effort typing activity hints for pre-final phases,
    - Email intentionally suppresses interim status updates to avoid inbox spam.
- **Fast Turn Path for Responsiveness**:
  - Added fast context bypass for deterministic direct-tool requests (`get_process_memory`, `cleanup_system`, `get_system_info`, etc.) so these turns no longer build full history/system prompt.
  - Added deterministic news/search path:
    - news/headline intents now map to required tool `web_search`,
    - `web_search` is now included in direct fast-path handling (raw tool result, no critic loop),
    - planning step is skipped when a required tool is already known (`required_tool`), reducing extra LLM round-trips,
    - `web_search` now falls back to Google News RSS when API-key providers are unavailable, so news queries still return live sources without key setup.
  - Added fast simple-context path for short non-tool chat turns.
  - Added speed guardrails in execution loop:
    - skip critic retries on short/CHAT turns,
    - skip critic retries on required-tool turns,
    - skip self-eval/critic loops on background/heartbeat turns.
  - Direct readouts for `cleanup_system` and `get_process_memory` now return raw tool output immediately (no extra summarization hop).
- **Input Maturity Hardening (Context over Keyword)**:
  - Added session-scoped follow-up intent latch (`pending_followup_tool`) in message runtime:
    - stores the last required tool per session with TTL,
    - allows short confirmations/follow-ups (e.g. `ya`, `gas`, `lanjut`, `terusin`) to continue the prior intended action without repeating keywords.
  - Added session-scoped non-tool follow-up intent continuity (`pending_followup_intent`):
    - preserves prior actionable user intent text + route profile with TTL,
    - maps short follow-ups like `ya lanjut` onto previous actionable context even when no explicit tool keyword is present,
    - injects `[Follow-up Context]` into turn input to keep downstream routing/skills loading coherent.
  - Added RESEARCH safety latch in message runtime:
    - when route profile is `RESEARCH` and query indicates live/current facts (latest/time/year/news markers), Kabot now forces `required_tool=web_search`.
  - Added execution-runtime RESEARCH fail-safe:
    - if upstream routing metadata is `RESEARCH` and `web_search` exists, agent loop forces web search tool path to reduce hallucinated â€œfrom memoryâ€ answers.
  - Extended critic speed policy:
    - skip critic retries for `RESEARCH` profile turns (in addition to existing short/chat/required-tool shortcuts) to prevent 20-40s retry loops on live-news prompts.
  - Added dedicated gap matrix document for operator parity tracking:
    - `docs/plans/2026-03-03--vs-kabot-input-gap-matrix.md`.
  - Improved actionable-intent detection for short messages:
    - short imperative prompts (e.g. `cek ram`, `buat skill`) are no longer treated as passive follow-up confirmations.
  - Improved skill matching for creator workflows:
    - `skill-creator` (and `writing-skills`) now gets intent-alias boost for phrases like:
      - `buat skill baru`,
      - `create/build skill`,
      - `skills creator`.
  - Fixed follow-up execution grounding across runtime phases:
    - `message_runtime` now persists resolved runtime hints into inbound metadata:
      - `effective_content`
      - `required_tool`
      - `required_tool_query`
      - `skip_critic_for_speed`
    - `execution_runtime` now consumes those hints so short confirmations like `ya/gas/lanjut` continue the intended prior action instead of re-asking or drifting.
  - Fixed direct tool query source for short confirmations:
    - deterministic fallback tools now use `required_tool_query` when present (instead of raw short text like `gas`), so `web_search/weather/cron` actions execute with the intended prior query context.
  - Hardened short follow-up continuity for live research:
    - short live-news prompts (for example `berita terbaru 2026 sekarang`) are now persisted as `pending_followup_intent` even when message length is short,
    - short confirmation phrases including action-form confirmations (for example `ambil sekarang`, `ya lakukan`, `terusin`) now continue prior intent/tool flow instead of dropping context.
  - Added execution-level live research fail-safe:
    - `execution_runtime` now forces `required_tool=web_search` for live/current-fact style prompts when web search tool is available, even when upstream route metadata is not explicitly `RESEARCH`.
  - Reduced critic-loop regressions on ambiguous confirmations:
    - short confirmation detection is now explicit and multilingual in execution runtime, preventing avoidable critic retries on `ya/gas/lanjut` style turns.
  - Telegram typing keepalive is now self-healing:
    - progress/status updates ensure typing keepalive is active when missing,
    - transient `send_chat_action` failures no longer terminate typing loop for the current run.
  - Improved responsiveness under heavy context assembly:
    - `context_builder.build_messages(...)` is now executed via `asyncio.to_thread(...)` in message runtime to avoid event-loop blocking,
    - typing keepalive/status pulses remain active while expensive prompt-context assembly runs.
- **Runtime Telemetry Emission**:
  - Added structured runtime events for:
    - turn lifecycle (`turn_start`, `turn_end`),
    - context build timing,
    - LLM attempt/result,
    - tool idempotency hits.
- **Per-Agent Workspace Context Resolution (Routing-Scoped)**:
  - Message runtime no longer hardcodes global `loop.context` for prompt assembly.
  - Context is now resolved per routed agent workspace on:
    - normal inbound messages,
    - system-origin callbacks (cron/system channel),
    - isolated execution paths.
  - Daily notes append now follows routed context resolver first, then falls back safely.
  - Result: `SOUL.md` / `AGENTS.md` / `USER.md` injection follows each agent workspace route, not global-only workspace.
- **Quota Enforcement in Fallback Runtime**:
  - `warn` mode logs quota warnings and continues.
  - `hard` mode blocks request before provider call when projected quota exceeds limit.
- **Config Migration Defaults**:
  - Loader now injects defaults for `runtime.observability`, `runtime.quotas`, `security.trustMode`, and `skills.onboarding`.
  - Loader now injects defaults for `runtime.queue` and keeps queue policy canonical during migration.
  - Skills section is canonicalized through migration path consistently (with atomic write + backup behavior retained).
- **Inbound Queue Burst Handling (Core Parity)**:
  - Added inbound queue policy engine in `MessageBus`:
    - per-session debounce window,
    - per-session pending-cap guard,
    - deterministic drop policy (`drop_oldest` / `drop_newest`),
    - dropped-message summarize metadata (`metadata.queue`) on surviving request.
  - Agent loop now auto-applies runtime queue settings from config on startup.
  - Message runtime now exposes merge awareness in queued phase text (e.g. merged pending messages) to improve interactivity.
- **External Skill Install Flow**:
  - `kabot skills install --git ...` now honors:
    - trust-mode validation (when enabled),
    - onboarding auto-enable toggle (`skills.onboarding.autoEnableAfterInstall`),
    - onboarding env prompts (`skills.onboarding.autoPromptEnv`) for required skill env keys,
    - optional SOUL persona injection (`skills.onboarding.soulInjectionMode`).
  - Installer now normalizes `skills` payload to canonical shape before save, including stable `skills.entries` presence.
  - In non-interactive terminals, persona injection prompt mode is skipped safely (no blocking prompt loop).
- **Wizard Persona Injection Flow (Prompt Mode)**:
  - AGENTS injection path now supports optional template-assisted generation without replacing existing default behavior.
  - Template assistant is opt-in (`default=false`) to keep current UX and test behavior stable.
  - Generated AGENTS templates include explicit routing semantics and skill identity (`skill_name`, `skill_key`).
  - Capability summary extraction now checks:
    - `SKILL.md` frontmatter `description`,
    - first meaningful content line,
    - fallback summary if metadata unavailable.
- **Adapter Feature Flag Semantics**:
  - `channels.adapters` now supports explicit override for any adapter key, including production adapters.
  - Example: setting `channels.adapters.telegram=false` now disables Telegram adapter initialization by policy.
- **Wizard Channel Instance Edit Flow (CRUD Hardening)**:
  - `Edit Instance` now supports per-channel credential updates while preserving existing secrets by default:
    - Telegram/Discord: edit bot token (optional),
    - WhatsApp: edit bridge URL (optional),
    - Slack: edit bot/app token independently (optional).
  - Existing values are retained unless the operator explicitly chooses to edit them.
- **Wizard Multi-Instance Channel Types Expanded**:
  - `Add Instance`, `Quick Add Multiple`, and `Apply Fleet Template` now include:
    - `Signal`
    - `Matrix`
    - `Teams`
    - `Google Chat`
    - `Mattermost`
    - `Webex`
    - `LINE`
  - Instance config prompts now support bridge URL + `allowFrom` for all bridge-based adapters above.
- **Bridge Adapter Payload Contract Hardening**:
  - Bridge websocket adapters now enforce stricter payload sanity checks:
    - outbound messages with missing `chat_id` are dropped,
    - outbound messages with empty text + empty media are dropped,
    - inbound non-object JSON payloads are ignored safely,
    - inbound empty message payloads (no text and no media) are ignored.
  - Reduces noise, accidental empty sends, and malformed bridge message side effects.
- **Parity Report Adapter Detail Expansion**:
  - `kabot doctor --parity-report` now includes instance-level adapter health details:
    - configured instance count,
    - per-instance channel key (`type:id`),
    - adapter enabled status (after feature flags),
    - runtime constructability probe (adapter can be instantiated with current config/dependencies),
    - bridge URL presence and TCP reachability check result,
    - operator-facing readiness state (`ready|not_ready`) with concrete reason tags (e.g. `adapter_disabled_by_flag`, `adapter_init_failed`, `bridge_unreachable`, `missing_bridge_url`).
  - Added adapter readiness summary counters in parity report:
    - `ready_instances` / `not_ready_instances`,
    - `ready_legacy` / `not_ready_legacy`,
    - reason occurrence counters for fast triage.
  - Added legacy adapter probe summary (`legacy_channels`) for enabled single-instance channels.

### Fixed
- **Gateway/Tailscale Gap Regression Coverage**:
  - Added tests to lock expected behavior for:
    - runtime gateway port resolution precedence (`CLI > config > default`),
    - tailscale mode resolution from current config contract,
    - tailscale runtime command execution path (`status` then `serve/funnel`),
    - tailscale startup failure propagation.
- **Codex Tool-Call Protocol Replay Hardening**:
  - Fixed duplicate `function_call_output` replay path that could emit repeated output entries for the same `call_id`.
  - Runtime now suppresses duplicate tool-output append on `tool_call_id` replay when output for that `call_id` already exists in message history.
  - ChatGPT backend request builder now prunes duplicate `function_call_output` entries per `call_id` (bounded by matching `function_call` count), preventing strict protocol rejection (`No tool call found for function call output ...`).
- **Trust-Mode Enforcement Gap on Skill Install**:
  - Fixed missing trust gate in external skill installer path by adding signer-manifest validation hook and fail-closed block behavior.
- **Doctor Surface Gap**:
  - Fixed CLI doctor surface by exposing explicit parity-report command path required by parity program ops flow.
- **Config Migration Persistence Robustness**:
  - `load_config` now degrades safely when migration write-back fails due filesystem permission errors:
    - warning is logged,
    - migrated config still applied in-memory,
    - runtime no longer crashes in restricted environments during migration checks.
- **Regression Coverage**:
  - Added tests for:
    - runtime schema defaults (`observability/quotas`, `security.trust_mode`, `skills.onboarding`),
    - migration defaults for the same sections,
    - doctor parity command surface + renderer dispatch,
    - quota warn/hard runtime behavior,
    - RESEARCH route web-search latch in message runtime,
    - critic bypass for long `RESEARCH` prompts,
    - RAM intent disambiguation (`kapasitas/total/spec RAM` -> `get_system_info`, usage/proses -> `get_process_memory`),
    - short follow-up continuation using pending non-tool intent context,
    - `skill-creator` intent matching for "create/buat skill baru" phrasing without explicit full skill-name mention,
    - trust-mode rejection in `skills install`,
    - parity report mandatory section contract,
    - AGENTS template assistant generation path and capability-summary resolution.
  - Expanded targeted integration regression suite to `98 passed` for wave-1/wave-2 continuity:
    - skills wizard/onboarding,
    - skill repo installer,
    - doctor parity,
    - adapter registry + bridge runtime,
    - channel instance management,
    - config migration/helpers.
- **Runtime Fallback Ambiguity (Double-Fallback)**:
  - Fixed duplicate fallback layers between runtime state machine and provider-level fallbacks.
  - Runtime now executes one explicit model per attempt, so logs/telemetry reflect the real serving model.
  - Runtime now treats provider synthetic error payloads (`finish_reason=error` / `All models failed...`) as real failures and continues to next configured model instead of falsely logging `result=success`.
- **Heartbeat Tool-Forcing False Positive**:
  - Heartbeat autopilot payloads no longer trigger `required_tool=cron` enforcement from keyword matching (`schedule`/`reminder`).
- **Channel Warning Noise**:
  - Suppressed `Unknown channel: cli` warning for non-network internal channels (`cli`, `system`) in outbound dispatcher.
- **Embedding Worker Protocol Robustness**:
  - Hardened sentence-embedding subprocess protocol to ignore non-JSON stdout noise and wait for matching JSON response IDs.
  - Added timeout-based guarded reads for init/request response loops to avoid parse crashes under noisy dependencies.
  - Serialized subprocess stdin/stdout request handling with an IO lock to prevent concurrent read/write interleaving that caused intermittent JSON parse errors (`char 0`, `char 8192`) under parallel embedding requests.
- **High `context_build_ms` Mitigation (Chat Latency)**:
  - Added caching for skills listing/summary generation in `SkillsLoader` with lightweight root-snapshot invalidation to avoid re-validating all skills every turn.
  - Reduced system-prompt overhead by skipping full â€œAvailable Skillsâ€ summary on routine `GENERAL`/`CHAT` turns (still shown for `CODING`/`RESEARCH` or explicit skill-related requests).
  - Heartbeat turns now skip skills-summary injection to keep background patrol prompts lean.
- **Cleanup UX Responsiveness**:
  - Direct `cleanup_system` execution now emits an immediate progress message before running long cleanup operations so users receive instant feedback instead of waiting on first completion output.
- **Tool-First Response Integrity (Anti-Hallucination Guard)**:
  - Prevented premature completion-like status messages before tool outputs are available.
  - Runtime now emits a neutral pre-tool progress message (`Processing your request, please wait...`) whenever a response contains tool calls.
  - Added regression coverage for both:
    - tool calls with completion-like assistant text, and
    - tool calls with empty assistant text.
- **Mutating Direct-Tool Output Safety**:
  - Updated direct-tool fast path so `cleanup_system` returns raw tool output immediately.
  - Removed LLM re-summary step for mutating cleanup execution to avoid optimistic/imagined post-cleanup phrasing.
  - Added regression tests to verify:
    - cleanup direct path skips `provider.chat`, and
    - read-only direct tools still use summary behavior.
- **Multilingual Skill-Matching Obedience**:
  - Improved skill matcher token extraction for Thai script (`\u0E00-\u0E7F`) and non-ASCII containment signals.
  - Added explicit full skill-name prioritization in ranking.
  - Added regression test for explicit digit-heavy skill names (e.g., `1password`) to ensure explicit mention remains rank #1 under competition.
- **Deterministic Skills Test Isolation**:
  - Hardened skills test suite against host-environment contamination from `~/.kabot/skills`.
  - Added HOME isolation fixtures and managed-skill temp-dir overrides in skills matching/precedence/semantics/OS tests.
  - Result: skills suite is deterministic across environments and no longer depends on local globally-installed sample skills.
- **Anti-Collision Regression Guards**:
  - Added explicit regression checks to prevent hidden naming conflicts:
    - unique `tool.name` across all tool classes,
    - unique adapter keys in channel adapter registry,
    - deterministic skill-name dedupe across all source roots (workspace/project-agents/personal-agents/managed/builtin/extra).

## [0.5.7] - 2026-02-26

### Added
- **Skills Git Repo Auto-Installer (CLI)**:
  - Added new command: `kabot skills install --git <repo>`.
  - Supports `--ref`, `--subdir`, `--name`, `--target managed|workspace`, and `--force`.
  - Auto-detects skill source folder (`SKILL.md`) with support for multi-layout repos (including conventional `skill/` subtree).
  - Installs skill into managed shared skills dir (default) or workspace skills dir, then marks it enabled in `skills.entries`.
  - Includes guidance after install to continue env/dependency setup from wizard.
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
- **Native Graph Memory (Entity-Relation Layer)**:
  - Added new internal graph memory store (`kabot/memory/graph_memory.py`) backed by SQLite.
  - Automatically extracts and stores lightweight relations (e.g., `uses`, `depends_on`, `prefers`) from conversation/fact text.
  - Added graph summary/query integration hooks in memory backends:
    - `search_graph(entity, limit)`
    - `get_graph_context(query, limit)`
  - Added new tool: `graph_memory` for inspecting relation memory directly from chat/tool runtime.
- **Default Bottleneck-Elimination Autopilot Loop**:
  - Added `runtime.autopilot` config:
    - `enabled`
    - `prompt`
    - `maxActionsPerBeat`
  - Heartbeat service now supports default proactive patrol prompt when no active heartbeat tasks are present.
  - Gateway heartbeat wiring now reads heartbeat/autopilot config instead of fixed hardcoded interval.

### Changed
- **Strict Channel Access Guard (Fail-Closed allowFrom)**:
  - `BaseChannel` now enforces fail-closed sender access when `tools.exec.policyPreset = strict` and `allowFrom` is empty.
  - Channel manager now decorates runtime channels with active security preset so access checks are consistent for legacy and multi-instance channels.
  - Wizard `allowFrom` prompt now warns explicitly when strict preset is active and list is empty (deny-all behavior).
- **Command Firewall Strict Preset Hardening**:
  - Strict preset now treats `policy: ask` as deny-by-default via `allowlist` mode instead of leaving permissive ask behavior.
  - Keeps explicit `deny`/`allowlist` policy values authoritative when already set in config.
- **Gemini 3.1 Catalog Expansion**:
  - Added `google/gemini-3.1-pro` and `google-gemini-cli/gemini-3.1-pro` to model catalog.
  - Added `openrouter/google/gemini-3.1-pro` parity reference.
  - Added aliases: `gemini31` and `gemini-3.1-pro`.
- **Documentation UTF-8 Cleanup**:
  - Normalized mojibake/corrupted characters in `README.md` and `HOW_TO_USE.MD` to proper UTF-8 text.
  - README title icon fixed to wolf emoji (`Kabot ðŸº`).
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
  - Added mid-session hot-reload for skill matching cache:
    - `match_skills()` now auto-refreshes keyword/body indexes when `SKILL.md` files are added, removed, or edited.
    - Cache invalidation uses deterministic snapshotting (`path + mtime + size`) across all configured skill roots.
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
- **Context Builder Graph Injection**:
  - `ContextBuilder` now supports memory config injection and can include `# Graph Memory` summary when graph DB exists.
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
- **Sentence Embedding Auto-Unload Determinism**:
  - Fixed race window where embedding subprocess could remain alive briefly past idle timeout under load.
  - Auto-unload shutdown path now uses a stricter graceful timeout before forced kill to ensure deterministic unload timing.
  - Added/validated regression path with repeated timeout test runs to avoid flaky behavior.
- **Skills Config Migration Key Integrity**:
  - Preserved constant-style env keys (e.g. `OPENAI_API_KEY`) during config camel/snake normalization and migration write-back.
  - Added migration persistence path that writes migrated config atomically with timestamped backup copy.
- **Wizard Select Non-TTY Crash**:
  - Fixed `kabot config` traceback in non-interactive/piped terminals (`NoConsoleScreenBufferError` from prompt_toolkit).
  - `ClackUI.clack_select()` now falls back safely when stdin/stdout are not TTY while keeping normal interactive UX unchanged.
  - Added regression test for non-TTY select fallback.
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
- **Command Firewall Preset Regression (Policy Override)**:
  - Fixed bug where runtime preset could overwrite explicit firewall policy from `command_approvals.yaml`.
  - Explicit `deny`/`allowlist` policies now remain authoritative; fail-safe deny remains locked on config load failure.
  - `compat` preset keeps permissive behavior by promoting `ask` to `allowlist` only when appropriate.
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

### Added - Parity Program Foundation (Wave 1 + Wave 2/3 Base) - 2026-02-27

- **Runtime Typed Config (Resilience + Performance)**:
  - Added `runtime.resilience` config block:
    - `enabled`
    - `dedupeToolCalls`
    - `maxModelAttemptsPerTurn`
    - `maxToolRetryPerTurn`
    - `strictErrorClassification`
    - `preventModelChainMutation`
    - `idempotencyTtlSeconds`
  - Added `runtime.performance` config block:
    - `fastFirstResponse`
    - `deferMemoryWarmup`
    - `embedWarmupTimeoutMs`
    - `maxContextBuildMs`
    - `maxFirstResponseMsSoft`
- **Typed Skills Root Contract**:
  - Replaced loose `skills: dict` root schema with typed `SkillsConfig` model (`entries`, `allow_bundled`, `load`, `install`, `limits`).
  - Kept backward compatibility via normalization and dict-like access helpers.
- **Channel Adapter Registry Architecture**:
  - Added `kabot/channels/adapters/` with:
    - `ChannelAdapterSpec` / `AdapterCapabilities`
    - centralized `AdapterRegistry`
  - Channel manager now initializes legacy + instance channels through adapter registry (instead of hardcoded branch tree).
  - Added scaffold entries for top-15 production keys and 25 experimental adapters with feature-flag-aware enablement.
- **Config Migration Expansion**:
  - Added migration for `tools.exec.policyPreset` in legacy configs.
  - Added auto-injection of canonical `runtime` resilience/performance sections during migration, with existing backup flow.

### Changed - Runtime Determinism, Tool Safety, and Latency

- **Deterministic Fallback Pipeline** (`execution_runtime.call_llm_with_fallback`):
  - Switched to immutable per-turn model chain snapshot (no in-place chain mutation).
  - Added bounded attempts via `maxModelAttemptsPerTurn`.
  - Added explicit state transitions in logs (`primary`, `auth_rotate`, `model_fallback`, `text_only_retry`).
  - Added strict error-class mapping (`auth`, `rate_limit`, `tool_protocol`, `transient`, `fatal`) via failover classifier.
- **Tool-Call Idempotency + Protocol Guards**:
  - Added per-turn payload hash idempotency and `tool_call_id` replay suppression with TTL.
  - Duplicate tool replays now return cached tool result instead of re-executing side effects.
  - Added assistant/tool envelope guard to avoid duplicate assistant tool-call envelopes.
  - Added status-update dedupe for repeated tool progress texts in the same turn.
- **Fast First-Response Path**:
  - Added deferred memory warmup mode with timeout-bound warmup (`embedWarmupTimeoutMs`).
  - Added non-blocking memory writes for user/assistant/tool records when fast mode is enabled.
  - Added context-build budget telemetry and soft-target first-response warnings.
  - Added cold-start + first-response + memory-warmup telemetry log markers.
- **Security Presets (Strict Default)**:
  - Added `tools.exec.policy_preset` (`strict|balanced|compat`).
  - `ExecTool` now passes preset into command firewall runtime policy selection.
  - Firewall audit output now includes active preset metadata.
  - Setup wizard `Tools & Sandbox -> Execution Policy` now exposes security preset selector.

### Fixed - Regression and Coverage

- Added/extended tests for:
  - deterministic fallback immutability and tool-protocol text-only retry,
  - turn-level tool idempotency suppression,
  - runtime schema defaults and skills typed normalization,
  - loader migration for runtime defaults + policy preset,
  - adapter registry production/experimental behavior and manager integration.
- Verification snapshot for this batch:
  - `tests/agent/loop_core/test_execution_runtime.py`
  - `tests/config/test_loader_meta_migration.py`
  - `tests/config/test_runtime_resilience_schema.py`
  - `tests/channels/test_multi_instance_manager.py`
  - `tests/channels/test_adapter_registry.py`
  - `tests/cli/test_setup_wizard_tools_menu.py`
  - `tests/cli/test_setup_wizard_skills.py`
  - All targeted suites pass.

## [0.5.6] - 2026-02-24

### Added
- **Embedding Auto-Unload System**: Intelligent memory management for the sentence-transformers embedding model (`all-MiniLM-L6-v2`)
  - Auto-unload after 5 minutes idle via configurable `auto_unload_timeout` in config (default: 300s, set 0 to disable)
  - Manual unload API: `memory.unload_resources()` for explicit resource cleanup
  - Recursive PyTorch module clearing with `module.cpu()` + parameter/buffer dereferencing
  - Platform-specific memory trimming: Windows `EmptyWorkingSet`, Linux `malloc_trim`, macOS `gc.collect()`
  - Model reloads transparently on next `search_memory()` Ã¢â‚¬â€ zero quality/intelligence loss
  - Thread-safe with `threading.RLock` and double-check locking pattern
- **ChromaDB Segment Cache Cap**: Added `chroma_memory_limit_bytes=50MB` to `Settings()` to limit in-memory HNSW segment cache
- **Memory Statistics API**: `embeddings.get_memory_stats()` returns model state, load count, and unload count

### Changed
- **Memory Factory** (`kabot/memory/memory_factory.py`): Added `auto_unload_seconds` passthrough from config with input validation
- **Sentence Embeddings** (`kabot/memory/sentence_embeddings.py`): Complete rewrite Ã¢â‚¬â€ added lazy loading, timer-based auto-unload, `_unload_model_internal()` with recursive cleanup, `warmup()` for background pre-loading
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
Kabot idle (91 MB) Ã¢â€ â€™ User sends message Ã¢â€ â€™ model loads (+359 MB = 450 MB)
                                            Ã¢â€ â€œ
                   User goes quiet Ã¢â€ â€™ 5 min timer expires Ã¢â€ â€™ model unloaded (443 MB*)
                                            Ã¢â€ â€œ
                   Next message Ã¢â€ â€™ model reloads (3-5s) Ã¢â€ â€™ fully functional
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
- Recursive module cleanup: `module.cpu()` Ã¢â€ â€™ clear parameters Ã¢â€ â€™ clear buffers Ã¢â€ â€™ `del` children
- Platform trimming: `ctypes.windll.kernel32.SetProcessWorkingSetSize` (Windows), `ctypes.CDLL(None).malloc_trim(0)` (Linux)
- 874 tests passing, 6 skipped

## [0.5.5] - 2026-02-24

### Added
- **Embedding Auto-Unload**: Embedding model (`all-MiniLM-L6-v2`) automatically unloads after 5 minutes idle
  - Configurable via `auto_unload_timeout` in config (default: 300s)
  - Manual unload: `memory.unload_resources()`
  - Recursive PyTorch module clearing + platform-specific memory trimming
  - Model reloads transparently on next search Ã¢â‚¬â€ zero quality loss
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
  - Ping-pong detection (AÃ¢â€ â€B alternating tool calls)
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
- **Agent Loop**: Integrated LoopDetector Ã¢â‚¬â€ critical loops blocked, warnings logged
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
- **AI-as-Developer Execution Discipline**: Added critical system prompt rules that force the AI to write scripts on-the-fly, execute them immediately using `exec`, verify results, and schedule recurring jobs using `cron` Ã¢â‚¬â€ instead of just describing what to do. Includes cross-platform detection for Windows, Linux, macOS, and Termux.

### Added
- **Cross-Platform Server Monitor Tool**: New `server_monitor` tool provides real-time resource usage (CPU load %, RAM used/free GB, disk usage %, uptime, network I/O) with full support for Windows (PowerShell), Linux (bash), macOS (bash), and Termux (Android). Triggered by 40+ multilingual keywords across 7 languages (EN, ID, MS, TH, ZH, KO, JA).

### Changed
- **Startup Time Optimization (~40s Ã¢â€ â€™ ~3s to Chat-Ready)**: (1) HeartbeatService now waits 30s before first beat, preventing startup blocking. (2) SentenceTransformer embedding model pre-loads in a background thread via `warmup()`. (3) `AgentLoop.run()` kicks off `_warmup_memory()` as a non-blocking background task. Telegram is now chat-ready in ~3s instead of ~40s.
- **Zero-Latency Cold Start**: Migrated heavy LLM libraries (`litellm`, etc.) to lazy-loading scopes, dropping CLI startup time to `< 0.7s`.
- **Asynchronous BM25 Indexing**: Deferred the synchronous `BM25Okapi` indexing to trigger only upon the first explicit user `search()`, removing background startup blocking.
- **SQLite Database Tuning**: Injected PRAGMA `WAL`, `synchronous=NORMAL`, and Memory-Mapped IO pragmas to `sqlite_store.py` to massively speed up asynchronous `EpisodicExtractor` writes without locking the read loop.

## [0.5.0] - 2026-02-22

### Added - Hybrid Memory Architecture (Exceeds Mem0)

- **HybridMemoryManager:** Modular memory orchestrator replacing monolithic `ChromaMemoryManager`.
- **Smart Router:** Query-intent classifier routes to correct memory store (episodic/knowledge/hybrid). Multilingual keyword matching for 8 languages (ID, EN, ES, FR, JA, ZH, KO, TH).
- **Reranker:** Three-stage filtering pipeline with configurable threshold (Ã¢â€°Â¥0.6), top-k (3), and hard token guard (500 tokens max). Reduces token injection by 60-72%.
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
- **Cron Ã¢â€ â€™ System Events:** Cron callbacks now emit system events so the agent can react to scheduled job completions.
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
  - Extended relative-time parsing in `kabot/cron/parse.py` for `minit`, Thai units, and Chinese units (e.g. `Ã¥Ë†â€ Ã©â€™Å¸Ã¥ÂÅ½`).
  - Improved weather location extraction for mixed queries (`tanggal + suhu` / `right now`) so city parsing no longer keeps noise tokens like `berapa` or `right`.
- Fixed root weather-tool failure mode for noisy LLM tool arguments:
  - `WeatherTool` now normalizes incoming `location` text before fetch (`suhu di cilacap sekarang` -> `Cilacap`).
  - Weather location normalization now strips trailing city descriptors (`kota`, `city`, `kabupaten`, etc.) to improve geocoding compatibility.
  - For `simple` mode, weather retrieval now prefers Open-Meteo first (structured current weather) and uses wttr as fallback.
  - Added safer request handling (`quote_plus`, explicit User-Agent, redirect handling) and cleaner error diagnostics.
  - Added support for `png` output mode as URL passthrough for wttr.
- Improved weather reply quality to be more human-care oriented and actionable:
  - `WeatherTool` now appends a practical care tip based on parsed temperature + condition (heat/cold/rain/storm/fog), e.g. sunscreen, hydration, jacket, umbrella.
  - Added explicit extreme-heat tier (`>=36Ã‚Â°C`) with stronger heatstroke caution and midday outdoor activity guidance.
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
  - New approval turns in chat/gateway sessions using approval IDs carried by the runtime queue.
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

**Kabot Parity: 85% Ã¢â€ â€™ 100% (COMPLETE)**

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

**Kabot Parity: 65% Ã¢â€ â€™ 85% (ACTUALLY ACHIEVED)**

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



