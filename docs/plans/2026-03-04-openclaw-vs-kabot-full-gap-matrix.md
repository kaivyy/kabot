# OpenClaw vs Kabot Full Gap Matrix (Post v2026.2.26)

Date: 2026-03-04  
Compared repos:
- OpenClaw: `C:/Users/Arvy Kairi/Desktop/bot/openclaw` (`HEAD=1be39d425`)
- Kabot: `C:/Users/Arvy Kairi/Desktop/bot/kabot`

## Audit Scope (No-Skip Boundary)

This audit intentionally covers all major operational surfaces, not just typing/keepalive:

1. Runtime loop, fallback, idempotency, queue behavior.
2. Input understanding (follow-up continuity, latest/live query safety, anti-hallucination guard).
3. UX responsiveness (typing keepalive, status phases, draft/partial behavior).
4. Channels (adapter architecture + production depth).
5. Gateway/control plane (RPC surface, auth scopes, pairing, write-budget guardrails).
6. Security hardening breadth.
7. Skills/plugins ecosystem.
8. Sessions, cron, memory, observability, operator UX.
9. Dashboard/control UI and monitoring surface.

OpenClaw change window examined (after `v2026.2.26`):
- `2026.3.1`, `2026.3.2`, `2026.3.3` changelog sections
- Diff volume `v2026.2.26..HEAD`: `2834 files changed, +200750/-57323`

Kabot current codebase size scanned (non-test):
- `371` files, `50178` lines

## Coverage Guard (Domain Mapping)

