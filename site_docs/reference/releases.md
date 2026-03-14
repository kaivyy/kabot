# Releases

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
