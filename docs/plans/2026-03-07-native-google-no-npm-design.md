# Native Google Without npm Design

**Date:** 2026-03-07

**Problem**

Kabot currently has two possible directions for Google integrations:

- native Python tools already inside Kabot
- external Google backends such as `gogcli`

The audit in [2026-03-07-google-native-vs-gogcli-gap-matrix.md](/C:/Users/Arvy%20Kairi/Desktop/bot/kabot/docs/plans/2026-03-07-google-native-vs-gogcli-gap-matrix.md) shows that `gogcli` is operationally mature, but Kabot's native path fits the agent runtime much better.

The product preference is clear:

- Google integrations should work without requiring `npm`
- Node-based dependency chains should not become a mandatory part of the Kabot core experience
- Kabot should remain lightweight, simpler to install, and safer on small systems or Windows machines

## Goal

Make Kabot's Google story "native-first, no-npm-by-default".

That means:

1. Core Google features should work through Kabot's built-in Python/native path.
2. No Node/npm runtime should be required for Gmail, Calendar, Drive, Docs, Sheets, or Contacts.
3. Optional external backends may exist, but they must stay optional and not define the main architecture.

## Product Decision

Recommended direction:

- Primary path: native Kabot Google tools
- Optional power-user path: external backends such as `gogcli`
- Explicit non-goal: making Node/npm a required dependency for Google features

This decision is based on four practical constraints:

- Kabot is an LLM-first agent, not a shell-first automation framework
- Node-based dependencies are more operationally fragile on low-resource systems
- Python-native tools integrate more cleanly with tool schemas, guardrails, and multilingual reply shaping
- Users expect `kabot config` / setup wizard to handle Google in one coherent place

## Architecture

### 1. Native Google becomes the canonical path

The canonical Google path should stay inside Kabot:

- auth manager
- tool registration
- setup wizard
- doctor checks
- runtime tool-calling

The existing native files already form the correct skeleton:

- `kabot/auth/google_auth.py`
- `kabot/agent/tools/google_suite.py`
- `kabot/integrations/gmail.py`
- `kabot/integrations/google_calendar.py`
- `kabot/integrations/google_drive.py`
- `kabot/integrations/google_docs.py`

The missing work is maturity, not direction.

### 2. No-npm means no mandatory Node dependency in the Google critical path

The Google critical path includes:

- auth setup
- account selection
- token refresh
- Gmail
- Calendar
- Drive
- Docs
- future Sheets
- future Contacts

All of these should remain:

- Python-native
- shell-free by default
- installable via normal Kabot/Python setup

If an optional integration requires a separate binary, that is acceptable only if:

- it is not required for baseline Google features
- it does not replace native tool schemas
- it is clearly labeled advanced/optional

### 3. External backends remain adapters, not runtime owners

If Kabot later integrates `gogcli`, it should do so through an adapter layer:

- explicit capability detection
- explicit account selection
- structured argument validation
- controlled command wrappers

The adapter must not expose freeform shell prompt execution as the main Google path.

That avoids:

- shell injection risk
- agent confusion
- brittle output parsing
- over-reliance on external CLI behavior

## Feature Roadmap

### Phase 1: Harden the existing native path

Bring the current native stack to a production baseline:

- safer token storage abstraction
- multi-account support
- headless/manual auth option
- better doctor and wizard diagnostics
- clearer error messages

### Phase 2: Expand native feature coverage

Prioritize the missing features with the highest user value:

1. Sheets
2. Contacts / People
3. Tasks

This delivers the largest practical benefit without introducing npm.

### Phase 3: Optional external backend bridge

Only after native maturity is improved:

- detect `gogcli`
- surface it in doctor/wizard
- add structured wrappers for advanced Google Workspace operations

This preserves the no-npm design while still allowing power-user expansion.

## Auth Model

The current native Google auth is too simple for long-term parity.

The target auth model should support:

- one or more account profiles
- one or more OAuth client profiles
- per-account token isolation
- optional safer storage backend
- manual/headless authorization flow
- scope shaping per feature set when possible

The important design point is this:

- improve the native model
- do not replace it with a shell-first auth dependency

## Setup and UX

The setup experience should stay centered in Kabot:

- `kabot google-auth`
- setup wizard Google section
- doctor status
- dashboard status later if needed

The user should not have to understand whether a Google feature is "native" or "backend-driven" unless they explicitly enter advanced mode.

Default expectation:

- install Kabot
- run wizard or auth command
- use Google features

No npm, pnpm, bun, or Node mental model should be required.

## Risks

### Risk: Native path becomes too broad

Mitigation:
- keep the native surface focused on high-value features
- do not chase full `gogcli` breadth immediately

### Risk: External backend grows into shadow architecture

Mitigation:
- define external tools as optional adapters only
- keep native tool schemas as the public contract for Kabot

### Risk: Auth complexity grows

Mitigation:
- centralize account/client/token logic in a dedicated native auth layer
- do not scatter Google account state across unrelated modules

## Recommendation

The preferred product direction is:

- Native Google in Kabot should be the main path
- Google features should not require npm
- Optional external integrations are allowed, but only as advanced adapters

In short:

**Make Google first-class in Kabot, not outsourced to a Node ecosystem.**
