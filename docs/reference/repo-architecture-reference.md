# reference platform Repo Reference

This document is a structural map of the reference platform repository at:

`C:\Users\Arvy Kairi\Desktop\bot\reference-repo`

It is based on direct inspection of the repository layout and a hand-audit of the highest-signal folders and files. The repo currently contains more than 5,000 files, so this guide focuses on:

- every important top-level folder
- the purpose of the main subtrees
- the root files that define behavior
- the key runtime files that explain how reference platform feels "AI-driven"
- the bootstrap/persona/template files that shape first-run behavior

This is not a literal line-by-line paraphrase of all 5,268 files. It is a careful repo map meant to help a developer quickly understand what each major folder is for and where to read next.

## 1. At a Glance

reference platform is a large TypeScript/Node monorepo for a personal AI assistant platform. The repository combines:

- the agent/runtime core
- a websocket gateway and control plane
- many channel adapters (Telegram, Slack, Discord, WhatsApp, Signal, etc.)
- a browser-control subsystem
- a control UI built with Vite + Lit
- mobile/desktop app surfaces
- a workspace bootstrap system (`SOUL.md`, `IDENTITY.md`, `USER.md`, etc.)
- a skill system with bundled, managed, and workspace-local skills
- docs, onboarding, wizard, install, and operational tooling

Important high-level technologies visible from the repo:

- TypeScript/Node runtime
- Vite + Lit for the control UI
- CLI-heavy architecture with many operational commands
- skill-first prompt/runtime behavior
- gateway-first control-plane design

## 2. Root of `reference-repo/`

### Main top-level folders

- `apps/`: platform application shells and shared app code for mobile/desktop experiences.
- `assets/`: static assets used by the project outside docs-specific assets.
- `docs/`: documentation source for the public docs site and deep reference material.
- `extensions/`: extension-related material and support files.
- `git-hooks/`: repository git hook scripts.
- `packages/`: small publishable/support packages that live beside the main app.
- `patches/`: package patches or dependency patch files.
- `scripts/`: automation and maintenance scripts for development and release workflows.
- `skills/`: bundled skills that ship with reference platform.
- `src/`: the main product source tree; this is the most important folder in the repo.
- `Swabble/`: a separate top-level subtree; likely a related app or experimental surface.
- `ui/`: the control UI frontend source (dashboard/web control surface).
- `vendor/`: vendored external code or bundled third-party assets.

### Important root files

- `README.md`: main project overview, install paths, supported channels, architecture summary, and links to docs.
- `CHANGELOG.md`: release history.
- `VISION.md`: product and architecture direction.
- `package.json`: monorepo package metadata, scripts, exports, and build entry points.
- `pnpm-lock.yaml`: lockfile.
- `pnpm-workspace.yaml`: workspace definition for the monorepo.
- `reference-repo.mjs`: likely the executable/bootstrap entry used by the CLI binary.
- `Dockerfile`, `Dockerfile.gateway`, `Dockerfile.min`, `Dockerfile.nix`: containerized runtime/install variants.
- `tsconfig.json` and related `tsconfig.*`: TypeScript build/test configuration.
- `vitest*.config.ts`: test runner configuration for different suites.
- `AGENTS.md`: repo-specific instructions for coding agents.
- `SECURITY.md`: security policy and reporting guidance.
- `CLAUDE.md`, `GEMINI.md`: editor/assistant-facing helper docs.
- `LICENSE`: license file.

## 3. `docs/` - Documentation Source

`docs/` is the authored documentation tree that powers the reference platform's public docs and reference material.

### What `docs/` is for

This folder is not just marketing docs. It is a live product manual covering:

- install/onboarding
- channels
- tools
- gateway behavior
- architecture concepts
- platform guides
- security
- debugging and diagnostics
- refactor notes
- public reference content

### Root files inside `docs/`

- `index.md`: main docs landing page.
- `docs.json`: docs-site metadata/config input.
- `pi.md`: documentation for the Pi agent/runtime concepts.
- `tts.md`: text-to-speech related documentation.
- `logging.md`: logging behavior and ops notes.
- `style.css`: docs styling.

### Main `docs/` subfolders

- `.i18n/`: translation/i18n documentation support.
- `assets/`: images, logos, sponsor graphics, visual assets used by docs.
- `automation/`: cron jobs, webhook, and automation docs.
- `channels/`: channel-specific docs (Telegram, Slack, WhatsApp, etc.).
- `cli/`: CLI docs.
- `concepts/`: architecture and runtime concepts (sessions, models, streaming, etc.).
- `debug/`: debugging-specific documentation.
- `design/`: design notes or product/system design documents.
- `diagnostics/`: operator/developer diagnostics reference.
- `experiments/`: experimental docs.
- `gateway/`: gateway/control-plane docs.
- `help/`: FAQ and troubleshooting.
- `images/`: image assets used in docs pages.
- `install/`: installation, upgrade, Docker, Nix, and setup guides.
- `ja-JP/`: Japanese localization docs.
- `nodes/`: docs for device/node capabilities.
- `platforms/`: macOS, iOS, Android, and other platform docs.
- `plugins/`: plugin system docs.
- `providers/`: provider/model docs.
- `refactor/`: refactor-oriented notes or historical architecture cleanup docs.
- `reference/`: low-level reference material, templates, and spec-like docs.
- `security/`: security guidance and threat-model-adjacent docs.
- `start/`: getting started, onboarding, showcase, and wizard docs.
- `tools/`: tool docs such as browser, skills, web tools, plugin tools, etc.
- `web/`: web UI / WebChat / control UI docs.

### `docs/reference/templates/` - Workspace Bootstrap Templates

This folder is one of the most important pieces in the reference platform's "alive" feeling. It defines the default workspace bootstrap files that get seeded into a user workspace.

Files present there:

- `AGENTS.md`
- `AGENTS.dev.md`
- `BOOT.md`
- `BOOTSTRAP.md`
- `HEARTBEAT.md`
- `IDENTITY.md`
- `IDENTITY.dev.md`
- `SOUL.md`
- `SOUL.dev.md`
- `TOOLS.md`
- `TOOLS.dev.md`
- `USER.md`
- `USER.dev.md`

