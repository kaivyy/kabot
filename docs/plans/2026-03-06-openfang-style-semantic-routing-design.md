# Openfang-Style Semantic Routing Design

**Date:** 2026-03-06

**Problem**

Kabot still routes too many turns through deterministic `required_tool_for_query(...)` and follow-up inference before the main LLM loop. That helps for a few high-confidence tasks, but it also causes the failures the user keeps seeing:

- natural follow-ups like `berangin apa ga?` can drift to the wrong tool
- meta turns like `kenapa jawabnya gitu?` can still inherit stale tool state
- conversion/advice turns like `jadikan idr` or `sunscreen yang bagus apa` are over-constrained by parser-heavy paths
- live-tool bypasses can feel rigid compared with Openfang

Openfang feels more natural because its main path is LLM-first: the model receives tool definitions, chooses tools during the loop, and only relies on heuristics for model tiering, safety, auto-reply suppression, and recovery of malformed tool-call output.

## Goal

Refactor Kabot so tool selection becomes semantic-first and parser-second:

1. Prefer contextual semantic intent arbitration before deterministic tool forcing.
2. Keep deterministic routing only for genuinely high-confidence or safety-critical cases.
3. Preserve multilingual behavior and reduce hardcoded phrasing dependence.
4. Keep fast-first-response, status updates, and direct-tool fallbacks, but move them behind stronger confidence gates.

## Proposed Architecture

### 1. Introduce an Intent Arbitration Layer

Add a new routing stage between `IntentRouter.route(...)` and `required_tool_for_query(...)`.

Input:
- raw user text
- normalized text
- recent user-turn-only history
- pending follow-up context
- route profile (`CHAT`, `GENERAL`, `RESEARCH`, `CODING`)
- tool availability

Output:
- `intent_type` (chat, advice, live_info, weather, stock_quote, stock_analysis, crypto_quote, reminder, file_read, update, system_info, cleanup, image_generation, email_draft, spreadsheet_help, unknown)
- `candidate_tool`
- `confidence`
- `reason_source` (`semantic`, `followup`, `deterministic`, `safety_latch`)

The new layer should prefer:
- LLM/semantic inference for ambiguous natural language
- deterministic fallback only when confidence is high
- no tool when the turn is discussion, clarification, opinion, advice, or complaint

### 2. Narrow Deterministic Routing

Keep parser-driven routing only for:
- schedule/reminder creation with explicit temporal payload
- explicit file/path reads
- explicit weather/location asks with recoverable location payload
- explicit live market quote asks with clear ticker/name/fx payload
- explicit system/update/cleanup operations

Do not force deterministic routing for:
- conversational follow-ups
- user complaints about previous answer
- general advice
- interpretation questions (`cenderung naik atau turun?`)
- currency conversion follow-ups that can be answered from recent tool context

### 3. Add Tool Context Continuation

Follow-ups should read from structured last-tool context, not only from text history.

Examples:
- `MSFT` -> last quote payload stored
- `jadikan idr` -> semantic continuation sees prior `stock_quote` context and chooses either:
  - lightweight post-processing path using last quote + fx lookup, or
  - LLM answer using recent tool result context

Similarly:
- weather result stores wind/temp/location
- stock result stores quote currency/exchange/name/ticker
- web research stores last query/domain/topic summary

### 4. Make Skills Follow the Same Contract

API skills should not depend on keyword matching. They should expose:
- capability name
- required env vars
- optional dependencies
- failure message contract

Semantic arbitration can then map `buatkan gambar mobil di hutan` to `image_generation`, and the runtime resolves the proper skill/tool. If API key is missing, the response should fail fast with a clear, localized setup error.

## Data Flow

1. Receive message.
2. Build route profile and lightweight context.
3. Run semantic intent arbitration.
4. If confidence is high and tool is deterministic-safe, use direct tool fast path.
5. Otherwise run normal LLM loop with tool availability and stronger guardrails.
6. Persist structured tool context for follow-ups.
7. Render status/typing/phase feedback as before.

## Error Handling

- Missing tool capability: do not hallucinate; fall back to regular chat.
- Missing API key for skills: fail-fast with user-facing setup error.
- Ambiguous tool intent: prefer no forced tool; let LLM ask or answer conservatively.
- Follow-up with insufficient context: ask one short clarification instead of forcing a tool.

## Testing Strategy

We need three layers of tests:

1. Pure arbitration tests:
- multilingual natural-language prompts
- free-form follow-ups
- non-action complaints/meta turns

2. Message runtime integration tests:
- pending follow-up tool/intents
- no stale tool inheritance
- structured last-tool context continuation

3. Live probes:
- Indonesian casual
- English conversational
- mixed shorthand/slang
- non-Latin scripts where current lexicon already claims support

## Expected Before / After

**Before**
- fast, but often rigid
- parser decides too early
- follow-up turns can inherit stale intent
- tools can be forced when a normal LLM answer would be better

**After**
- still fast on high-confidence operational asks
- more natural on discussion/advice/follow-up turns
- less keyword dependence
- closer to Openfang’s feel without removing Kabot’s safety rails
