# Phase 7: Vector Memory Implementation Plan

> **Goal:** Enable semantic search over long-term memory using ChromaDB embeddings, matching OpenClaw's `memory-search` capability.

## Task 20: Vector Store Interface

**Files:**
- Create: `kabot/memory/vector_store.py`
- Test: `tests/memory/test_vector.py`

**Goal:** Interface for vector storage (ChromaDB or simple FAISS wrapper) to enable semantic search.

**Step 1: Write failing test**

```python
# tests/memory/test_vector.py
import pytest
from kabot.memory.vector_store import VectorStore

def test_add_and_search():
    store = VectorStore(collection_name="test_mem")
    store.add(
        documents=["The cat sat on the mat", "Dogs are loyal"],
        ids=["1", "2"]
    )
    
    results = store.search("feline", k=1)
    assert len(results) == 1
    assert results[0].id == "1"
    assert "cat" in results[0].content
```

**Step 2: Implement VectorStore (using chromadb)**

```python
# kabot/memory/vector_store.py
import chromadb
from dataclasses import dataclass

@dataclass
class SearchResult:
    id: str
    content: str
    # score: float

class VectorStore:
    def __init__(self, path: str = "./kabot_data", collection_name: str = "memory"):
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(collection_name)
        
    def add(self, documents: list[str], ids: list[str]):
        self.collection.upsert(
            documents=documents,
            ids=ids
        )
        
    def search(self, query: str, k: int = 3) -> list[SearchResult]:
        results = self.collection.query(
            query_texts=[query],
            n_results=k
        )
        
        output = []
        if results["ids"]:
            for i, id in enumerate(results["ids"][0]):
                content = results["documents"][0][i]
                output.append(SearchResult(id=id, content=content))
        return output
```

**Step 3: Run tests, commit**

```bash
pip install chromadb
pytest tests/memory/test_vector.py -v
git commit -m "feat(memory): add vector store with chromadb"
```

---

## Task 21: Semantic Search Tool

**Files:**
- Create: `kabot/agent/tools/memory_search.py`
- Modify: `kabot/agent/loop.py`
- Test: `tests/tools/test_memory_search.py`

**Goal:** Tool for agent to search memory semantically: `memory_search.execute(query="what did we discuss about sharks?")`

**Step 1: Implement MemorySearchTool**

```python
# kabot/agent/tools/memory_search.py
from kabot.agent.tools.base import Tool
from kabot.memory.vector_store import VectorStore

class MemorySearchTool(Tool):
    def __init__(self, store: VectorStore):
        self.store = store
        
    @property
    def name(self) -> str:
        return "memory_search"
        
    @property
    def description(self) -> str:
        return "Search memory for relevant past conversations and facts."
        
    def execute(self, query: str, **kwargs) -> str:
        results = self.store.search(query)
        if not results:
            return "No relevant memories found."
            
        return "\n\n".join([f"- {r.content}" for r in results])
```

**Step 2: Register tool and commit**

```bash
git commit -m "feat(tools): add semantic memory search tool"
```
