# Releases

## v0.6.5-rc1

Release date: 2026-03-15

Status: Release candidate

### Highlights

- Makes Kabot more OpenClaw-like in multilingual, model-first routing and follow-up continuity without leaning on Indonesian-only parser paths.
- Strengthens grounded repo/folder inspection, live web fallback behavior, and external skill continuity for headless or VPS-style runtimes.
- Polishes the gateway dashboard shell and chat workspace into a more operator-friendly control console.

### Notable fixes

- `buka config.json` and similar bare filename follow-ups now resolve against the active folder context instead of falling back to a stale or generic path.
- Weather commentary and source/provider follow-ups like `lumayan hangat ya`, `wttr.in`, or `open-meteo` no longer misfire as fresh weather fetches.
- Live finance/news turns are more honest about missing live sources and now prefer grounded `web_search -> web_fetch -> skill/reference/script` fallback behavior.

### Validation snapshot

- Syntax checks passed for updated runtime, dashboard, and regression test files.
- `git diff --check` is clean.
- Release build/test automation still depends on environment packages such as `pytest` and docs/build tooling.

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