What the key templates do:

- `BOOTSTRAP.md`: first-run ritual. It tells the newly awakened agent to talk naturally, learn its name/nature/vibe/emoji, learn who the user is, then update identity/user files and delete the bootstrap file when done.
- `SOUL.md`: persistent persona/boundary file. It tells the agent to be genuinely helpful, have opinions, avoid corporate filler, respect privacy, and treat the workspace files as memory.
- `TOOLS.md`: local setup cheat sheet. It is for user-specific device names, SSH aliases, TTS voice preferences, local infra names, and other environment-specific notes.
- `IDENTITY.md`: the agent's self-description file (name, creature, vibe, emoji, avatar).
- `USER.md`: the user's profile file (name, what to call them, timezone, notes, ongoing context).
- `HEARTBEAT.md`: simple periodic-check task file. It is intentionally empty by default and is used to define heartbeat tasks when needed.
- `AGENTS.md`: workspace-local agent instructions.

### Important docs worth reading first

If you want to understand how reference platform behaves before reading source code, these docs are especially important:

- `docs/tools/skills.md`: explains bundled/managed/workspace skills, precedence, gating, and ClawHub install/sync behavior.
- `docs/tools/web.md`: explains `web_search` and `web_fetch`, provider selection, setup hints, and when to use browser instead.
- `docs/start/getting-started*`: setup/onboarding flow.
- `docs/gateway/*`: gateway concepts and operator-facing behavior.
- `docs/concepts/*`: sessions, models, retry, streaming, usage, presence.

## 4. `src/` - Main Product Source Tree

`src/` is the heart of reference platform. It contains the actual runtime, tools, channel adapters, gateway, CLI, skill loader, browser control, routing, security, and supporting infrastructure.

### Root files in `src/`

The `src/` root also contains a handful of top-level files like:

- `entry.ts`
- `index.ts`
- `runtime.ts`
- `utils.ts`
- `version.ts`

These are typical package/runtime entry and shared-helper files.

### Top-level `src/` folders and what they contain

- `acp/`: ACP-related protocol or compatibility code.
- `agents/`: core agent runtime, prompt building, tools, workspace loading, skills, and execution behavior.
- `auto-reply/`: inbound message handling, triggers, command registry, reply orchestration, and chat dispatch logic.
- `browser/`: browser control subsystem.
- `canvas-host/`: canvas host/runtime support.
- `channels/`: shared channel abstractions and support code across messaging providers.
- `cli/`: CLI framework, command routing, helpers, and CLI runtime infrastructure.
- `commands/`: user-facing command implementations (`reference-repo agent`, `reference-repo status`, onboarding, doctor, setup, etc.).
- `compat/`: compatibility helpers and migration shims.
- `config/`: config schemas, parsing, and config-related logic.
- `context-engine/`: context assembly or context-processing layer.
- `cron/`: scheduled jobs and isolated agent runtime for cron-like triggers.
- `daemon/`: daemon/service support.
- `discord/`: Discord channel integration.
- `docs/`: code that interacts with docs or docs-specific runtime logic.
- `gateway/`: websocket/http control plane, control UI server, server methods, and runtime management.
- `hooks/`: hook system support.
- `i18n/`: localization/internationalization support.
- `imessage/`: iMessage-specific integration.
- `infra/`: infrastructure helpers like path guards, home dir, boundary reads, etc.
- `line/`: LINE integration.
- `link-understanding/`: link parsing/understanding logic.
- `logging/`: structured logging and subsystem loggers.
- `markdown/`: markdown formatting/rendering helpers.
- `media/`: media processing helpers.
- `media-understanding/`: media analysis or interpretation support.
- `memory/`: memory-related runtime code.
- `node-host/`: node/device host support.
- `pairing/`: pairing code and identity handshake behavior.
- `plugin-sdk/`: plugin SDK exports and runtime interfaces.
- `plugins/`: plugin runtime support.
- `process/`: process execution helpers.
- `providers/`: provider-specific model or service integrations.
- `routing/`: session and route resolution logic.
- `scripts/`: runtime-internal scripts/helpers.
- `secrets/`: secret resolution and runtime secret plumbing.
- `security/`: security checks, policy, and related enforcement.
- `sessions/`: session persistence and session mechanics.
- `shared/`: cross-cutting shared utilities/types.
- `signal/`: Signal integration.
- `slack/`: Slack integration.
- `telegram/`: Telegram integration.
- `terminal/`: terminal-specific behaviors/utilities.
- `test-helpers/`: reusable test scaffolding.
- `test-utils/`: reusable test utility helpers.
- `tts/`: text-to-speech support.
- `tui/`: terminal UI support.
- `types/`: shared types.
- `utils/`: generic reusable utilities.
- `web/`: web-facing helpers or HTTP/web runtime logic.
- `whatsapp/`: WhatsApp integration.
- `wizard/`: onboarding/setup wizard logic.

## 5. `src/agents/` - Agent Runtime Core

This is one of the most important subtrees in the entire repo. It contains the runtime behavior that makes reference platform feel like a persistent personal assistant rather than a stateless chatbot.

### What `src/agents/` contains

The folder includes:

- workspace bootstrap and template loading
- system prompt construction
- tool catalog / tool policy
- bash/exec tools
- skill loading and skill installation
- model selection and failover
- subagent registry and subagent lifecycle
- sandbox/runtime path policy
- transcript/session protection helpers
- embedded agent runner logic

### Especially important files in `src/agents/`

