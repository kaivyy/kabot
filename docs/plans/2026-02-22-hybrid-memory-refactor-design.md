# Hybrid Memory Architecture Refactor — Design Document

**Date:** 2026-02-22
**Goal:** Refactor Kabot's memory system into a modular `HybridMemoryManager` that **exceeds Mem0** capabilities while being token-efficient, RAM-light, anti-hallucination, and supporting high-level contextual understanding.

---

## 1. Current State Analysis

### Files & Line Counts
| File | Lines | Role |
|---|---|---|
| `chroma_memory.py` | 782 | Main orchestrator (monolithic) |
| `sqlite_store.py` | 522 | Metadata + 7 tables |
| `vector_store.py` | 73 | Simple ChromaDB wrapper (Phase 7 legacy) |
| `sentence_embeddings.py` | 140 | Local embedding (all-MiniLM-L6-v2) |
| `ollama_embeddings.py` | 105 | Ollama embedding (nomic-embed-text) |
| `__init__.py` | 14 | Package exports |

### Integration Points (3 files reference `ChromaMemoryManager`)
1. **`agent/loop.py:137-140`** — Instantiation: `self.memory = ChromaMemoryManager(workspace / "memory_db", ...)`
2. **`agent/tools/memory.py:9,39,105`** — `SaveMemoryTool` and `GetMemoryTool` inject `ChromaMemoryManager`
3. **`memory/__init__.py:3,9`** — Re-exports

### Existing Capabilities ✅
- ChromaDB vector search (cosine HNSW)
- BM25 keyword search (rank_bm25)
- RRF (Reciprocal Rank Fusion) merging
- Temporal Decay weighting (exponential, configurable half-life)
- MMR (Maximal Marginal Relevance) diversity
- SQLite parent-child message chains
- Metacognition lessons + guardrails
- Session compaction (summarize old messages)
- Embedding cache (MD5-keyed, 1000 items)

### Missing Capabilities ❌
- **Smart Router** — every query hits both engines wastefully
- **Auto-Extract** — user preferences only saved via explicit `save_memory` tool call
- **Token Guard** — no hard cap on memory injection into LLM context
- **Auto-Pruning** — no scheduled cleanup of stale facts/memories
- **Deduplication** — facts can be stored multiple times
- **Cross-Channel Memory** — no merging of user data across Telegram/WhatsApp/etc.

---

## 2. Target Architecture

```
HybridMemoryManager (orchestrator)
  ├── KnowledgeStore       ← ChromaDB collection "knowledge" (static docs, facts)
  ├── EpisodicStore        ← ChromaDB collection "episodic" (conversations, preferences)
  ├── SmartRouter          ← Classify query intent → route to correct store
  ├── Reranker             ← Cross-score + threshold filter (upgrade from MMR)
  ├── TokenGuard           ← Hard cap on total injected tokens
  ├── EpisodicExtractor    ← LLM-based auto-extraction of user facts post-chat
  ├── Deduplicator         ← BM25+cosine check before inserting new facts
  └── MemoryPruner         ← Scheduled cleanup via CronService
```

### Data Flow
```
Query → SmartRouter → [episodic|knowledge|both]
                          ↓
              Parallel search (ChromaDB + BM25)
                          ↓
              RRF Fusion + Temporal Decay
                          ↓
              Reranker (threshold ≥ 0.6, top-k=3)
                          ↓
              TokenGuard (hard cap 500 tokens)
                          ↓
              → Inject into LLM context
```

### Post-Chat Flow
```
Chat ends → EpisodicExtractor (LLM mini-call)
                ↓
        Extract: preferences, facts, entities
                ↓
        Deduplicator (BM25+cosine check)
                ↓
        Store unique items → EpisodicStore
```

---

## 3. New Module Specifications

### 3.1 SmartRouter (`smart_router.py`)
```python
class SmartRouter:
    """Classify queries into episodic/knowledge/hybrid routing."""
    EPISODIC_KEYWORDS: list[str]   # "ingat", "tadi", "kamu", "sebelumnya", "suka"
    KNOWLEDGE_KEYWORDS: list[str]  # "apa itu", "jelaskan", "cara", "bagaimana"
    
    def route(query: str) -> Literal["episodic", "knowledge", "hybrid"]
```
- Rule-based first (zero cost), LLM fallback only for ambiguous cases
- Multilingual keywords (ID, EN, ES, FR, JA, ZH, KO, TH)

### 3.2 Reranker (`reranker.py`)
```python
class Reranker:
    """Score, filter, and cap memory results before injection."""
    threshold: float = 0.6    # minimum relevance score
    top_k: int = 3            # max results after filtering
    max_tokens: int = 500     # hard token budget
    
    def rank(query: str, results: list[dict]) -> list[dict]
    def _token_guard(results: list[dict]) -> list[dict]
```
- Replaces raw MMR with threshold + token-aware filtering
- Inherits existing `_cosine_similarity` and `_normalize_scores` from current code

### 3.3 EpisodicExtractor (`episodic_extractor.py`)
```python
class EpisodicExtractor:
    """Auto-extract user preferences/facts from conversations using LLM."""
    
    async def extract(messages: list[dict], provider: LLMProvider) -> list[ExtractedFact]
    async def _deduplicate(facts: list[ExtractedFact], store: EpisodicStore) -> list[ExtractedFact]
```
- Runs **after** each chat session ends (async, non-blocking)
- Uses the **same LLM provider** already in Kabot (no new API key needed)
- Prompt: extract preferences, entities, habits in JSON format
- Dedup: BM25 search existing facts, skip if cosine similarity > 0.85

