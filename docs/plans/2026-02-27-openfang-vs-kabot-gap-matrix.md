# Kabot vs OpenFang/OpenClaw Gap Verification

> Latest exhaustive follow-up (post OpenClaw `v2026.2.26`): `docs/plans/2026-03-04-openclaw-vs-kabot-full-gap-matrix.md`.

Date: 2026-03-01
Scope: non-test code verification (deep scan), then gap reclassification.

## Verification Coverage

- Kabot non-test files scanned: `362`
- Kabot non-test lines scanned: `46600`
- OpenClaw src non-test files scanned: `2445`
- OpenClaw src non-test lines scanned: `396869`
- OpenFang crates non-test files scanned: `379`
- OpenFang crates non-test lines scanned: `153697`

## High-Level Result

This previous matrix was stale. Several old "major gaps" in Kabot are already implemented.
The largest remaining gaps are now:

1. Channel parity breadth (many adapters still scaffold/placeholder).
2. Operator diagnostics depth (doctor parity-report style is not yet first-class).
3. Third-party skill onboarding UX (install is real, but not yet one-shot env/persona automation).

## Verified Parity Matrix (Current)

| ID | Area | Kabot Status | Evidence (Kabot) | Comparator Evidence | Final Verdict |
|---|---|---|---|---|---|
| P01 | Runtime fallback state machine | Implemented | `kabot/agent/loop_core/execution_runtime.py` (`state=primary/auth_rotate/model_fallback/text_only_retry`, max attempts, strict classification) | OpenClaw/OpenFang have deterministic routing/retry policies | Parity achieved (core) |
| P02 | Tool-call idempotency | Implemented | `kabot/agent/loop_core/execution_runtime.py` (`idempotency_ttl_seconds`, `tool_call_id_cache`, payload duplicate suppression) | OpenClaw uses guard + transcript repair | Parity achieved (core), OpenClaw still deeper on transcript repair ergonomics |
| P03 | Runtime config contracts (resilience/perf) | Implemented | `kabot/config/schema.py` (`RuntimeResilienceConfig`, `RuntimePerformanceConfig`) | OpenFang strongly typed runtime config style | Parity achieved |
| P04 | Fast-first-response memory path | Implemented | `kabot/agent/loop.py` deferred warmup + timeout + telemetry (`memory_warmup_ms`) | OpenFang/OpenClaw both optimize startup paths | Parity achieved |
| P05 | Skills typed canonical schema + migration | Implemented | `kabot/config/schema.py` (`SkillsConfig`), `kabot/config/skills_settings.py`, `kabot/config/loader.py` migration/default injection | OpenClaw has canonical config + migration helpers | Parity achieved |
| P06 | Skills precedence contract | Implemented and explicit | `kabot/agent/skills.py` order is explicit and deterministic via first-seen: workspace > agents-project > agents-personal > managed > builtin > extra | OpenClaw explicit precedence in `src/agents/skills/workspace.ts` | Parity achieved |
| P07 | Security preset wizard flow | Implemented | `kabot/config/schema.py` (`policy_preset`), `kabot/security/command_firewall.py`, wizard in `tools_gateway_skills.py` | OpenClaw has strong safety defaults and doctor security checks | Parity achieved (config/wizard), diagnostics depth still lower |
| P08 | OpenRouter model format handling | Implemented | `kabot/cli/wizard/sections/model_auth.py` supports nested ids/suffix format and examples | OpenClaw accepts provider-native ids and catalog probing | Parity achieved |
| P09 | WhatsApp bridge lifecycle hardening | Largely implemented | `kabot/cli/bridge_utils.py` (reachability, stop/reuse, background start), wizard flow in `channels.py`, runtime auto-start in `kabot/channels/whatsapp.py` | OpenClaw has mature bridge/session UX | Partial parity (better now, still needs long soak validation) |
| P10 | Native graph memory | Implemented | `kabot/memory/graph_memory.py`, integration in `chroma_memory.py`, `sqlite_memory.py`, prompt injection in `agent/context.py` | OpenFang has typed memory substrate + graph APIs | Feature parity exists; OpenFang remains stronger in type-rigidity and kernel-level composition |
| P11 | Adapter registry architecture | Implemented skeleton | `kabot/channels/adapters/registry.py` + manager integration | OpenFang has broad channel module surface in `openfang-channels/src/lib.rs` | Partial parity (architecture yes, implementation breadth no) |
| P12 | Top channel breadth | Not yet | Kabot currently real adapters: telegram, whatsapp, discord, slack, email, feishu, dingtalk, qq; others mostly placeholder | OpenFang exports much wider set; OpenClaw also broader | Gap remains (major) |
| P13 | Kernel-grade governance (RBAC/metering/manifest trust) | Limited | Kabot has command firewall and http guard, but no OpenFang-equivalent kernel RBAC/metering stack | OpenFang: `openfang-kernel/src/auth.rs`, `metering.rs`, manifest signing in `openfang-types/src/manifest_signing.rs` | Gap remains (major) |
| P14 | Doctor parity report depth | Partial | Kabot has doctor commands/services, but no dedicated parity report command with subsystem-level matrix | OpenClaw doctor stack includes stronger security and subsystem reporting depth | Gap remains (medium) |
| P15 | External skill one-shot onboarding | Partial | `kabot skills install --git` exists (`skill_repo_installer.py` + `commands.py`), enables config entry automatically | OpenClaw onboarding integrates setup flow tightly | Gap remains (medium): missing automatic env prompt + persona/SOUL injection step |