- `workspace.ts`: resolves default workspace paths, defines bootstrap file names, loads/seeds workspace files, and tracks onboarding completion.
- `workspace-templates.ts`: finds and resolves the bootstrap template directory.
- `bootstrap-files.ts`: controls which bootstrap files are loaded into prompt context.
- `system-prompt.ts`: builds the central system prompt. This is where skills are described and where runtime messaging/tool guidance is injected.
- `reference-tools.ts`: assembles the main tool surface exposed to the agent.
- `skills.ts`: skill loading/runtime-facing skill composition.
- `skills-install.ts`, `skills-install-download.ts`, `skills-install-extract.ts`, `skills-status.ts`: installation and lifecycle utilities for managed skills.
- `context.ts`: agent context assembly.
- `memory-search.ts`: memory retrieval integration.
- `pi-embedded-runner.ts` and related `pi-embedded-*`: the embedded agent runner and tool/message streaming behavior.
- `tool-policy.ts`, `tool-loop-detection.ts`, `tool-catalog.ts`: control how tools are described and safeguarded.
- `bash-tools.*`: exec/process/approval machinery for shell-based execution.
- `subagent-*`: subagent lifecycle, registry, and orchestration.

### What `workspace.ts` is doing

Direct inspection shows `workspace.ts` defines canonical workspace file names like:

- `AGENTS.md`
- `SOUL.md`
- `TOOLS.md`
- `IDENTITY.md`
- `USER.md`
- `HEARTBEAT.md`
- `BOOTSTRAP.md`
- `MEMORY.md`

It also:

- resolves the default workspace under `~/.reference-repo/workspace` (or `workspace-<profile>`)
- loads templates from `docs/reference/templates`
- strips frontmatter from template content before seeding
- writes files if missing
- stores onboarding state in `.reference-repo/workspace-state.json`

This is the core of the reference platform's first-run workspace behavior.

### What `system-prompt.ts` is doing

Direct inspection shows the prompt builder includes explicit sections such as:

- skills
- memory recall
- authorized senders
- reply tags
- messaging rules
- docs lookup hints
- tool summaries

The most important bit for parity work is the skills contract:

- scan available skills
- if exactly one clearly applies, read its `SKILL.md`
- if multiple apply, choose the most specific one
- if none clearly apply, do not read any skill

That is a major reason reference platform feels skill-first without needing language-specific parsers.

### `src/agents/skills/workspace.ts`

This file is the runtime skill loader for workspace/managed/bundled skills. Direct inspection shows it handles:

- skill loading from multiple roots
- precedence rules
- frontmatter parsing
- eligibility gating (`requires.bins`, `requires.env`, config gates)
- skill command name sanitization
- prompt formatting for available skills

This file is central to understanding why reference platform can be highly customizable and still keep skill loading disciplined.

## 6. `src/auto-reply/` - Inbound Message and Reply Orchestration

This subtree is responsible for taking inbound messages and turning them into routed assistant behavior.

### What is here

- command detection
- command registry
- reply dispatching
- heartbeat reply behavior
- trigger handling
- reply payload building
- skill-command registration
- status/thinking behavior

### Important files

- `commands-registry.ts`: registry of native commands.
- `commands-registry.data.ts`: command data/spec content.
- `skill-commands.ts`: bridges skills into user-invocable commands.
- `heartbeat.ts`: heartbeat reply flow.
- `reply.ts`: top-level reply pipeline.
- `dispatch.ts`: dispatch logic.
- `status.ts`: reply status handling.
- `thinking.ts`: thinking/reasoning support.
- `send-policy.ts`: send behavior rules.
- `command-detection.ts`: command parsing/detection.

### Why this subtree matters

This is where reference platform starts to feel interactive and channel-aware. It is the layer between "a message came in" and "run the agent with the right context, route, and command surface."

## 7. `src/telegram/` - Telegram Runtime

`src/telegram/` contains one of the clearest examples of how reference platform bridges the generic agent runtime into a specific channel.

### What it includes

- bot startup and provider wiring
- message context/session extraction
- native command registration
- reply threading
- approval buttons
- delivery state
- draft/reasoning stream support
- send and webhook handling

### Important files

- `bot.ts`: Telegram provider bootstrap.
- `bot-handlers.ts`: inbound update handlers and message dispatch.
- `bot-native-commands.ts`: native Telegram command registration/sync.
- `bot-native-command-menu.ts`: Telegram command menu behavior.
- `bot-message-context.ts` and related files: message/session context extraction.
- `conversation-route.ts`: Telegram conversation routing.
- `send.ts`: low-level message sending.
- `lane-delivery.ts`: lane-specific delivery logic.
- `reasoning-lane-coordinator.ts`: coordinating reasoning/draft behavior in Telegram.
- `approval-buttons.ts`: interactive approval UI.
- `exec-approvals.ts`: approval flow integration.
- `draft-stream.ts`: streaming preview/draft output.
- `thread-bindings.ts`: reply/thread bindings.
- `webhook.ts`: webhook support.

### What this tells you about reference platform

the reference platform's Telegram behavior is not an afterthought. Telegram gets:

- native slash commands
- reply/thread semantics
- draft/reasoning handling
- approval UI
- lane-aware delivery state

That is why the Telegram experience feels deeper than a thin bot wrapper.

## 8. `src/gateway/` - Control Plane and Server Runtime

`src/gateway/` is the control-plane backbone of reference platform.

### Main responsibilities

- websocket server runtime
- HTTP endpoints
- control UI serving
- auth and rate limiting
- session/server management
- channel health and startup
- node registry and node invocation support
- server methods exposed to clients
- gateway startup and reload behavior

### Notable folders

- `protocol/`: protocol definitions/types.
- `server/`: server implementation pieces.
- `server-methods/`: discrete server method handlers.

### High-signal files

- `server.ts`, `server.impl.ts`: gateway server implementation entrypoints.
- `server-http.ts`: HTTP serving layer.
- `server-ws-runtime.ts`: websocket runtime.
- `server-startup.ts`, `server-startup-log.ts`: startup orchestration and logging.
- `server-methods.ts`, `server-methods-list.ts`: exported method surface.
- `control-ui.ts`: serves or integrates the control UI.
- `agent-prompt.ts`: gateway-side agent prompt shaping support.
- `exec-approval-manager.ts`: exec approval coordination.
- `server-session-key.ts`: session key handling.
- `server-node-events.ts`: node event streaming.
- `server-channels.ts`: channel integration at the gateway layer.
- `auth.ts`, `auth-rate-limit.ts`, `connection-auth.ts`: auth/security policies.
- `server-browser.ts`: browser integration inside the gateway runtime.

