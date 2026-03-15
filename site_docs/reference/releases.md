# Releases

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
