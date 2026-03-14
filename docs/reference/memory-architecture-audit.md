# reference platform vs Kabot Memory Architecture

This note compares the real memory architecture in reference platform and Kabot after reading:

- `C:\Users\Arvy Kairi\Desktop\bot\STRUKTOR OPEN.txt`
- reference platform memory/runtime files under `reference-repo/src/memory/` and `reference-repo/src/agents/`
- Kabot memory/runtime files under `kabot/memory/`

The goal is not to claim the systems are identical. The goal is to separate:

1. what reference platform actually does,
2. where Kabot should stay similar,
3. where Kabot is already stronger and should keep that advantage.

## Short Verdict

reference platform is broader and more mature as a configurable memory-search platform.

Kabot is already stronger in one very important area:

- conversation-native memory,
- hybrid retrieval over live chat history and facts,
- SQLite durability for message chains,
- and subprocess-based embedding isolation that releases RAM much more decisively.

That means the best parity target is:

- keep reference-like routing, session continuity, and skill/tool philosophy,
- while keeping Kabot's stronger memory core.

## What `STRUKTOR OPEN.txt` Gets Right

The reference note is directionally accurate about reference platform:

- `src/agents/` is the orchestration core,
- `src/memory/` is a real hybrid-search subsystem,
- `src/gateway/` and `src/auto-reply/` provide the session/runtime shell around the agent,
- `src/browser/` and tool layers are separate capabilities, not magic parser shortcuts.

The important correction is that the file is still a high-level map, not the final source of truth.

For memory behavior, the code shows a more precise picture:

- the reference platform's built-in memory stack is SQLite-based and hybrid-aware,
- it can optionally swap to QMD,
- it supports vector, BM25, MMR, temporal decay, embedding cache, and session-memory indexing,
- but it is mostly built around indexed Markdown memory plus optional transcript search.

## reference platform Memory: What It Actually Does

## 1. Memory Is Config-Driven Per Agent

The core config resolution happens in:

- `reference-repo/src/agents/memory-search.ts`
- `reference-repo/src/memory/backend-config.ts`

Important details:

- store driver defaults to SQLite,
- hybrid search is enabled by default,
- default weights are `0.7` vector and `0.3` text,
- MMR and temporal decay exist but are off by default,
- session memory search is experimental and opt-in,
- storage path is per-agent SQLite, typically under `~/.reference-repo/memory/<agentId>.sqlite`.

This means the reference platform's memory is not "just vector search". It is a configurable retrieval pipeline.

## 2. Built-In Hybrid Search Is Real, Not Marketing

The relevant implementation lives in:

- `reference-repo/src/memory/hybrid.ts`
- `reference-repo/src/memory/manager-search.ts`
- `reference-repo/src/memory/manager-embedding-ops.ts`

The built-in pipeline includes:

- FTS query building,
- BM25 rank conversion,
- weighted vector + keyword merging,
- optional temporal decay,
- optional MMR reranking,
- SQLite embedding cache,
- sqlite-vec acceleration when available,
- JS fallback when vector acceleration is unavailable.

That is a serious local-first retrieval design.

## 3. reference platform Supports a Second Memory Backend: QMD

The relevant files are:

- `reference-repo/src/memory/qmd-manager.ts`
- `reference-repo/src/memory/backend-config.ts`
- `reference-repo/docs/concepts/memory.md`

QMD mode gives reference platform:

- collection-based indexing,
- separate update and embed phases,
- optional session export into searchable collections,
- external CLI-driven hybrid retrieval.

This is one of the reference platform's biggest strengths: it can move from built-in SQLite search to a more powerful sidecar backend without changing the user-facing tool concept.

## 4. reference platform Memory Scope Is More "Search Over Indexed Files"

This is the most important architectural nuance.

reference platform memory is excellent, but its default shape is closer to:

- indexed `MEMORY.md`,
- indexed `memory/**/*.md`,
- optional indexed session transcripts,
- tool-based retrieval of relevant snippets.