### Why `src/gateway/` matters

This is what makes reference platform feel like a product rather than only a CLI. The gateway is the long-lived control plane that ties together:

- channels
- the control UI
- agent sessions
- browser/canvas/nodes
- remote clients
- auth and pairing

## 9. `src/cli/` - CLI Framework and Plumbing

`src/cli/` is where the CLI plumbing lives.

### What is here

- argv parsing helpers
- command routing and formatting
- specialized CLI surfaces for browser, channels, docs, memory, gateway, daemon, nodes, skills, update, security, etc.
- shared CLI utilities and completion scripts

### Important files

- `program.ts`: main CLI program composition.
- `run-main.ts`: CLI execution entry.
- `route.ts`: command routing.
- `argv.ts`: argument handling.
- `help-format.ts`: help rendering.
- `skills-cli.ts`: skill-related CLI surface.
- `gateway-cli.ts`: gateway-specific CLI surface.
- `channels-cli.ts`: channel command support.
- `browser-cli.ts`: browser command surface.
- `memory-cli.ts`: memory commands.
- `daemon-cli.ts`: daemon control.
- `update-cli.ts`: update behavior.
- `docs-cli.ts`: docs-related commands.
- `plugins-cli.ts`: plugin commands.
- `exec-approvals-cli.ts`: approval management.
- `completion-*`: shell completion support.

### CLI design pattern

reference platform separates CLI framework (`src/cli/`) from end-user command logic (`src/commands/`). That keeps command wiring and command implementation from being tangled together.

## 10. `src/commands/` - End-User Command Implementations

This folder contains the concrete implementations behind user-facing commands such as:

- `reference-repo agent`
- `reference-repo status`
- `reference-repo doctor`
- `reference-repo setup`
- `reference-repo onboard`
- channel setup/config flows
- daemon install/runtime flows
- gateway status and dashboard flows
- skills, sessions, backups, sandbox, uninstall, etc.

### Why it is large

reference platform ships a lot of operational product surface through the CLI, so this folder effectively contains a big chunk of the product's operator interface.

### Key clusters

- `agent/`: agent command behavior.
- `channels/`: channel-oriented command surfaces.
- `gateway-status/`: gateway status outputs.
- `models/`: model command surfaces.
- `onboarding/` and `onboard-*`: onboarding wizard logic.
- `status-*`: rich status computation and formatting.
- `doctor-*`: diagnostics and health checks.
- `configure*`: configuration flows.

### Especially high-signal files

- `agent.ts`: direct agent CLI entry behavior.
- `dashboard.ts`: dashboard-related command/runtime glue.
- `doctor.ts`: umbrella doctor workflow.
- `status.ts`: status command entry behavior.
- `setup.ts`: main setup entry.
- `configure.ts`: config wizard/interactive flows.
- `onboard.ts`: onboarding orchestration.
- `channels.ts`: channels command surface.
- `models.ts`: models command surface.

## 11. `ui/` - Control UI Frontend

`ui/` is the standalone frontend package for the reference platform control UI.

### Root UI files

- `package.json`: defines a Vite + Lit frontend package called `reference-control-ui`.
- `vite.config.ts`: build config.
- `vitest.config.ts`: browser/frontend tests.
- `vitest.node.config.ts`: node-side tests for the frontend package.
- `index.html`: frontend HTML entry.
- `public/`: static public assets.
- `src/`: main frontend source.

### What `ui/package.json` tells us

Direct inspection shows the UI uses:

- `lit`
- `@lit/context`
- `@lit-labs/signals`
- `marked`
- `dompurify`
- `vite`
- `vitest`
- `playwright`

So this is a modern web frontend based on Lit rather than React/Vue.

### `ui/src/`

First-level structure:

- `i18n/`: UI localization support.
- `styles/`: style layer.
- `ui/`: most of the actual control UI code.
- `main.ts`: main frontend entry.
- `styles.css`: global stylesheet.
- `css.d.ts`: CSS type support.

### `ui/src/ui/`

This is the actual application UI layer.

First-level folders:

- `chat/`: chat/event presentation helpers.
- `components/`: reusable UI components.
- `controllers/`: stateful UI controllers and data fetch/control logic.
- `data/`: packaged UI data or static data helpers.
- `test-helpers/`: UI test support.
- `types/`: UI type definitions.
- `views/`: major rendered views/panels.
- `__screenshots__/`: screenshot artifacts or snapshot images.

Important top-level files in `ui/src/ui/`:

- `app.ts`: main UI app composition.
- `app-gateway.ts`: gateway connectivity layer.
- `app-chat.ts`: chat-facing app behavior.
- `app-settings.ts`: settings UI behavior.
- `app-lifecycle.ts`: app init/lifecycle state.
- `app-render.ts`: rendering orchestration.
- `app-view-state.ts`: view state handling.
- `app-tool-stream.ts`: tool stream rendering logic.
- `assistant-identity.ts`: assistant identity display in UI.
- `navigation.ts`: navigation behavior.
- `markdown.ts`: markdown rendering in the UI.
- `tool-display.ts`: tool result presentation.
- `theme.ts` and `theme-transition.ts`: theming behavior.
- `storage.ts`: local UI persistence.

### `ui/src/ui/chat/`

This is a utility-heavy chat rendering subtree. Direct inspection shows files such as:

- `constants.ts`
- `copy-as-markdown.ts`
- `grouped-render.ts`
- `message-extract.ts`
- `message-normalizer.ts`
- `tool-cards.ts`
- `tool-helpers.ts`

This suggests the reference platform's UI chat surface does not just dump raw events; it has a dedicated normalization/render pipeline for messages and tool cards.

### `ui/src/ui/components/`

Direct inspection currently shows:

- `resizable-divider.ts`

This looks like a small reusable component layer, with much of the UI behavior living in controllers/views instead.