## Key Corrections vs Old Matrix

The following old gaps are no longer valid as "missing":

1. Typed `skills` contract in schema.
2. Runtime resilience/performance typed config.
3. Deterministic fallback state machine.
4. Tool idempotency controls.
5. OpenRouter parser flexibility improvements.
6. Security preset support in wizard.
7. Native graph memory availability.

## Remaining Priority (Superpower Roadmap)

### P0 (must do next)

1. Channel implementation breadth behind existing adapter registry (start with Signal, Matrix, Teams).
2. Long-run soak on bridge + fallback + cron idempotency under mixed auth failures.
3. Doctor parity report command (`kabot doctor --parity-report`) with explicit subsystem status.

### P1 (next)

1. One-shot external skill onboarding:
   - clone/install
   - detect required env keys
   - prompt/set keys
   - optional SOUL/AGENTS persona injection
2. Governance uplift package:
   - usage metering/quota guardrails (cost + token ceilings)
   - optional signed skill/manifest trust mode.

### P2 (quality hardening)

1. Expand wizard regression tests on channel CRUD and back-navigation.
2. Add structured observability dashboard summary (turn_id, model_chain, error_class, idempotency_hit).

## Practical Conclusion

Kabot is no longer behind on many core runtime/skills foundations; it is now mainly behind on ecosystem depth and operational hardening layers where OpenFang/OpenClaw are broader.

To make Kabot "superpower" in practice, the shortest path is:

1. Fill adapter breadth on top of current registry.
2. Add governance/diagnostic depth (doctor parity report, metering, trust mode).
3. Finish one-shot skills onboarding UX for non-technical users.

## Re-Audit 2026-03-03 (Beyond Keepalive)

Scope refresh for responsiveness and run UX after keepalive/status-phase rollout.

### Already Closed (This Week)

1. Multilingual phase status lifecycle in runtime (`queued/thinking/tool/done/error`) now emitted consistently from loop runtime.
   - Evidence: `kabot/agent/loop_core/message_runtime.py` and `kabot/agent/loop_core/execution_runtime.py`.
2. Cross-channel status dedupe + mutable status rendering is now wired:
   - Telegram, Discord, Slack update one status message per chat/thread.
   - Bridge adapters emit best-effort typing activity for `queued/thinking/tool`.
   - Email suppresses progress spam intentionally.
