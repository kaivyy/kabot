# Google Native Vs gogcli Gap Matrix

Date: 2026-03-07

Scope:
- Native Google path inside Kabot
- External `gogcli` repo cloned at `C:\Users\Arvy Kairi\Desktop\bot\gogcli`
- Focus: auth, storage, runtime/tool integration, output behavior, feature coverage, setup UX, and implications for Kabot

Primary evidence:
- Kabot native auth/tool/runtime:
  - `kabot/auth/google_auth.py`
  - `kabot/agent/tools/google_suite.py`
  - `kabot/integrations/gmail.py`
  - `kabot/integrations/google_calendar.py`
  - `kabot/integrations/google_drive.py`
  - `kabot/integrations/google_docs.py`
  - `kabot/agent/loop.py`
  - `kabot/cli/commands.py`
  - `kabot/cli/wizard/sections/core.py`
- gogcli auth/config/runtime:
  - `gogcli/internal/config/paths.go`
  - `gogcli/internal/config/config.go`
  - `gogcli/internal/config/credentials.go`
  - `gogcli/internal/config/clients.go`
  - `gogcli/internal/secrets/store.go`
  - `gogcli/internal/googleauth/oauth_flow.go`
  - `gogcli/internal/googleauth/service.go`
  - `gogcli/internal/googleapi/client.go`
  - `gogcli/internal/cmd/root.go`
  - `gogcli/internal/cmd/auth.go`
  - `gogcli/internal/outfmt/outfmt.go`
  - `gogcli/internal/errfmt/errfmt.go`
  - `gogcli/internal/cmd/schema.go`

Repo scale snapshot for gogcli:
- 630 files total
- 553 Go files
- 317 test files
- 453 files under `internal/cmd`

## Executive Summary

`gogcli` is not an AI agent runtime. It is a large, mature, test-heavy Google Workspace CLI designed to be consumed by humans, scripts, and agents. Its biggest strengths are:

- broad Google Workspace surface area
- mature multi-account and multi-client auth
- secure secrets storage via keyring or encrypted file backend
- stable machine-readable output
- extensive tests around command behavior and output

Kabot's native Google path is much smaller but better aligned to direct LLM tool-calling because it exposes structured tools instead of shelling out to a CLI.

The key decision is not "which one is better overall" but:

- Native Kabot is better as the primary tool-call path for common agent tasks.
- `gogcli` is better as an advanced external backend for broader Google Workspace coverage.

Recommendation:
- Keep native Kabot Google tools as the default agent path.
- Add `gogcli` as an optional advanced integration layer.
- Do not replace native Kabot wholesale with `gogcli` unless the product direction becomes "shell-centric automation" instead of "LLM-native tool orchestration".

## Parity Snapshot

- Native Kabot stronger:
  - LLM tool-call integration
  - simpler setup for one account
  - direct runtime registration
  - user-facing response shaping
- gogcli stronger:
  - auth maturity
  - multi-account/multi-client routing
  - service breadth
  - output contracts
  - test coverage
  - headless/manual auth flows
  - least-privilege scope selection

## Gap Matrix

| Area | Native Kabot | gogcli | Gap | Severity |
| --- | --- | --- | --- | --- |
| Runtime model | Structured Python tools registered into agent runtime | CLI command tree with machine-friendly output | Different integration model; gogcli is a tool backend, not a replacement runtime | P0 |
| Gmail | Search, send, draft | Much broader: search threads/messages, labels, filters, delegates, vacation, history, watch, attachments, replies | Native Kabot covers only core actions | P1 |
| Calendar | List and create events | Large surface: list/get/create/update/delete/respond/freebusy/conflicts/colors/team/focus/OOO/working location | Native Kabot calendar is minimal | P1 |
| Drive | Search and upload text | List/search/get/download/upload/mkdir/delete/move/share/permissions/comments/shared drives | Native Kabot Drive is narrow | P1 |
| Docs | Create/read/append | Export/copy/create and document editing workflows via broader command set | Native Kabot Docs is smaller but more direct | P2 |
| Sheets | None native | Strong native CLI support | Missing entirely in Kabot native | P0 |
| Contacts / People | None native | Strong CLI coverage | Missing entirely in Kabot native | P0 |
| Chat / Classroom / Forms / Tasks / Groups / Keep / Slides / AppScript | None native | Supported | Missing entirely in Kabot native | P1 |
| Auth storage | `google_token.json` on disk under `~/.kabot` | Keyring by default, encrypted file backend fallback | Kabot stores tokens less defensively | P0 |
| OAuth client handling | Single client path | Named clients, domain mapping, account-to-client mapping | Kabot lacks mature multi-client model | P0 |
| Multi-account | No first-class account bucket model | First-class multi-account and per-client isolation | Major capability gap | P0 |
| Headless / remote auth | Browser local-server flow only | Local browser, manual pasteback, remote two-step | Kabot auth is weak for headless servers | P0 |
| Least-privilege scopes | Broad fixed scopes | Per-service selection, readonly flags, drive/gmail scope modes | Kabot auth is broader than necessary | P1 |
| Service accounts | Not present in native Google path | Workspace service account + domain-wide delegation supported | Enterprise/workspace gap | P1 |
| Output contract | Human-oriented strings | JSON-first and plain stable output | gogcli is easier to automate downstream | P1 |
| Error formatting | Simple strings | Dedicated user-facing formatter with auth/setup hints | Kabot native errors are less operationally mature | P2 |
| Command/schema introspection | Tool schemas exist only inside runtime | CLI schema command and stable command tree | gogcli is more self-describing externally | P2 |
| Setup wizard | Native Google auth section exists | No Kabot wizard integration for gogcli | Integration gap in Kabot UX | P1 |
| Security controls | Kabot command firewall and tool policies | Command allowlist inside gogcli plus keyring backend controls | Different strengths; should be combined, not replaced | P1 |
| Test coverage | Relatively limited in Google native area | Extremely broad | Confidence gap | P0 |
| Windows packaging | Python-based, generally okay | Windows auth backend appears supported, packaging/install docs less first-class | gogcli is not Windows-first operationally | P2 |