### `ui/src/ui/controllers/`

This is a key layer that bridges gateway data into the UI. Direct inspection shows controllers for:

- agents
- agent identity/files/skills
- channels
- chat
- config
- control UI bootstrap
- cron
- debug
- devices
- exec approvals
- logs
- nodes
- presence
- sessions
- skills
- usage

This is a strong sign that the control UI is not merely presentational; it actively models backend subsystems as first-class controllers.

### `ui/src/ui/views/`

This is the view/panel layer. Direct inspection shows files for:

- agents panels
- channels config views
- chat
- config form rendering
- cron
- debug
- exec approval view
- overview
- logs
- nodes
- sessions
- skills
- usage

This matches the product: the control UI is an operator console for channels, sessions, skills, logs, usage, and approvals.

## 12. `skills/` - Bundled Skills

This folder contains bundled skill directories that ship with reference platform. These are not generic docs; they are operational prompt assets that teach the agent how to use tools/workflows.

Direct inspection shows bundled skills including:

- `1password`
- `apple-notes`
- `apple-reminders`
- `bear-notes`
- `blogwatcher`
- `blucli`
- `bluebubbles`
- `camsnap`
- `canvas`
- `clawhub`
- `coding-agent`
- `discord`
- `eightctl`
- `gemini`
- `gh-issues`
- `gifgrep`
- `github`
- `gog`
- `goplaces`
- `healthcheck`
- `himalaya`
- `imsg`
- `mcporter`
- `model-usage`
- `nano-banana-pro`
- `nano-pdf`
- `notion`
- `obsidian`
- `openai-image-gen`
- `openai-whisper`
- `openai-whisper-api`
- `openhue`
- `oracle`
- `ordercli`
- `peekaboo`
- `sag`
- `session-logs`
- `sherpa-onnx-tts`
- `skill-creator`
- `slack`
- `songsee`
- `sonoscli`
- `spotify-player`
- `summarize`
- `things-mac`
- `tmux`
- `trello`
- `video-frames`
- `voice-call`
- `wacli`
- `weather`
- `xurl`

### What this folder means architecturally

This is where reference platform gets much of its "customizable but still disciplined" behavior. The system prompt points the model toward skills, but the skills themselves live here as local instructions and supporting assets.

## 13. `apps/` - Platform App Shells

Direct inspection shows:

- `android/`
- `ios/`
- `macos/`
- `shared/`

This indicates reference platform ships or supports dedicated platform applications, with shared app code separated out for reuse.

`apps/shared/` currently contains `reference platformKit/`, which looks like a shared platform/application kit.

## 14. `packages/` - Side Packages

Direct inspection shows two packages:

- `clawdbot/`
- `moltbot/`

Each currently contains at least:

- `index.js`
- `package.json`
- `scripts/`

These look like smaller adjacent packages or integration packages maintained inside the same monorepo.

## 15. Other Top-Level Folders

### `assets/`

General repository assets outside the docs-specific asset tree.

### `extensions/`

Likely browser/editor/runtime extension-related material.

### `git-hooks/`

Local git hook scripts used by the repo.

### `patches/`

Dependency patch files or patched-package support, likely used with a patching workflow.

### `scripts/`

Repository automation scripts for building, release, sync, maintenance, or tooling support.

### `vendor/`

Vendored third-party code or assets.

### `Swabble/`

A distinct subtree that likely contains a related app, experiment, or integration surface. It is notable because it sits at the top level rather than being tucked into `apps/` or `packages/`.

## 16. `src/browser/` - Browser Control Subsystem

`src/browser/` is a full browser-control subsystem, not a thin helper around Playwright. It includes browser server startup, auth, profile management, CDP helpers, screenshot handling, tab/session state, route registration, and agent-facing browser actions.

### What it contains

Direct inspection shows files for:

- CDP helpers and timeouts
- Chrome executable/profile handling
- control service auth
- extension relay
- profile capability tracking
- Playwright session state
- screenshot/output helpers
- server lifecycle and middleware
- route dispatch and per-route action handlers

### Important files

- `server.ts`: starts the browser control HTTP server, installs middleware, ensures browser auth, and registers routes.
- `control-service.ts`: service-level browser control runtime.
- `control-auth.ts`: browser control auth behavior.
- `chrome.ts`, `chrome.executables.ts`, `chrome.profile-decoration.ts`: Chrome/Chromium discovery and profile behavior.
- `cdp.ts` and `cdp.helpers.ts`: low-level Chrome DevTools Protocol support.
- `profiles.ts`, `profiles-service.ts`: profile handling.
- `screenshot.ts`: screenshot creation/output support.
- `pw-session.ts` and `pw-tools-core.*`: Playwright session/tool behavior.
- `server-context.ts`: server-side browser context and selection state.
- `runtime-lifecycle.ts`: browser runtime lifecycle.

### `src/browser/routes/`

This folder contains route/action handlers used by the browser control server. Direct inspection shows route files such as:

- `agent.ts`
- `agent.act.ts`
- `agent.act.download.ts`
- `agent.snapshot.ts`
- `agent.storage.ts`
- `tabs.ts`
- `dispatcher.ts`
- `basic.ts`

This suggests the browser subsystem is exposed through a dedicated internal HTTP API with explicit route handlers for agent actions, snapshots, downloads, tabs, and storage.

## 17. `src/channels/` - Shared Channel Runtime Layer

`src/channels/` is the shared abstraction layer that sits above individual channel implementations like Telegram or Slack.

### What it handles

- channel registry and metadata
- allowlists / sender filtering
- mention and command gating
- session envelope helpers
- typing lifecycle
- native command targeting
- thread binding policy
- inbound debounce behavior
- shared run-state machine behavior

### Important files

