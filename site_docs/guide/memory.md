# Memory Guide

Kabot supports multiple memory strategies so you can choose between capability and footprint.

## Main Memory Idea

Kabot is designed to avoid the usual "stateless chatbot" feel.

Depending on configuration, Kabot can retain:
- session history
- useful facts and preferences
- retrieved contextual knowledge
- graph-like relationship context

The goal is not to hoard every message forever.

The goal is to keep the right information available at the right time without destroying latency or token budget.

## Memory Modes

### Lightweight / Simple Paths
Best when you need:
- low RAM usage
- simpler environments
- reduced overhead on small machines

### Hybrid Memory
Best when you need:
- stronger retrieval quality
- richer context reuse
- longer-term knowledge behavior
- better semantic and keyword blending

## How To Choose

Use this rough rule:

| Situation | Better Starting Choice |
| --- | --- |
| laptop with limited RAM | lightweight path |
| small VPS | lightweight path |
| Termux | lightweight path first |
| personal workstation with more headroom | hybrid memory |
| long-running knowledge-heavy workflow | hybrid memory |

## Why Memory Choice Matters

Memory affects:
- latency
- RAM/disk footprint
- retrieval quality
- how much context Kabot can reuse across runs

It also affects how Kabot feels:
- quick and light
- or deeper and more context-rich

## Operational Advice

Use lightweight memory first if you are on:
- low-RAM laptops
- VPS with strict resource limits
- Termux devices

Use hybrid memory when you want:
- stronger recall
- better semantic retrieval
- more advanced project continuity

## What Memory Is Not

Memory is not a guarantee that Kabot will perfectly remember every conversational correction forever.

Real behavior depends on:
- session continuity
- what memory mode is active
- retrieval thresholds
- runtime path
- whether the relevant fact was persisted or only present in short-lived context

## Architecture Direction

Kabot's memory architecture uses layered ideas such as:
- persistent stores for history/facts
- hybrid retrieval strategies
- reranking and token-guard behavior
- lazy initialization paths to reduce cold-start cost
- subprocess-isolated embeddings so heavy local models can be unloaded decisively

This is why some recent runtime work focused on:
- lazy probe memory paths
- lighter one-shot startup
- better balance between memory power and cold-start speed
- stronger separation between durable chat memory and heavyweight embedding lifecycles

## Memory Layers In Practice

Kabot's current memory stack can combine several layers:

- SQLite durability for sessions, messages, facts, and operational metadata
- hybrid recall with vector search plus BM25-style keyword search
- reranking and token guards before prompt injection
- optional graph memory for related-entity context
- subprocess-based embedding workers that can fully release RAM after idle time

That last point matters more than it sounds.

Embedding models are often the most expensive part of local memory search. Kabot can keep lightweight session memory available while unloading the heavy embedding process when it is not needed.

## Design Direction

The right interaction target for Kabot is:

- skill-first interaction
- session continuity
- tool honesty
- workspace and route orchestration

Kabot should stay strong there.

But Kabot does not need to copy another project's memory shape exactly.

Kabot is already stronger in some memory-specific areas:

- conversation-native persistence
- fact/profile memory tied directly to chat
- lazy probe startup for one-shot runs
- subprocess embedding isolation

That is the parity target:

- make interaction logic more session-first and evidence-driven,
- keep Kabot's stronger memory core.

## Recent Runtime Improvements

Recent work improved memory-related startup behavior by introducing lighter probe paths for one-shot runs before heavy memory systems are needed.

That means simple one-shot prompts do not always have to pay the full cost of booting a heavier memory stack immediately.

## Memory And Performance

If Kabot feels slow, memory may be only one part of the reason.

Latency can come from:
- provider/model response time
- context assembly
- skill loading
- memory initialization
- retrieval and reranking cost

Good debugging sequence:

1. verify model latency separately
2. test one-shot prompt
3. compare with interactive session
4. test lighter memory mode
5. only then decide whether memory is the main bottleneck

## Memory On Different Environments

### Windows

Usually fine for normal local usage, but heavy embedding or indexing workloads still depend on machine size.

### macOS / Linux

Often good for always-on background runs, especially on a mini server or workstation.

### Termux

Needs the most care:
- lighter models
- lighter memory
- smaller expectations for always-on heavy retrieval

## Good Practices

- start light
- measure first
- only enable heavier memory paths when they solve a real problem
- keep one or two smoke prompts for memory-sensitive checks

## When To Go Advanced

Move to the advanced/runtime docs when you want to reason about:
- hybrid retrieval trade-offs
- memory architecture design
- startup optimization
- long-running project continuity strategies

## Related Pages

- [Troubleshooting](troubleshooting.md)
- [Advanced runtime architecture](../advanced/runtime-architecture.md)
- [Multi-agent guide](multi-agent.md)

Internal parity audits live in the repository under `docs/reference/`.

## If You See Memory-Related Slowdowns

- reduce advanced memory load
- test one-shot prompts separately
- use `kabot doctor smoke-agent`
- prefer lighter models and smaller memory footprints on constrained machines