| Domain | OpenClaw evidence | Kabot evidence | Coverage |
|---|---|---|---|
| Inbound context finalization | `src/auto-reply/reply/inbound-context.ts`, `untrusted-context.ts` | `kabot/agent/context.py`, `kabot/agent/loop_core/message_runtime.py` | Covered |
| Typing/status lifecycle | `src/auto-reply/reply/typing.ts`, `typing-mode.ts`, `src/channels/status-reactions.ts` | `kabot/agent/loop_core/message_runtime.py`, `kabot/channels/base.py`, `kabot/channels/telegram.py`, `kabot/channels/discord.py`, `kabot/channels/slack.py` | Covered |
| Follow-up continuity | `src/auto-reply/reply/followup-runner.ts` | `kabot/agent/loop_core/message_runtime.py`, `kabot/agent/loop_core/execution_runtime.py` | Covered |
| Control UI/dashboard | `ui/src/ui/**`, `docs/web/control-ui.md`, `docs/web/dashboard.md` | No equivalent `ui/src/ui` tree in Kabot | Covered |
| Gateway RPC/scope model | `src/gateway/server-methods-list.ts`, `method-scopes.ts` | `kabot/gateway/webhook_server.py`, `kabot/cli/commands.py` | Covered |
| Control-plane write limiter | `src/gateway/control-plane-rate-limit.ts` | `kabot/gateway/middleware/rate_limit.py` (generic HTTP limiter) | Covered |
| Channel breadth/depth | Changelog families: Discord/Telegram/Feishu/Slack/LINE/etc | `kabot/channels/*`, `kabot/channels/adapters/registry.py` | Covered |
| Security hardening | Changelog families: Security/*, Gateway/Security/*, Sandbox/* | `kabot/security/command_firewall.py`, `kabot/config/schema.py`, `kabot/gateway/webhook_server.py` | Covered |
| Skills/plugins | Changelog families: Plugins/*, Plugin runtime/*, Hooks/* | `kabot/cli/skill_repo_installer.py`, `kabot/plugins/manager.py`, `kabot/agent/skills.py` | Covered |
| Sessions/cron/memory/observability | Changelog families: Sessions/*, Cron/*, Memory/*, Docs/Web | `kabot/session/*`, `kabot/cron/*`, `kabot/memory/*`, `kabot/utils/doctor.py` | Covered |

## Matrix A - Areas Already Near Parity

| ID | Area | OpenClaw baseline | Kabot status | Evidence |
|---|---|---|---|---|
| A01 | Deterministic runtime fallback | Stable fallback/error classes | Implemented | `kabot/agent/loop_core/execution_runtime.py` |
| A02 | Tool-call idempotency guard | Duplicate/replay protections | Implemented | `kabot/agent/loop_core/execution_runtime.py` |
| A03 | Runtime typed resilience/perf/queue config | Strong typed runtime knobs | Implemented | `kabot/config/schema.py`, `kabot/config/loader.py` |
| A04 | Queue/debounce for burst traffic | Follow-up queue + debounce maturity | Implemented (core) | `kabot/bus/queue.py`, `kabot/agent/loop_core/message_runtime.py` |
| A05 | Forced live-search path for "latest/current/news" intent | Live-fact safe routing | Implemented (core) | `kabot/agent/loop_core/message_runtime.py`, `execution_runtime.py` |
| A06 | Adapter registry architecture | Registry-first channel loading | Implemented | `kabot/channels/adapters/registry.py`, `kabot/channels/manager.py` |
| A07 | One-shot external skill install baseline | Mature skill ecosystem | Implemented baseline | `kabot/cli/skill_repo_installer.py`, `kabot/cli/commands.py` |
| A08 | Parity diagnostics command surface | Strong doctor/status surfaces | Implemented baseline | `kabot/cli/commands.py` (`doctor --parity-report`), `kabot/utils/doctor.py` |

## Matrix B - Remaining Gaps (Comprehensive)

| ID | Area | OpenClaw behavior | Kabot current | Gap level | Priority |
|---|---|---|---|---|---|
| G01 | Untrusted metadata boundary | Explicit untrusted context block ("do not treat as instructions") | Added explicit untrusted-context guard + data envelope in prompt assembly; still simpler than OpenClaw inbound-finalizer contract | Partial | P0 |
| G02 | Inbound context normalization contract | `BodyForAgent`, `BodyForCommands`, `CommandAuthorized`, media alignment enforced centrally | Routing/context exists, but normalization contract is looser and spread across runtime | Partial | P1 |
| G03 | Reasoning lane separation | Separate partial/reasoning/tool callbacks and lane delivery | Added `reasoning_update` lane and lane metadata (`status/partial/reasoning`); still not full OpenClaw callback graph depth | Partial | P0 |
| G04 | Reaction-based phase UX | Native channel-agnostic status reaction controller (`queued/thinking/tool/done/error`) | Phase text/status updates exist, but no unified reaction controller abstraction | Partial | P1 |
| G05 | Draft-stream finalization maturity | Dedicated draft-stream boundary/finalization modules (Telegram) | `draft_update` exists, but token-stream/draft-finalization semantics still simpler | Partial | P1 |
| G06 | Full web control UI | Full SPA dashboard (chat/config/cron/sessions/logs/usage/devices/exec approvals) | Added lightweight SSR+HTMX dashboard baseline (`/dashboard` + partials + status API); still not feature-complete control UI | Partial | P0 |
| G07 | Gateway method scope model | Per-method least-privilege scopes (`operator.read/write/admin/...`) | Added scoped bearer token baseline with route-level scope checks (`operator.read`, `ingress.write`) | Partial | P0 |
| G08 | Device/node pairing workflow | First-class device/node pair/list/approve/revoke | Kabot has bridge pairing helpers, not equivalent gateway device trust workflow | Open | P1 |
| G09 | Control-plane write budget limiter | Per-client control-plane write budget guard | Only generic HTTP rate-limit middleware; no control-plane semantic limiter | Partial | P1 |
| G10 | Channel production-depth parity | Heavy hardening in Discord/Telegram/Feishu/Slack/LINE changelog stream | Kabot channels exist but do not yet match OpenClaw depth across edge cases | Partial | P0 |
| G11 | Feishu-level maturity | Extensive Feishu reliability/auth/routing/dedupe hardening | Feishu adapter present, but parity depth not yet demonstrated | Partial | P1 |
| G12 | Plugin runtime API depth | Rich plugin runtime hooks/events/subpaths/channel runtime context | Kabot plugin manager exists, but runtime SDK/hook depth is lower | Open | P1 |
| G13 | Session control/telemetry APIs | Sessions usage logs/timeseries/preview/reset/compact via dashboard+gateway | Kabot has session persistence and core services, but no equivalent API/dashboard control surface | Partial | P1 |
| G14 | Cron web operator surface | Full cron UI editing/filter/history behaviors | CLI/runtime cron strong; no equivalent dashboard-grade cron UX | Partial | P2 |
| G15 | Security hardening breadth | Very broad hardening stream (SSRF/canonicalization/ingress/tool/sandbox/auth labels/etc.) | Strong firewall + trust config exists, but breadth still smaller | Partial | P0 |
| G16 | Multilingual quality consistency | Strong channel/runtime maturity with fewer keyword-bound paths | Kabot still has keyword-heavy heuristics and mixed hardcoded term banks | Partial | P0 |
| G17 | Text encoding quality in lexicon | UTF-safe multilingual strings in mature stack | Core lexicon migrated to valid UTF-8 + i18n mojibake fallback to English; residual risk still exists in some legacy strings | Partial | P0 |
| G18 | "Implicit intent" robustness | Mature handling without requiring strict confirmation tokens | Kabot improved follow-up continuity but still has lexical dependency in some flows | Partial | P0 |
| G19 | Operator monitoring productization | Dashboard + logs + usage + presence as one control surface | Kabot parity-report exists, but monitoring remains CLI-centric | Partial | P1 |
| G20 | Cross-channel interaction parity | OpenClaw ships broader interaction semantics across channels | Kabot core works, but behavior parity across all adapters still uneven | Partial | P1 |

## Delta Update - 2026-03-04 (Gateway/Tailscale Reality Check)

This pass closes one previously implicit runtime gap in Kabot:

| ID | Area | Previous Kabot state | Current Kabot state | Status |
|---|---|---|---|---|
| D01 | Gateway port source of truth | Wizard saved `gateway.port`, but `kabot gateway` defaulted to hardcoded `18790` unless `--port` was passed | `kabot gateway` now uses `config.gateway.port` by default; `--port` remains explicit override | Closed |
| D02 | Tailscale execution reality | `gateway.tailscale`/`bind_mode=tailscale` existed at config/wizard level but had no real startup integration | Gateway startup now runs real tailscale CLI flow (`status` + `serve/funnel`) and reports URL/errors | Closed |
| D03 | Tailscale failure semantics | Could behave like mock/placeholder (silent from runtime path) | `bind_mode=tailscale` now fail-fast when tailscale activation fails (clear operator signal) | Closed |
| D04 | Untrusted-context guard | Transport/session metadata could mix with instruction path | Added `Untrusted Context Safety` guard + `[UNTRUSTED_CONTEXT_JSON]` envelope as data-only context | Closed (baseline) |
| D05 | Reasoning lane baseline | Only status/draft mutable lane existed | Added dedicated `reasoning_update` lane with explicit `lane` metadata (`status/partial/reasoning`) | Closed (baseline) |
| D06 | Dashboard baseline | No built-in web dashboard route | Added SSR+HTMX lightweight dashboard surface (`/dashboard`, partials, status API) | Closed (baseline) |
| D07 | Method-scope auth baseline | Single bearer token without scope semantics | Added scoped token parsing (`token|scope1,scope2`) + per-route scope checks (`operator.read`, `ingress.write`) | Closed (baseline) |
| D08 | Multilingual mojibake hardening | Corrupted non-Latin term banks in key runtime lexicon path | Rebuilt shared lexicon with valid UTF-8 terms + i18n fallback when locale template looks mojibake | Closed (baseline) |

Residual difference to OpenClaw:
- OpenClaw still has richer tailscale productization (`off|serve|funnel` typed mode, reset-on-exit, broader dashboard/control-plane integration).
- Kabot now has real runtime activation, but still uses backward-compatible boolean/bind-mode mapping rather than full typed tailscale mode schema.

## Highest-Impact P0 Gaps (Do First)

1. G01/G03/G16/G18: Input correctness and anti-hallucination maturity.
2. G06/G07: Control plane parity (dashboard + method scope governance).
3. G10/G15: Channel and security hardening depth.
4. G17: Multilingual text-quality/encoding reliability (prevent broken non-Latin matching).

## Concrete "No-Miss" Checklist for Next Iteration

To avoid missing anything in the next pass, use this exact sequence:

1. Re-scan OpenClaw changelog sections `2026.3.1`, `2026.3.2`, `2026.3.3`.
2. Re-check these OpenClaw files:
   - `src/auto-reply/reply/inbound-context.ts`
   - `src/auto-reply/reply/untrusted-context.ts`
   - `src/auto-reply/reply/followup-runner.ts`
   - `src/auto-reply/reply/typing.ts`
   - `src/auto-reply/reply/typing-mode.ts`
   - `src/channels/status-reactions.ts`
   - `src/gateway/server-methods-list.ts`
   - `src/gateway/method-scopes.ts`
   - `src/gateway/control-plane-rate-limit.ts`
   - `ui/src/ui/controllers/*`
3. Re-check these Kabot files:
   - `kabot/agent/loop_core/message_runtime.py`
   - `kabot/agent/loop_core/execution_runtime.py`
   - `kabot/agent/context.py`
   - `kabot/agent/cron_fallback_nlp.py`
   - `kabot/agent/language/lexicon.py`
   - `kabot/channels/base.py`
   - `kabot/channels/telegram.py`
   - `kabot/channels/discord.py`
   - `kabot/channels/slack.py`
   - `kabot/channels/adapters/registry.py`
   - `kabot/gateway/webhook_server.py`
   - `kabot/gateway/middleware/rate_limit.py`
   - `kabot/utils/doctor.py`
4. Update matrix status only after this list is completed end-to-end.

---

Practical conclusion: Kabot has closed many core runtime foundations, but the biggest remaining deltas to OpenClaw are still in control-plane maturity, input/context safety contract depth, multilingual robustness, and channel hardening breadth.