- `registry.ts`: defines core chat channel order, aliases, metadata, and normalization helpers.
- `channel-config.ts`: shared config conventions.
- `command-gating.ts`: controls when commands are allowed.
- `mention-gating.ts`: mention/reply-based gating.
- `session.ts`, `session-meta.ts`, `session-envelope.ts`: session packaging.
- `targets.ts`: target resolution helpers.
- `typing.ts`, `typing-lifecycle.ts`, `typing-start-guard.ts`: typing indicator behavior.
- `reply-prefix.ts`: reply-format helpers.
- `run-state-machine.ts`: shared runtime state transitions.

### Subfolders

- `allowlists/`: allowlist support.
- `plugins/`: channel plugin interface layer.
- `telegram/`: Telegram-specific shared channel plugin support.
- `transport/`: transport-level helpers.
- `web/`: web-channel/shared web delivery helpers.

### Specific notable subfolders

`src/channels/transport/` currently contains `stall-watchdog.ts`, which suggests transport health monitoring / stuck send detection.

`src/channels/telegram/` currently contains:

- `allow-from.ts`
- `api.ts`

This suggests there is a Telegram-specific shared adapter layer here, while most Telegram runtime behavior still lives under `src/telegram/`.

## 18. `src/plugin-sdk/` - Plugin and External Integration SDK

`src/plugin-sdk/` is the exported SDK surface for plugin/channel integrators.

### What it exposes

Direct inspection of `index.ts` shows it re-exports:

- channel plugin types and helpers
- ACP runtime types and registry
- plugin runtime/service interfaces
- gateway request handler types
- runtime logger and subagent runtime types
- config helpers
- webhook guards and target registration
- allowlist resolution helpers
- channel send helpers
- runtime store helpers
- channel metadata helpers
- many channel/provider-specific runtime types

### Why this matters

This folder is what makes reference platform extensible without requiring every extension to reach into internal source folders directly. It is effectively a public or semi-public developer surface for:

- channel plugins
- webhook integrations
- plugin HTTP routes
- runtime services
- provider auth flows
- channel send/result helpers

## 19. `src/memory/` - Memory and Retrieval Engine

`src/memory/` is a substantial subsystem, not a single embedding helper.

### What it contains

Direct inspection shows support for:

- embeddings across multiple providers
- batch embedding flows
- SQLite and sqlite-vec support
- hybrid retrieval
- query expansion
- temporal decay
- MMR
- manager/search orchestration
- session file indexing
- remote embedding/fetch providers

### Important files

- `manager.ts`: core memory manager / index manager orchestration.
- `manager-search.ts`: search operations.
- `manager-embedding-ops.ts`: embedding operations.
- `embeddings.ts`: embedding provider abstraction.
- `embeddings-openai.ts`, `embeddings-gemini.ts`, `embeddings-voyage.ts`, `embeddings-mistral.ts`, `embeddings-ollama.ts`: provider-specific embeddings.
- `hybrid.ts`: hybrid retrieval merging.
- `query-expansion.ts`: query keyword expansion.
- `sqlite.ts`, `sqlite-vec.ts`: database/index storage.
- `session-files.ts`: memory over session files.
- `search-manager.ts`: search manager orchestration.
- `status-format.ts`: memory status output formatting.

### What `manager.ts` tells us

Direct inspection shows `manager.ts` builds a cached `MemoryIndexManager` keyed by agent/workspace/settings, resolves embedding providers, opens the database, tracks watcher/session sync state, and orchestrates retrieval/search behavior. This is a serious subsystem rather than a convenience feature.

## 20. `src/providers/` - Provider-Specific Auth and Model Integrations

`src/providers/` is relatively compact compared with `src/agents/`, but it is important because it contains provider-specific auth/model glue.

Direct inspection shows files such as:

- `github-copilot-auth.ts`
- `github-copilot-models.ts`
- `github-copilot-token.ts`
- `google-shared.test-helpers.ts`
- `kilocode-shared.ts`
- `qwen-portal-oauth.ts`

This folder appears to contain provider-specific code that does not fit cleanly inside the generic agent runtime or config system.

## 21. `src/wizard/` - Interactive Onboarding and Setup Flow

`src/wizard/` is the interactive setup and onboarding engine behind the CLI wizard experience.

### Important files

- `onboarding.ts`: core onboarding wizard flow.
- `onboarding.finalize.ts`: completion/finalization behavior.
- `onboarding.gateway-config.ts`: gateway config shaping during onboarding.
- `onboarding.secret-input.ts`: secure input handling.
- `onboarding.types.ts`: types used by the wizard.
- `clack-prompter.ts`: terminal prompt/presenter implementation.
- `prompts.ts`: prompt helpers and cancellation types.
- `session.ts`: wizard session state.

### What `onboarding.ts` tells us

Direct inspection shows the wizard:

- prints a wizard header
- performs a security/risk acknowledgement
- reads existing config snapshots
- can reuse, modify, or reset existing config
- supports `quickstart` vs `advanced/manual` flows
- coordinates gateway defaults and runtime config decisions

That explains why onboarding in reference platform feels like a real product wizard rather than a few setup prompts bolted onto the CLI.

## 22. `src/web/` - Web Channel and Web-Facing Runtime

`src/web/` is the web-facing runtime subtree, not to be confused with the `ui/` frontend package.

### What it contains

Direct inspection shows:

- `auto-reply/`
- `inbound/`
- account/login helpers
- session handling
- outbound/media helpers
- reconnect/login/QR helpers

### Important files

- `auto-reply.ts` / `auto-reply.impl.ts`: auto-reply orchestration for web-facing delivery.
- `inbound.ts`: inbound message handling.
- `outbound.ts`: outbound send behavior.
- `login.ts`, `login-qr.ts`, `qr-image.ts`: web login and QR flows.
- `session.ts`: web session handling.
- `media.ts`: media handling.
- `reconnect.ts`: reconnection behavior.

### Subfolders

`src/web/auto-reply/` includes files such as:

- `deliver-reply.ts`
- `heartbeat-runner.ts`
- `mentions.ts`
- `monitor.ts`
- `session-snapshot.ts`

This indicates a mini reply runtime specifically for web-facing delivery/monitoring.

`src/web/inbound/` includes files such as:

