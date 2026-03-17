# Releases

## v0.6.7

Release date: 2026-03-17

Status: Stable release

### Highlights

- Adds fallback selection and ordering to the setup wizard.
- Normalizes OpenRouter model identifiers and provider routing to reduce invalid requests.
- Expands Telegram slash command handling to support bot mention suffixes and `/model` directives.

### Notable changes

- Updates failover classification patterns with expanded tests.

### Validation snapshot

- `mkdocs build --strict` succeeded for the updated release docs.
- `python -m build` produced `kabot-0.6.7.tar.gz` and `kabot-0.6.7-py3-none-any.whl`.

See full details in root `CHANGELOG.md`.

## v0.6.6-rc3

Release date: 2026-03-15

Status: Release candidate

### Highlights

- Keeps the OpenClaw-style runtime direction while tightening real skill execution continuity.
- Makes approved skill workflows, freshly created skills, and active external stock/finance skills stay grounded to actual execution evidence.
- Lets direct GitHub skill sources and exact installed skill names steer the workflow from grounded skill inventory and source paths instead of extra action keywords.

### Notable fixes

- Approved `skill-creator` and installer turns now require real tool or approved-skill execution before Kabot can claim success.
- Newly created workspace skills can now be reused immediately on the first matching follow-up instead of bouncing back to `skill-creator`.
- Active external stock/finance lanes stay on the selected skill workflow instead of drifting into generic `web_search` setup errors.
- Exact installed skill names and direct GitHub skill source URLs now trigger the correct skill lane from grounded inventory/source matching.

### Validation snapshot

- Targeted runtime guard regression slice: `2 passed`.
- Targeted transcript and skill continuity regression slices: `9 passed`.
- Targeted skill matching regression slice: `3 passed`.
- `python -m build --no-isolation` will normalize artifacts as `kabot-0.6.6rc3.tar.gz` and `kabot-0.6.6rc3-py3-none-any.whl`.
- `mkdocs build --strict` succeeded for the updated release docs.

See full details in root `CHANGELOG.md`.

## v0.6.6-rc2

Release date: 2026-03-15

Status: Release candidate

### Highlights

- Keeps the `v0.6.6` OpenClaw-style runtime direction intact while fixing the release-follow-up cross-platform regression slice.
- Aligns the CI guard/runtime tests with the parser-light, state-first contract now used by Kabot's active routing layers.
- Confirms the macOS and Ubuntu matrix passes again on `main`.

### Notable fixes

- The cross-platform regression slice no longer expects Indonesian parser-era prompts for action requests, delivery reuse, weather status, web search, or browser headless-live guards.
- The exact workflow slice in `.github/workflows/ci-matrix.yml` was replayed locally and brought back to green before cutting this RC.

### Validation snapshot

- Exact cross-platform regression slice from `.github/workflows/ci-matrix.yml`: `122 passed`.
- `python -m build --no-isolation` will normalize artifacts as `kabot-0.6.6rc2.tar.gz` and `kabot-0.6.6rc2-py3-none-any.whl`.
- `mkdocs build --strict` succeeded for the updated release docs.

See full details in root `CHANGELOG.md`.

## v0.6.6-rc1

Release date: 2026-03-15

Status: Release candidate

### Highlights

- Moves Kabot closer to OpenClaw-style execution with model-first, skill-first, workspace/cwd-first, and session continuity-first routing.
- Shrinks parser and keyword-heavy fallback behavior across follow-up reuse, live research, filesystem grounding, and temporal fast paths.
- Keeps external skill workflows, repo inspection, and API/script execution more grounded while installer/docs stay release-ready.

### Notable fixes

- Bare filename follow-ups such as `open config.json` now resolve against the active folder context instead of falling back to stale or generic paths.
- Weather commentary and provider/source follow-ups stay grounded to the existing weather context instead of misfiring as fresh fetches.
- Live finance/news turns are more honest about missing sources and prefer grounded `web_search -> web_fetch -> skill/reference/script` fallback behavior.

### Validation snapshot

- `python3 -m py_compile` passed for the updated runtime, routing, skill, and regression files.
- Targeted OpenClaw-style regression slices passed across semantic intent, skill matching, context building, reminder fallback, follow-up reuse, temporal fast replies, direct delivery reuse, stock extraction, and web-search fallback.
- `python -m build --no-isolation` produced `kabot-0.6.6rc1.tar.gz` and `kabot-0.6.6rc1-py3-none-any.whl`.
- `mkdocs build --strict` succeeded.
- `git diff --check` is clean.

See full details in root `CHANGELOG.md`.

## v0.6.5

Release date: 2026-03-14

### Highlights

- Hardened file-delivery continuity across chat turns.
- Improved session-aware path memory (`last_navigated_path`, `last_delivery_path`).
- Prevented stale internal temp paths (e.g. `.basetemp`) from overriding active user folder context.
- Fixed `list_dir` follow-up latch so it no longer overrides explicit send-file intents.
- Improved short send follow-ups like `kirim langsung` when prior delivery context exists.

### Notable reliability fixes

- `kirim file tes.md kesini` now keeps `message` intent and avoids false `File not found` caused by stale follow-up state.
- Search/send workflows now honor active navigation context before older fallback paths.
- Session hydration/finalization now persists filesystem continuity metadata for one-shot and multi-turn chat flows.

### Validation snapshot

- Regression suites passed after hardening: 245+ passing targeted tests in local CI runs.

See full details in root `CHANGELOG.md`.