3. Fast route shortcuts are active:
   - direct deterministic tool turns skip heavy context assembly,
   - simple short turns use fast-simple context path,
   - critic retry is skipped for speed-sensitive turns (short chat / required-tool / background).
4. Queue mode runtime is now implemented for burst handling:
   - typed config in `runtime.queue`,
   - inbound debounce + per-session cap + drop policy (`drop_oldest|drop_newest`),
   - merged dropped-message summary metadata for interactive user feedback.
5. Draft partial preview lane is now available on the existing progress pipeline:
   - runtime emits `draft_update` during critic/self-eval retries,
   - channel base treats `draft_update` as mutable progress update (dedupe + edit-in-place behavior on channels that support message edits),
   - final non-progress reply clears mutable progress message as before.

### Remaining Non-Keepalive Gaps vs OpenClaw

| ID | Area | OpenClaw Evidence | Kabot Evidence | Gap Verdict |
|---|---|---|---|---|
| R1 | Draft partial streaming lifecycle (preview edit/finalize/clear) | `src/telegram/draft-stream.ts`, `src/channels/draft-stream-controls.ts` | Implemented core draft preview lifecycle via `draft_update` in `execution_runtime` + unified mutable progress lane in `channels/base.py` and channel senders | **Partial parity (core closed, token-stream granularity remains gap)** |
| R2 | Reasoning lane separation + stream callbacks | `src/auto-reply/types.ts` (`onPartialReply`, `onReasoningStream`, `onToolStart`, `isReasoning`) and `src/telegram/lane-delivery.ts` | Single text/status pipeline only; no lane-separated delivery contract | **Major gap** |
| R3 | Queue mode runtime (debounce/cap/drop policy + summarize) | `src/config/types.messages.ts` (`queue`), `src/utils/queue-helpers.ts` | Implemented in `kabot/config/schema.py` (`RuntimeQueueConfig`), loader migration defaults, and `kabot/bus/queue.py` inbound policy engine + drop-summary metadata surfaced in `message_runtime` queued status | **Closed (core parity)** |
| R4 | Native status reaction controller | `src/channels/status-reactions.ts` (`setQueued/setThinking/setTool/setDone/setError`, stall timers) | Text status updates only; no emoji reaction controller abstraction | **Medium gap** |
| R5 | Control-plane write budget limiter | `src/gateway/control-plane-rate-limit.ts` | No equivalent control-plane write throttler in Kabot channel/gateway surface | **Medium gap** |
| R6 | Approval payload richness (binding/plan/provenance) | `src/infra/exec-approvals.ts` (`systemRunBindingV1`, `systemRunPlanV2`, source fields) | Strong firewall exists, but approval payload transport metadata is simpler | **Medium gap** |

### Priority Recommendation

1. **P0**: R2 first (reasoning lane separation + stream callbacks).
2. **P1**: R4 (native reaction controller abstraction).
3. **P1/P2**: R5 + R6 (ops resilience and governance depth).

### Conflict Audit (Code/Tools/Skills)

Audit method:
1. Static scan + runtime doctor check.
2. Targeted regression tests for runtime/channels/skills/config.
3. Additional anti-collision tests for tool names, adapter keys, and skill dedupe.

Result summary:
1. **Tools**: no duplicate `tool.name` detected across `kabot/agent/tools`.
2. **Adapters**: no duplicate adapter keys in registry.
3. **Skills**:
   - raw directory collisions are present by design (workspace/global/builtin copies),
   - resolver remains deterministic and returns unique names by precedence.
4. **Known namespace overlap** (intentional, non-breaking): `cron` and `weather` exist as both skill names and tool names; current routing keeps them in separate layers (skill context vs tool execution).
5. **Doctor parity snapshot** confirms canonical config sections and deterministic skill precedence roots.