- `access-control.ts`
- `dedupe.ts`
- `extract.ts`
- `media.ts`
- `monitor.ts`
- `send-api.ts`

This suggests the web channel has explicit inbound extraction, access control, deduplication, and send API wiring.

## 23. Channel-Specific Runtime Subtrees

reference platform does not hide all channel behavior behind one generic adapter. Several channels have their own substantial runtime subtree, which is part of why the product feels native on each surface.

### `src/slack/`

Direct inspection shows:

- subfolders: `http/`, `monitor/`
- files for actions, blocks input/fallback, draft stream, threading, token/scopes, send, targets, channel migration, and user/channel resolution

Important responsibilities visible from file names:

- Slack-specific send path
- channel/user resolution
- block-based UI fallback
- streaming and threading support
- HTTP integration surface
- monitoring/runtime event handling

Notable files:

- `send.ts`
- `threading.ts`
- `draft-stream.ts`
- `message-actions.ts`
- `scopes.ts`
- `resolve-channels.ts`
- `resolve-users.ts`

### `src/discord/`

Direct inspection shows:

- subfolders: `monitor/`, `voice/`
- files for send pipelines, component handling, guild/channel resolution, mentions, exec approvals, draft chunking/streaming, voice message support, UI helpers, and monitor gateway wiring

This indicates Discord is treated as a deep native integration, not just a text transport.

Notable files:

- `send.ts`
- `send.messages.ts`
- `send.reactions.ts`
- `send.components.ts`
- `mentions.ts`
- `guilds.ts`
- `draft-stream.ts`
- `voice-message.ts`
- `monitor.ts`
- `ui.ts`

`src/discord/monitor/` is especially dense and appears to contain the Discord-side monitoring, provider lifecycle, inbound worker/message-handler pipeline, command handling, presence, typing, threading, and route resolution machinery.

### `src/signal/`

Direct inspection shows:

- subfolder: `monitor/`
- files for daemon/client integration, identity, SSE reconnect, reaction sending, monitor flow, RPC context, and send logic

This suggests Signal support is mediated through a daemon/client model with reconnect-aware monitoring.

Notable files:

- `client.ts`
- `daemon.ts`
- `identity.ts`
- `monitor.ts`
- `send.ts`
- `send-reactions.ts`
- `sse-reconnect.ts`

`src/signal/monitor/` currently contains:

- `access-policy.ts`
- `event-handler.ts`
- `mentions.ts`

which points to a narrower but explicit monitor/event layer for Signal.

### `src/imessage/`

`src/imessage/` has a medium-sized dedicated subtree focused on iMessage-specific monitoring and outbound safety.

Direct inspection shows files for:

- accounts and client runtime
- constants and targets
- outbound send helpers
- probe/monitor entrypoints
- target parsing helpers

It also has a rich `monitor/` subfolder with files such as:

- `monitor-provider.ts`
- `inbound-processing.ts`
- `parse-notification.ts`
- `deliver.ts`
- `sanitize-outbound.ts`
- `echo-cache.ts`
- `reflection-guard.ts`
- `loop-rate-limiter.ts`

This strongly suggests the iMessage integration is built around notification parsing and guarded monitor loops, rather than a simple direct API transport.

### `src/line/`

`src/line/` has its own substantial subtree with webhook/bot handling and LINE-specific rendering/send helpers.

Direct inspection shows files for:

- bot startup and handlers
- bot message context
- channel access token handling
- flex templates
- markdown-to-LINE conversion
- rich menu handling
- reply chunking
- webhook helpers
- send/monitor/probe logic

Notable files:

- `bot.ts`
- `bot-handlers.ts`
- `bot-message-context.ts`
- `markdown-to-line.ts`
- `flex-templates.ts`
- `rich-menu.ts`
- `send.ts`
- `monitor.ts`
- `webhook.ts`

This makes LINE one of the channel integrations with its own clearly defined runtime personality.

### `src/whatsapp/`

`src/whatsapp/` is intentionally small at the top level in this repo snapshot. Direct inspection shows only:

- `normalize.ts`
- `resolve-outbound-target.ts`

However, repo-wide inspection shows WhatsApp support is distributed across several places:

- `src/plugins/runtime/runtime-whatsapp*.ts`
- `src/channels/plugins/*whatsapp*.ts`
- `src/agents/tools/whatsapp-actions.ts`
- `src/agents/tools/whatsapp-target-auth.ts`
- `src/plugin-sdk/whatsapp.ts`
- `src/config/types.whatsapp.ts`

So WhatsApp is clearly a first-class capability, but its implementation is more spread across plugin/runtime/channel layers than concentrated in a dedicated `src/whatsapp/` subtree.

### `googlechat`

There is no large dedicated `src/googlechat/` subtree in the same style as `src/telegram/` or `src/slack/`.

Instead, repo inspection shows Google Chat appears through:

- `src/config/types.googlechat.ts`
- `src/plugin-sdk/googlechat.ts`
- broader shared channel/plugin infrastructure

That is an important design clue: reference platform mixes two patterns:

- some channels have deep dedicated runtime trees
- some channels live more through plugin/config/shared abstractions

That flexibility is part of the repo's overall shape.

## 24. Platform App Details

The `apps/` subtree is not just a placeholder. The platform directories show distinct native app projects and their own build toolchains.

### `apps/android/`

Direct inspection shows:

- `app/`
- `benchmark/`
- `gradle/`
- `scripts/`
- `THIRD_PARTY_LICENSES/`
- Gradle files and wrapper scripts

The `README.md` says the Android app is \"extremely alpha\" but already includes:

- a 4-step onboarding flow
- gateway connect tab
- encrypted persistence for gateway/auth state
- streaming chat UI
- QR scanning
- permission flows
- push notifications
- voice and screen tabs
- integration testing guidance

This is clearly a serious native Android node/client surface, not a demo app.

### `apps/ios/`

Direct inspection shows:

- `ActivityWidget/`
- `Config/`
- `fastlane/`
- `screenshots/`
- `ShareExtension/`
- `Sources/`
- `Tests/`
- `WatchApp/`
- `WatchExtension/`