That is not the same as a full conversation-native relational memory core.

In practice, reference platform is very good at:

- searchable memory notes,
- semantic recall from durable Markdown,
- optional session retrieval,
- and clean snippet injection into prompts.

## Kabot Memory: What It Actually Does

## 1. Kabot Is Conversation-Native First

The core files are:

- `kabot/memory/sqlite_store.py`
- `kabot/memory/chroma_memory.py`
- `kabot/memory/sqlite_memory.py`

Kabot's SQLite metadata store persists much more than a plain note index:

- sessions,
- parent-child messages,
- facts,
- lessons,
- models,
- system logs,
- and links between stored messages and vector entries.

That means Kabot's memory is centered on the actual chat/runtime graph, not just indexed memory documents.

This is already closer to a mem0-style "operational memory for an assistant" than the reference platform's default Markdown-first memory layer.

## 2. Kabot Uses a Real Hybrid Retrieval Stack

The main implementation is in:

- `kabot/memory/chroma_memory.py`
- `kabot/memory/reranker.py`

The retrieval path includes:

- semantic vector search through Chroma,
- BM25 search over SQLite-fetched documents,
- route-aware search behavior,
- Reciprocal Rank Fusion (RRF),
- temporal decay on candidate ranking,
- optional MMR-like diversity selection,
- final reranking with threshold, top-k, and token budget.

This is not a thin wrapper around vector search.

It is a full hybrid stack tuned for assistant memory injection.

## 3. Kabot's Biggest Memory Advantage: Subprocess Embeddings

The key files are:

- `kabot/memory/sentence_embeddings.py`
- `kabot/memory/_embedding_worker.py`
- `tests/memory/test_memory_leak.py`

Unlike the reference platform's main in-process embedding manager architecture, Kabot can run sentence-transformer embeddings in a dedicated child process.

Why that matters:

- embedding models are heavy,
- Python's allocator often keeps arenas resident even after object deletion,
- a child process can be killed cleanly,
- the OS reclaims the full embedding-model RSS immediately.

Kabot's provider does all of this:

- starts a dedicated worker with `subprocess.Popen`,
- communicates over JSON lines,
- caches lightweight results in the parent,
- auto-unloads after idle timeout,
- and can fully terminate the worker to return memory to the OS.

That is a real operational advantage for long-running assistants on laptops, VPSes, and low-RAM hosts.

## 4. Kabot Also Has a Better Fail-Open Story for One-Shot Runs

The main file is:

- `kabot/memory/lazy_probe_memory.py`

This backend starts light:

- immediate SQLite path for session creation and recent history,
- hybrid backend loaded only if semantic memory work is actually needed,
- pending indexes flushed later,
- fallback to SQLite if hybrid search or indexing fails.

This gives Kabot a better "cheap one-shot, heavier when needed" memory lifecycle than a single always-heavy backend.

## 5. Kabot Can Mix Symbolic and Graph Memory

Relevant files:

- `kabot/memory/sqlite_store.py`
- `kabot/memory/graph_memory.py`
- `kabot/memory/memory_factory.py`

The graph layer is optional, but the architecture is already there.

That means Kabot can combine:

- relational chat history,
- long-term facts,
- hybrid semantic retrieval,
- and graph-style context summarization.

reference platform is strong in search-system breadth.
Kabot is strong in assistant-memory depth.

## Similarities Between reference platform and Kabot

These parts are genuinely aligned:

- both use SQLite as a durable local memory substrate,
- both support hybrid retrieval instead of vector-only search,
- both treat keyword search as important for exact tokens,
- both support recency/diversity improvements,
- both have provider abstractions for embeddings,
- both try to keep search usable even when one retrieval mode is degraded.

So parity should not mean rewriting Kabot into the reference platform's exact storage design.
Parity should mean keeping the good architectural shape:

- local-first,
- hybrid-aware,
- evidence-grounded,
- memory that degrades gracefully.

## Where reference platform Is Still Stronger

reference platform still wins in several areas:

## 1. Config Breadth and Surface Area

the reference platform's memory config surface is broader and more polished:

- provider selection,
- remote headers,
- batch settings,
- fallback chains,
- session-memory thresholds,
- sqlite-vec extension handling,
- and QMD backend switching.

## 2. Built-In SQLite Vector Acceleration

the reference platform's built-in engine can use `sqlite-vec` directly.

That keeps vector distance queries in the database when the extension is available, which is elegant and deployment-friendly.

## 3. Indexing Markdown Memory as a First-Class Tool

reference platform has a clean conceptual model for:

- `MEMORY.md`,
- `memory/*.md`,
- `memory_search`,
- `memory_get`.

This is especially good for agents that live in workspace notes and knowledge bases.

## 4. Search Manager Abstraction Is More Mature

The built-in manager + QMD split is a strong design.

Kabot's memory backends are already good, but the reference platform's search-manager abstraction is currently more standardized and operator-facing.

## Where Kabot Is Already Stronger

This is the part worth preserving.

## 1. Kabot Stores Real Assistant Memory, Not Just Searchable Notes

Kabot's SQLite schema includes:

- sessions,
- message chains,
- facts,
- lessons,
- models,
- system logs.

That is much closer to a working assistant brain than a pure searchable note index.

## 2. Kabot's Subprocess Embedding Worker Is Operationally Better

For RAM-sensitive environments, this is Kabot's clearest win.

reference platform has excellent embedding orchestration, batching, and caching.
Kabot has the stronger model-lifecycle isolation story.

If the design goal is:

- stable memory,
- lower idle RAM,
- full reclaim after embedding work,

Kabot's subprocess worker is the better shape.

## 3. Kabot's Lazy Probe Memory Is Better for One-Shot Agent Runs

`LazyProbeMemory` means:

- fast startup when the user just needs a simple turn,
- no forced heavy semantic boot,
- and no hard failure if the hybrid backend is unavailable.

That fits real CLI/chat workloads well.

## 4. Kabot's Memory Fits Live Multi-Turn Chat Better

Because Kabot stores session messages and facts directly, it is naturally better positioned for:

- profile memory,
- "call me X",
- "what do you remember about me",
- task continuity,
- and tool/result grounding across normal assistant turns.

This is exactly the kind of memory behavior users tend to feel immediately.

## Recommended Parity Direction

The best direction is:

1. keep reference-like routing, tool philosophy, and session continuity,
2. keep Kabot's stronger conversation-native memory,
3. keep Kabot's hybrid retrieval and subprocess embedding worker,
4. continue reducing brittle parser-heavy routing so the model and memory can do more of the real work.

In other words:

- make Kabot behave more like reference platform,
- but do not downgrade Kabot's memory architecture just to imitate file layout or config naming.

## Practical Design Rule

If a design decision makes Kabot more like reference platform in:

- session continuity,
- skill-first behavior,
- AI-driven routing,
- or tool honesty,

that is usually good.

If a design decision would make Kabot weaker than it already is in:

- memory durability,
- hybrid recall,
- subprocess isolation,
- or fail-open startup behavior,

that is the wrong kind of parity.

## Bottom Line

reference platform is the stronger reference for:

- session orchestration,
- tool surface design,
- skill-first behavior,
- and searchable workspace memory systems.

Kabot is already the stronger base for:

- assistant-native memory,
- chat/fact persistence,
- hybrid recall over live history,
- and subprocess-controlled embedding lifecycle.

That should remain the target:

- **reference-like interaction logic**
- **Kabot-strong memory core**

## Related Reading

- [reference platform File Continuity](reference-file-continuity.md)
- [reference platform Repo Reference](reference-repo-reference.md)
- [Memory Guide](../guide/memory.md)
