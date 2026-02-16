# Kabot Intelligence Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade Kabot with enterprise-grade features (Auto-Retry, Hybrid Memory, Adaptive Context) to match OpenClaw's capabilities.

**Architecture:**
1.  **Auto-Retry**: Implement `tenacity` retry logic with smart fallback chain (Primary -> Fallback -> Backup).
2.  **Hybrid Memory**: Combine Vector Search (ChromaDB) with Keyword Search (BM25) using Reciprocal Rank Fusion (RRF).
3.  **Adaptive Context**: Use a lightweight "Router" LLM to classify intent and dynamically build system prompts.

**Tech Stack:** Python 3.11+, `tenacity`, `rank_bm25`, `chromadb`, `litellm`.

---

### Task 1: Add Dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add new dependencies**

Add `tenacity` and `rank_bm25` to the dependencies list in `pyproject.toml`.

```toml
dependencies = [
    # ... existing ...
    "tenacity>=8.2.0",
    "rank_bm25>=0.2.2",
]
```

**Step 2: Install dependencies**

Run: `pip install tenacity rank_bm25`

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add tenacity and rank_bm25 dependencies"
```

---

### Task 2: Implement Auto-Retry & Failover

**Files:**
- Modify: `kabot/providers/litellm_provider.py`
- Modify: `kabot/config/schema.py`

**Step 1: Add fallback configuration schema**

Update `ProviderConfig` in `kabot/config/schema.py` to support `fallbacks` list.

```python
class ProviderConfig(BaseModel):
    # ... existing ...
    fallbacks: list[str] = Field(default_factory=list)  # List of model IDs to try on failure
```

**Step 2: Implement retry logic in LiteLLMProvider**

Modify `kabot/providers/litellm_provider.py` to use `tenacity`.

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import litellm

class LiteLLMProvider(LLMProvider):
    # ... existing ...

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((litellm.RateLimitError, litellm.APIConnectionError, litellm.ServiceUnavailableError)),
        reraise=True
    )
    async def _chat_attempt(self, kwargs):
        return await acompletion(**kwargs)

    async def chat(self, ...):
        # ... resolve model ...

        # Build list of models to try: [primary, *fallbacks]
        models_to_try = [model]
        # (Logic to get fallbacks from config if available)

        last_exception = None

        for current_model in models_to_try:
            try:
                kwargs["model"] = current_model
                response = await self._chat_attempt(kwargs)
                return self._parse_response(response)
            except Exception as e:
                logger.warning(f"Model {current_model} failed: {e}")
                last_exception = e
                continue

        raise last_exception
```

**Step 3: Commit**

```bash
git add kabot/providers/litellm_provider.py kabot/config/schema.py
git commit -m "feat: implement auto-retry and failover logic"
```

---

### Task 3: Implement Hybrid Memory (BM25 + Vector)

**Files:**
- Modify: `kabot/memory/chroma_memory.py`

**Step 1: Initialize BM25 Index**

Add `rank_bm25` initialization in `__init__` and `_build_bm25_index` method.

```python
from rank_bm25 import BM25Okapi

class ChromaMemoryManager:
    def __init__(self, ...):
        # ... existing ...
        self.bm25 = None
        self.bm25_corpus = [] # List of (message_id, content)
        self._build_bm25_index()

    def _build_bm25_index(self):
        # Load all messages from SQLite
        # Tokenize
        # self.bm25 = BM25Okapi(tokenized_corpus)
```

**Step 2: Update BM25 on new message**

Update `add_message` to append to corpus and re-initialize BM25 (or partial update if possible, usually re-init for BM25Okapi).

**Step 3: Implement Hybrid Search**

Update `search_memory` to perform RRF.

```python
    async def search_memory(self, query, ...):
        # 1. Vector Search
        vector_results = ... # existing logic

        # 2. Keyword Search
        tokenized_query = query.split(" ")
        bm25_scores = self.bm25.get_scores(tokenized_query)
        top_bm25_indices = np.argsort(bm25_scores)[-limit:]

        # 3. Fuse Results (RRF Algorithm)
        # RRF Score = 1 / (k + rank)
        # Combine and sort
```

**Step 4: Commit**

```bash
git add kabot/memory/chroma_memory.py
git commit -m "feat: implement hybrid memory with BM25 and RRF"
```

---

### Task 4: Implement Adaptive Context (AI Router)

**Files:**
- Create: `kabot/agent/router.py`
- Modify: `kabot/agent/context.py`
- Modify: `kabot/agent/loop.py`

**Step 1: Create Intent Router**

Create `kabot/agent/router.py` to classify user intent.

```python
class IntentRouter:
    def __init__(self, provider):
        self.provider = provider
        self.router_model = "groq/llama-3.1-8b-instant" # Fast model

    async def classify(self, message: str) -> str:
        # Prompt: "Classify this message into: CODING, CHAT, RESEARCH..."
        # Return label
```

**Step 2: Update Context Builder**

Modify `kabot/agent/context.py` to support profiles.

```python
PROFILES = {
    "CODING": "You are a coding expert...",
    "CHAT": "You are a friendly assistant...",
}

class ContextBuilder:
    def build_system_prompt(self, profile="DEFAULT", ...):
        # ... logic to inject profile instructions ...
```

**Step 3: Integrate into Agent Loop**

Modify `kabot/agent/loop.py` to call router before main chat.

```python
    async def _process_message(self, msg):
        # 1. Route
        intent = await self.router.classify(msg.content)

        # 2. Build Context
        messages = self.context.build_messages(..., profile=intent)

        # 3. Chat
```

**Step 4: Commit**

```bash
git add kabot/agent/router.py kabot/agent/context.py kabot/agent/loop.py
git commit -m "feat: implement adaptive context with AI router"
```

---