The `README.md` describes the iOS app as \"super alpha\" and internal-use oriented, with manual Xcode deployment and a node-style role connecting to the reference platform Gateway.

The documented capabilities include:

- pairing via setup code
- gateway connection via discovery/manual host+port
- chat/talk surfaces
- iPhone node commands in foreground
- share extension forwarding
- location automation testing guidance

### `apps/macos/`

Direct inspection shows:

- `Sources/`
- `Tests/`
- `Package.swift`
- `Package.resolved`
- `README.md`

The README focuses on dev run, packaging, and code signing. This strongly suggests the macOS app is maintained as a Swift package/app target with careful signing and packaging workflows.

## 25. `src/commands/` - More About Agent and Channel Commands

Earlier sections described `src/commands/` broadly. Two concrete files are especially useful for understanding how the operator surface is organized:

### `src/commands/agent.ts`

Direct inspection shows this file pulls together:

- ACP session handling
- workspace resolution
- auth profile handling
- model fallback and model selection
- bootstrap warnings
- CLI session IDs
- skill snapshot building
- embedded Pi agent execution
- delivery back to channels/sessions
- session store updates

This file is a good example of the reference platform's architecture style: the command layer does not just shell out to a single runtime function. It orchestrates a large amount of policy and runtime state before calling the agent.

### `src/commands/channels.ts`

This file is a compact export barrel for channel-related commands. Direct inspection shows it re-exports concrete channel operations such as:

- `add`
- `capabilities`
- `list`
- `logs`
- `remove`
- `resolve`
- `status`

That confirms the CLI command surface for channels is modularized as many small focused implementations, rather than one giant command file.

## 26. `gateway/server-methods/` - RPC/Control Method Surface

Direct inspection of `src/gateway/server-methods/` shows a wide set of focused method files such as:

- `agent.ts`
- `agents.ts`
- `browser.ts`
- `channels.ts`
- `chat.ts`
- `cron.ts`
- `devices.ts`
- `doctor.ts`
- `exec-approval.ts`
- `logs.ts`
- `models.ts`
- `nodes.ts`
- `push.ts`
- `restart-request.ts`
- `secrets.ts`
- `send.ts`
- `sessions.ts`
- `skills.ts`
- `system.ts`
- `talk.ts`
- `tts.ts`
- `update.ts`
- `usage.ts`
- `voicewake.ts`
- `web.ts`
- `wizard.ts`

This is the backend method surface used by the gateway/control plane. It is a strong signal that reference platform treats the gateway as a structured RPC server, not just a raw websocket event pipe.

## 27. `packages/` - Additional Detail

Earlier we identified `clawdbot` and `moltbot` as side packages. Their `package.json` files make their purpose explicit:

- both are compatibility shims that forward to `reference-repo`
- both expose a dedicated bin:
  - `clawdbot`
  - `moltbot`
- both depend on `reference-repo` via `workspace:*`

So these packages are effectively alternate entry/compatibility wrappers rather than independent products.

## 28. More About Why reference platform Feels Native Instead of Parser-Heavy

Several structural clues reinforce the same conclusion:

- channel runtimes are deep and channel-native
- the gateway is persistent and event-driven
- the workspace bootstrap files are runtime artifacts, not decoration
- skills are loaded through explicit precedence and gating
- web/browser/fetch/search are separate capability surfaces
- native command systems are bridged per channel instead of everything being forced through one regex-heavy command parser

This helps explain why reference platform can feel flexible in multilingual chat without needing a visible language-specific parser layer for every domain.

## 29. Architecture Notes That Explain the reference platform's Feel

Several files explain why reference platform feels less parser-driven and more AI/skill-driven:

- `src/agents/system-prompt.ts`
  - tells the model to scan available skills first
  - only read a skill when one clearly applies
  - keeps the model in charge of natural-language understanding
- `src/agents/workspace.ts`
  - makes workspace bootstrap files real runtime state, not just docs
- `src/agents/skills/workspace.ts`
  - loads skill roots with precedence and gating
- `src/auto-reply/commands-registry.ts`
  - centralizes native command registry
- `src/auto-reply/skill-commands.ts`
  - turns skills into user-invocable commands when configured
- `src/telegram/bot-native-commands.ts`
  - bridges command registry into Telegram-native commands
- `docs/tools/web.md`
  - keeps `web_search`, `web_fetch`, and browser clearly separated as different capabilities

In other words, the reference platform's behavior is strongly shaped by:

- workspace files
- skill summaries and skill loading
- tool surfaces with clear boundaries
- channel-specific bridges
- less dependence on language-specific parsers

## 30. Suggested Reading Order for a Developer

If you need to understand the repo efficiently, a good reading order is:

1. `README.md`
2. `docs/tools/skills.md`
3. `docs/tools/web.md`
4. `docs/reference/templates/BOOTSTRAP.md`
5. `docs/reference/templates/SOUL.md`
6. `src/agents/workspace.ts`
7. `src/agents/system-prompt.ts`
8. `src/agents/skills/workspace.ts`
9. `src/agents/reference-tools.ts`
10. `src/auto-reply/commands-registry.ts`
11. `src/auto-reply/skill-commands.ts`
12. `src/telegram/bot-native-commands.ts`
13. `src/gateway/server.ts` and related `server-*` files
14. `ui/src/ui/app.ts`
15. `ui/src/ui/controllers/*`
16. `ui/src/ui/views/*`

## 31. Practical Takeaways

The reference platform repo is not organized around a single monolithic agent file. It is organized around a few major ideas:

- the gateway is the control plane
- the agent runtime is workspace- and skill-aware
- channels are native integrations, not thin wrappers
- the UI is a real operator console
- workspace files (`SOUL.md`, `IDENTITY.md`, `USER.md`, `TOOLS.md`, `HEARTBEAT.md`, `BOOTSTRAP.md`) are part of runtime behavior
- skills are first-class runtime assets, not just docs

That is the core reason reference platform feels flexible, "alive", and highly customizable.