## Detailed Findings

### 1. Runtime Architecture

Native Kabot:
- Google tools are direct runtime tools loaded in `loop.py`.
- They fit naturally into the LLM tool-call model.
- No shell hop is required when the tool is invoked.

gogcli:
- Everything routes through the CLI command tree in `internal/cmd/root.go`.
- Output is intentionally stable for scripts and agents.
- The `agent` surface is tiny; it offers helper behaviors like stable exit codes, not an LLM loop.

Interpretation:
- gogcli should be treated as a highly capable external tool, not as an agent runtime to copy.

### 2. Auth and Secret Storage

Native Kabot:
- OAuth client JSON is copied to `~/.kabot/google_credentials.json`
- Tokens are stored in `~/.kabot/google_token.json`
- This is operationally simple but weaker from a secrets-handling standpoint.

gogcli:
- Config base dir is `os.UserConfigDir()/gogcli`
- On this Windows machine that resolves to `C:\Users\Arvy Kairi\AppData\Roaming\gogcli`
- OAuth client data is stored in `credentials.json` / `credentials-<client>.json`
- Refresh tokens are stored in keyring by default or encrypted file backend under `keyring/`

Interpretation:
- gogcli's auth system is materially more mature and safer.
- This is the largest architectural advantage over Kabot native Google.

### 3. Multi-Account and Client Routing

Native Kabot:
- Assumes one credentials path and one token path.
- There is no native account bucket abstraction.

gogcli:
- Supports named clients
- Supports account -> client mapping
- Supports domain -> client mapping
- Supports service account precedence for some flows

Interpretation:
- If Kabot needs "work Gmail + personal Gmail + domain-routed clients", the current native path is not enough.

### 4. Output and Automation Readiness

Native Kabot:
- Returns human-readable strings from tool handlers.
- Good for final conversational replies.
- Weaker for downstream automation reuse.

gogcli:
- Has `--json`, `--plain`, `--results-only`, `--select`
- Has explicit output and error formatting layers
- Has tests asserting text and JSON output stability

Interpretation:
- gogcli is a better automation backend.
- Native Kabot is a better final user-facing tool-call surface.

### 5. Feature Coverage

Native Kabot Google coverage is intentionally narrow and high-signal:
- Gmail
- Calendar
- Drive
- Docs

gogcli coverage is much broader:
- Gmail
- Calendar
- Chat
- Classroom
- Drive
- Docs
- Slides
- Sheets
- Forms
- Apps Script
- Contacts
- Tasks
- People
- Groups
- Keep

Interpretation:
- Kabot native is not near parity on breadth.
- The largest missing surface areas for practical productivity use are Sheets and Contacts.

### 6. Headless and Remote Server UX

Native Kabot:
- Uses local browser flow via `InstalledAppFlow.run_local_server`
- Good for desktop setup
- Weak for SSH/VPS/headless flows

gogcli:
- Local browser
- Manual flow
- Remote two-step flow
- Keyring/file backend selection for interactive vs non-interactive environments

Interpretation:
- gogcli is much more operationally ready for remote automation.

### 7. Testing Maturity

Native Kabot:
- Google native area exists but is comparatively thin in verification maturity.

gogcli:
- Test-heavy across auth, config, storage, output, and command semantics
- Many tests lock in exact text and JSON output expectations

Interpretation:
- This is not a cosmetic difference. It explains why gogcli is safer to depend on as an external automation backend.

## Integration Recommendation For Kabot

### Recommended Role Split

Primary path:
- Native Kabot Google tools for conversational agent workflows

Secondary path:
- Optional `gogcli` bridge for advanced commands and broad Google Workspace coverage

Why:
- Native tools preserve structured LLM tool invocation
- `gogcli` fills feature breadth and auth maturity gaps
- Combining both avoids overfitting Kabot to a shell-first model

### Best Next Steps

P0:
- Add a `gogcli` doctor/inventory check in Kabot
- Detect install status, auth readiness, config path, backend, and account list
- Do not auto-route blindly; expose capability state clearly

P0:
- Design a native multi-account Google model for Kabot
- Even if `gogcli` is integrated, Kabot still needs a coherent account identity model

P1:
- Add native Sheets and Contacts tools to Kabot
- These are the most meaningful coverage gaps relative to gogcli

P1:
- Upgrade Kabot native auth to support:
  - safer token storage
  - named clients
  - optional headless/manual auth flow

P1:
- Add a `gogcli` adapter layer with structured command wrappers instead of raw shell freeform

### Explicit Anti-Pattern To Avoid

Do not replace native Google tools with direct freeform shell prompts like:
- `gog gmail send ...`
- `gog calendar ...`

inside agent reasoning.

That would:
- reduce structured safety
- increase shell injection and parsing risk
- make the user-facing tool layer less deterministic

If Kabot uses `gogcli`, it should use:
- structured wrapper tools
- explicit argument validation
- explicit account selection logic

## Bottom Line

`gogcli` is the stronger Google automation backend.
Kabot native Google is the stronger LLM-facing tool surface.

So the real gap is not "Kabot should become gogcli".

The real gap is:
- Kabot needs better auth maturity
- better multi-account support
- broader native feature coverage
- and an optional structured bridge to `gogcli`

That gives Kabot the best of both worlds without inheriting the wrong runtime model.