### 3.4 TokenGuard (`token_guard.py`)
```python
class TokenGuard:
    """Enforce hard token budget for memory injection."""
    max_tokens: int = 500
    
    def guard(results: list[dict]) -> list[dict]
    def count_tokens(text: str) -> int  # word-count × 1.3 heuristic
```

### 3.5 MemoryPruner (`memory_pruner.py`)
```python
class MemoryPruner:
    """Scheduled cleanup of stale memories."""
    
    async def prune(store: SQLiteMetadataStore, max_age_days: int = 30) -> int
    async def prune_duplicates(store: SQLiteMetadataStore) -> int
```
- Integrates with existing `CronService` as a background job
- Deletes facts older than configurable threshold
- Merges duplicate facts (keeps highest confidence)

---

## 4. Refactoring Plan

### 4.1 Files to MODIFY

| File | Changes |
|---|---|
| `chroma_memory.py` | Rename class → `HybridMemoryManager`. Split single ChromaDB collection into 2 (`knowledge`, `episodic`). Import and wire `SmartRouter`, `Reranker`, `TokenGuard`. Move MMR/RRF/decay logic into `Reranker`. |
| `__init__.py` | Update exports: add `HybridMemoryManager`, keep `ChromaMemoryManager` as alias for backward compatibility. |
| `agent/loop.py:137-140` | Change `ChromaMemoryManager(...)` → `HybridMemoryManager(...)`. Add post-chat extraction hook. |
| `agent/tools/memory.py:9` | Update import to `HybridMemoryManager`. |

### 4.2 Files to CREATE

| File | Purpose |
|---|---|
| `memory/smart_router.py` | Query intent classification |
| `memory/reranker.py` | Score filtering + token guard |
| `memory/episodic_extractor.py` | Auto-extract user facts |
| `memory/memory_pruner.py` | Scheduled cleanup |
| `tests/memory/test_smart_router.py` | Unit tests for routing |
| `tests/memory/test_reranker.py` | Unit tests for scoring/filtering |
| `tests/memory/test_episodic_extractor.py` | Unit tests for extraction |
| `tests/memory/test_hybrid_memory.py` | Integration test for full pipeline |
| `tests/memory/test_memory_pruner.py` | Unit tests for pruning |

### 4.3 Files UNCHANGED
- `sqlite_store.py` — Schema stays identical, no migration needed
- `sentence_embeddings.py` — Provider interface unchanged
- `ollama_embeddings.py` — Provider interface unchanged
- `vector_store.py` — Legacy wrapper, kept for Phase 7 backward compat

---

## 5. Backward Compatibility

- `ChromaMemoryManager` will be kept as an **alias** in `__init__.py`:
  ```python
  ChromaMemoryManager = HybridMemoryManager  # backward compat
  ```
- All existing method signatures (`add_message`, `search_memory`, `remember_fact`, `get_conversation_context`, etc.) remain identical
- Existing SQLite tables remain unchanged — zero migration
- Existing ChromaDB collection `kabot_memory` auto-migrates to `knowledge` collection on first access

---

## 6. Performance Targets

| Metric | Before | After | Improvement |
|---|---|---|---|
| Token injection per turn | ~800-1800 | ~300-500 | **60-72% reduction** |
| Search latency (hybrid) | ~200ms | ~150-250ms | Comparable (router saves one DB hit) |
| RAM overhead | ~0 MB extra | ~0 MB extra | No new dependencies |
| Fact deduplication | None | BM25+cosine | **Zero duplicates** |
| Auto-extraction accuracy | Manual only | LLM-based | **Automatic preference learning** |

---

## 7. Test Strategy (pytest)

```
tests/memory/
├── test_smart_router.py        # 8 test cases (routing accuracy per language)
├── test_reranker.py            # 6 test cases (threshold, top-k, token guard)
├── test_episodic_extractor.py  # 5 test cases (extraction, dedup, empty input)
├── test_hybrid_memory.py       # 4 test cases (end-to-end search pipeline)
└── test_memory_pruner.py       # 4 test cases (age-prune, dedup-prune)
```

Run: `pytest tests/memory/ -v`

---

## 8. CHANGELOG Entry (preview)

```markdown
## [0.5.0] - 2026-02-22

### Added - Hybrid Memory Architecture (Exceeds Mem0)
- **HybridMemoryManager:** Modular memory orchestrator with separated Knowledge and Episodic stores.
- **Smart Router:** Query-intent classifier routes to correct memory store (episodic/knowledge/hybrid). Multilingual keyword matching (ID, EN, ES, FR, JA, ZH, KO, TH).
- **Reranker:** Cross-score filtering with configurable threshold (0.6), top-k (3), and hard token guard (500 tokens max).
- **Episodic Extractor:** LLM-based auto-extraction of user preferences, facts, and entities after each chat session.
- **Memory Pruner:** Scheduled cleanup of stale memories (>30 days) and duplicate fact merging.
- **Deduplicator:** BM25 + cosine similarity check prevents duplicate fact storage.
- 27 new pytest test cases across 5 test files.
```
