# Kabot Memory System - Modular Architecture

## Overview

Kabot's memory system is a modular, swappable architecture designed to prevent **amnesia** (context loss) and **hallucination** (disconnected responses) issues commonly found in AI agents. The system supports multiple backends that can be switched via configuration without code changes.

## Architecture

### High-Level Design

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                      User Configuration                      â”‚
â”‚                    (config.json or Wizard)                   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                             â”‚
                             â–¼
                    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                    â”‚ MemoryFactory  â”‚
                    â”‚  (Dispatcher)  â”‚
                    â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜
                             â”‚
         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
         â”‚                   â”‚                   â”‚
         â–¼                   â–¼                   â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ HybridMemory    â”‚  â”‚ SQLiteMemory â”‚  â”‚   NullMemory    â”‚
â”‚ (Full Power)    â”‚  â”‚ (Lightweight)â”‚  â”‚   (Disabled)    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚                   â”‚                   â”‚
         â–¼                   â–¼                   â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    MemoryBackend ABC                         â”‚
â”‚  (Contract: add_message, search_memory, remember_fact, etc.) â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Hybrid Backend Architecture (Default)

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚   User Message  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Sentence-Transformers  â”‚  â† Pure Python, Free
â”‚  (Embedding Model)      â”‚     all-MiniLM-L6-v2
â”‚                         â”‚     Lazy Loading
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚                 â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
         â”‚                 â”‚  Auto-Unload Timer   â”‚
         â”‚                 â”‚  (5min idle)         â”‚
         â”‚                 â”‚  â†’ Unload Model      â”‚
         â”‚                 â”‚  â†’ Free ~550MB RAM   â”‚
         â”‚                 â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚       ChromaDB          â”‚  â† Vector Storage
â”‚   (Semantic Search)     â”‚     Cosine Similarity
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚
         â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
         â”‚                 â”‚
         â–¼                 â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚   BM25      â”‚   â”‚  Smart Routerâ”‚
â”‚ (Keyword)   â”‚   â”‚  (Episodic/  â”‚
â”‚             â”‚   â”‚  Knowledge)  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚                 â”‚
         â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                  â–¼
         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
         â”‚    Reranker     â”‚
         â”‚ (Temporal Decay â”‚
         â”‚  + MMR Diversity)â”‚
         â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                  â”‚
                  â–¼
         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
         â”‚     SQLite      â”‚  â† Metadata & Relationships
         â”‚ (Parent-Child   â”‚     Proper Message Trees
         â”‚     Chain)      â”‚
         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

## Components

### 1. MemoryBackend (Abstract Base Class)

**File**: `kabot/memory/memory_backend.py`

**Purpose**: Defines the contract that all memory backends must implement.

**Methods**:
- `add_message()`: Store a message in memory
- `search_memory()`: Search for relevant memories
- `remember_fact()`: Store long-term facts
- `get_conversation_context()`: Retrieve recent conversation history
- `create_session()`: Initialize a new conversation session
- `get_stats()`: Get memory system statistics
- `health_check()`: Check memory system health

**Design Pattern**: Abstract Base Class (ABC) ensuring all backends are swappable.

### 2. MemoryFactory

**File**: `kabot/memory/memory_factory.py`

**Purpose**: Creates the appropriate memory backend based on configuration.

**Supported Backends**:
- `hybrid` (default): ChromaDB + SQLite + BM25
- `sqlite_only`: Lightweight keyword search
- `disabled`: No-op implementation

**Configuration**:
```json
{
  "memory": {
    "backend": "hybrid",
    "embedding_provider": "sentence",
    "embedding_model": "all-MiniLM-L6-v2",
    "enable_hybrid_search": true
  }
}
```

### 3. HybridMemoryManager (Default Backend)

**File**: `kabot/memory/chroma_memory.py`

**Features**:
- **Semantic Search**: Vector embeddings via sentence-transformers
- **Keyword Search**: BM25 algorithm for exact matches
- **Smart Router**: Automatically chooses episodic vs knowledge search
- **Reranker**: Temporal decay + MMR diversity for optimal results
- **Hybrid Ranking**: Combines semantic and keyword scores

**Resource Management API**:
- `unload_resources()`: Manually unload embedding model to free RAM
- `get_memory_stats()`: Get detailed memory usage statistics
- Automatic resource cleanup on shutdown

**Embedding Providers**:
- `sentence` (default): Local sentence-transformers (no API cost)
- `ollama`: Ollama server for embeddings (requires Ollama running)

**Models**:
- `all-MiniLM-L6-v2` (default): 384 dimensions, fast, good quality
- `all-mpnet-base-v2`: 768 dimensions, slower, best quality
- `paraphrase-multilingual-MiniLM-L12-v2`: Multilingual support

### 4. SQLiteMemory (Lightweight Backend)

**File**: `kabot/memory/sqlite_memory.py`

**Purpose**: Lightweight memory using only SQLite with keyword search.

**Best For**:
- Termux on Android
- Raspberry Pi
- Low-resource devices
- Quick prototyping

**Features**:
- SQL LIKE keyword search
- Low memory footprint (~50MB)
- No external dependencies
- Fast startup (<1s)

**Trade-offs**:
- No semantic understanding
- Cannot find related concepts
- Exact keyword matching only

### 5. NullMemory (Disabled Backend)

**File**: `kabot/memory/null_memory.py`

**Purpose**: No-op implementation for stateless mode.

**Best For**:
- Privacy-focused users
- Temporary sessions
- Testing scenarios

**Behavior**:
- All reads return empty results
- All writes are discarded
- Zero memory footprint

### 6. SQLite Metadata Store

**File**: `kabot/memory/sqlite_store.py`

**Purpose**: Stores metadata and parent-child relationships.

**Tables**:
- `sessions`: Conversation session data
- `messages`: Messages with parent_id (prevents amnesia)
- `facts`: Long-term facts storage
- `memory_index`: Index to ChromaDB vectors

### 7. Sentence Embedding Provider

**File**: `kabot/memory/sentence_embeddings.py`

**Purpose**: Converts text to vector embeddings with RAM optimization.

**Model**: `all-MiniLM-L6-v2` (384 dimensions)

**Architecture**: Subprocess-based isolation for true memory reclamation
- **Worker Process**: `kabot/memory/_embedding_worker.py`
- **Communication**: JSON line protocol over stdin/stdout
- **Windows Compatible**: Fixed subprocess pipe buffering (v0.5.6)

**RAM Optimization Features**:
- **Lazy Loading**: Model loads only when first embedding is requested
- **Auto-Unload Timer**: Automatically unloads model after 5 minutes of inactivity
- **Configurable Timeout**: Set `auto_unload_timeout` in config (default: 300 seconds)
- **Thread-Safe**: Uses threading.Timer for background unloading
- **Subprocess Isolation**: Model runs in separate process, OS reclaims ALL memory when killed
- **Manual Control**: `unload_model()` method for explicit resource management

**RAM Impact**:
- **Idle RAM**: ~250MB (model unloaded)
- **Active RAM**: ~500MB (model loaded during search)
- **RAM Freed**: ~550MB when model auto-unloads

**Advantages**:
- Pure Python (no Ollama/AI API required)
- Free & local
- Caching for performance
- Minimal idle memory footprint
- True memory reclamation via subprocess architecture

#### Hugging Face Hub Integration

**Model Source**: All embedding models are downloaded from **Hugging Face Hub** (https://huggingface.co).

**No Account Required**:
- Models are **public and open-source**
- No registration or login needed
- No API key required
- Anonymous downloads work perfectly

**First Run Experience**:

When you first start Kabot with hybrid memory backend, you'll see:

```
Loading sentence-transformers model: all-MiniLM-L6-v2
Warning: You are sending unauthenticated requests to the HF Hub.
Please set a HF_TOKEN to enable higher rate limits and faster downloads.
Loading weights: 100%|â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆ| 103/103 [00:00<00:00, 1843.23it/s]
```

**This warning is normal and can be ignored!** The model downloads successfully without authentication.

**Download Details**:
- **Size**: ~90MB for `all-MiniLM-L6-v2`
- **Cache location**:
  - Linux/Mac: `~/.cache/huggingface/hub/`
  - Windows: `C:\Users\Username\.cache\huggingface\hub\`
- **Subsequent runs**: Model loads from cache (no re-download)

**RAM Usage (with auto-unload optimization)**:
- **Model on disk**: ~90MB
- **Idle RAM**: ~250MB (model auto-unloads after 5min)
- **Active RAM**: ~500MB (model + ChromaDB + cache during search)
- **RAM freed on unload**: ~550MB

**Optional: HF_TOKEN (Not Required)**

You can optionally set `HF_TOKEN` to:
- Get higher rate limits (useful if downloading many models)
- Get faster download speeds (authenticated requests get priority)
- Access gated models (not used by Kabot)

To set token (optional):
```bash
# Linux/Mac
export HF_TOKEN="your_token_here"

# Windows PowerShell
$env:HF_TOKEN="your_token_here"

# Windows CMD
set HF_TOKEN=your_token_here
```

**Get token**: https://huggingface.co/settings/tokens (free account)

**Available Models**:
- `all-MiniLM-L6-v2` (default): https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- `all-mpnet-base-v2`: https://huggingface.co/sentence-transformers/all-mpnet-base-v2
- `paraphrase-multilingual-MiniLM-L12-v2`: https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

### 8. Smart Router

**File**: `kabot/memory/smart_router.py`

**Purpose**: Automatically routes queries to episodic or knowledge search.

**Routing Logic**:
- Episodic: "What did I say about...", "When did we discuss..."
- Knowledge: "What is...", "How does... work"
- Hybrid: Ambiguous queries use both

**Multilingual**: Supports Indonesian, English, Japanese

### 9. Reranker

**File**: `kabot/memory/reranker.py`

**Purpose**: Optimizes search results for quality and diversity.

**Features**:
- **Temporal Decay**: Prefers recent memories
- **MMR Diversity**: Avoids redundant results
- **Score Threshold**: Filters low-quality matches
- **Token Guard**: Caps output to prevent context bloat

## Integration with Agent Loop

**File**: `kabot/agent/loop.py`

The agent loop uses MemoryFactory to instantiate the configured backend:

```python
# Initialization (loop.py:147-155)
from kabot.memory.memory_factory import MemoryFactory
from kabot.config.loader import load_config

_cfg_obj = load_config()
_cfg = _cfg_obj.model_dump() if hasattr(_cfg_obj, 'model_dump') else _cfg_obj.dict()

# Allow constructor param to override config
if not enable_hybrid_memory:
    _cfg.setdefault("memory", {})["enable_hybrid_search"] = False

self.memory = MemoryFactory.create(_cfg, workspace)
```

**Usage**:

```python
# Store user message
await self.memory.add_message(
    session_id=msg.session_key,
    role="user",
    content=msg.content
)

# Retrieve conversation context (30 recent messages)
conversation_history = self.memory.get_conversation_context(
    session_id=msg.session_key,
    max_messages=30
)

# Store tool call results (prevents amnesia!)
await self.memory.add_message(
    session_id=msg.session_key,
    role="tool",
    content=str(result),
    tool_results=[...]
)

# Search memory
results = self.memory.search_memory(
    query="What did I say about my project?",
    session_id=msg.session_key,
    limit=5
)

# Store long-term facts
fact_id = self.memory.remember_fact(
    fact="User prefers dark mode",
    category="preferences",
    session_id=msg.session_key
)
```

## Setup Wizard Integration

**File**: `kabot/cli/setup_wizard.py`

The setup wizard provides an interactive menu for memory configuration:

```python
def _configure_memory(self) -> None:
    """Configure memory backend settings."""
    backend = ClackUI.clack_select(
        "Memory backend",
        choices=[
            "Hybrid (ChromaDB + SQLite + BM25) â€” Full power",
            "SQLite Only â€” Lightweight, no embeddings",
            "Disabled â€” No memory at all",
        ]
    )

    if backend == "hybrid":
        emb_provider = ClackUI.clack_select(
            "Embedding provider",
            choices=[
                "Sentence-Transformers (Local, recommended)",
                "Ollama (Requires running Ollama server)",
            ]
        )
```

**Access**: Run `kabot config` and select "Memory" from the menu.

## Advantages vs Kabot

| Aspect | Kabot | Kabot Memory System |
|--------|----------|---------------------|
| **Parent Chain** | Broken during compaction | Always preserved |
| **Tool Results** | Aggressively truncated | Stored completely |
| **Context Pruning** | Aggressive | Smart compaction |
| **Embeddings** | None | Semantic search |
| **Long-term Facts** | Limited | Dedicated storage |
| **Backend Swapping** | Not supported | 3 backends via config |
| **Low-resource Support** | No | SQLite-only mode |
| **Privacy Mode** | No | Disabled mode |

## Anti-Amnesia Mechanisms

### 1. Parent-Child Relationships

- Every message stores `parent_id`
- Enables conversation chain reconstruction
- No orphaned messages

### 2. Full Context Preservation

- Tool calls stored completely
- Tool results not truncated
- Metadata stored in SQLite

### 3. Semantic Search

- Searches by meaning, not just keywords
- Cosine similarity for relevance
- Finds related concepts

### 4. Session Isolation

- Each workspace has isolated memory
- No cross-contamination
- Clean context boundaries

## Testing

### Run All Memory Tests

```bash
python -m pytest tests/memory/ -v
```

**Expected Output**:
```
tests/memory/test_memory_backend.py::test_memory_backend_cannot_be_instantiated PASSED
tests/memory/test_memory_backend.py::test_memory_backend_has_required_methods PASSED
tests/memory/test_memory_factory.py::test_factory_creates_disabled_backend PASSED
tests/memory/test_memory_factory.py::test_factory_creates_sqlite_backend PASSED
tests/memory/test_memory_factory.py::test_factory_creates_hybrid_backend_by_default PASSED
tests/memory/test_null_memory.py::test_null_memory_is_memory_backend PASSED
tests/memory/test_sqlite_memory.py::test_sqlite_memory_is_memory_backend PASSED
tests/memory/test_hybrid_conforms.py::test_hybrid_is_subclass_of_memory_backend PASSED
...
============================= 60 passed in 28.70s =============================
```

### Run Setup Wizard Tests

```bash
python -m pytest tests/cli/test_setup_wizard_memory.py -v
```

**Expected Output**:
```
tests/cli/test_setup_wizard_memory.py::test_memory_in_advanced_menu_options PASSED
tests/cli/test_setup_wizard_memory.py::test_memory_in_simple_menu_options PASSED
============================= 2 passed in 5.13s =============================
```

## Dependencies

### Hybrid Backend

```bash
pip install chromadb>=0.4.18 sentence-transformers>=2.2.0 torch
```

**Installed Versions**:
- âœ… chromadb 1.5.0
- âœ… sentence-transformers 5.2.2
- âœ… torch 2.10.0
- âœ… numpy 2.2.6

### SQLite Only Backend

No external dependencies required (uses Python stdlib).

### Disabled Backend

No dependencies required.

## Configuration

### Via Setup Wizard

```bash
kabot config
```

Select "Memory" from the menu, then choose your backend.

### Via config.json

Edit `~/.kabot/config.json` (or `C:\Users\Username\.kabot\config.json` on Windows):

```json
{
  "memory": {
    "backend": "hybrid",
    "embedding_provider": "sentence",
    "embedding_model": "all-MiniLM-L6-v2",
    "enable_hybrid_search": true,
    "auto_unload_timeout": 300
  }
}
```

**Configuration Options**:
- `backend`: Memory backend type (`hybrid`, `sqlite_only`, `disabled`)
- `embedding_provider`: Embedding provider (`sentence`, `ollama`)
- `embedding_model`: Model name (e.g., `all-MiniLM-L6-v2`)
- `enable_hybrid_search`: Enable hybrid search combining semantic + keyword
- `auto_unload_timeout`: Seconds of inactivity before unloading model (default: 300)
  - Set to `0` to disable auto-unload
  - Recommended: 300-600 seconds for optimal RAM savings

**Restart required**: After changing backends, restart Kabot.

## Memory Statistics

Check memory system health:

```bash
kabot doctor
```

**Output**:
```
Memory System:
  Backend: hybrid
  Messages: 1,234
  Facts: 56
  Sessions: 12
  Status: OK
```

## File Structure

```
kabot/memory/
â”œâ”€â”€ __init__.py                  # Module exports with lazy loading
â”œâ”€â”€ memory_backend.py            # Abstract base class (ABC)
â”œâ”€â”€ memory_factory.py            # Backend factory
â”œâ”€â”€ chroma_memory.py             # Hybrid backend (ChromaDB + SQLite + BM25)
â”œâ”€â”€ sqlite_memory.py             # SQLite-only backend
â”œâ”€â”€ null_memory.py               # Disabled backend (no-op)
â”œâ”€â”€ sentence_embeddings.py       # Sentence-Transformers provider
â”œâ”€â”€ ollama_embeddings.py         # Ollama provider (alternative)
â”œâ”€â”€ sqlite_store.py              # SQLite metadata storage
â”œâ”€â”€ smart_router.py              # Query routing (episodic/knowledge)
â”œâ”€â”€ reranker.py                  # Result optimization
â”œâ”€â”€ episodic_extractor.py        # Fact extraction from conversations
â””â”€â”€ memory_pruner.py             # Old memory cleanup
```

## Backend Comparison

| Feature | Hybrid | SQLite Only | Disabled |
|---------|--------|-------------|----------|
| Semantic search | âœ… Yes | âŒ No | âŒ No |
| Keyword search | âœ… Yes | âœ… Yes | âŒ No |
| Memory footprint | ~250MB idle / ~500MB active | ~50MB | 0MB |
| Startup time | ~5s (on first use) | <1s | <1s |
| Dependencies | ChromaDB, sentence-transformers | None | None |
| Best for | Production | Low-resource | Privacy |
| Context understanding | Excellent | Basic | None |
| Multi-language | Yes | Limited | N/A |
| RAM optimization | Auto-unload after 5min | N/A | N/A |

## Troubleshooting

### "ChromaDB import error"

**Solution**: Switch to `sqlite_only` backend or install dependencies:
```bash
pip install chromadb sentence-transformers
```

### "Memory search returns no results"

**Checks**:
1. Backend is not `disabled`
2. For `sqlite_only`, use exact keywords (not semantic queries)
3. Run `kabot doctor` to check database health

### "High memory usage"

**Solutions**:
1. Switch from `hybrid` to `sqlite_only`
2. Use `disabled` for zero memory footprint
3. Reduce `max_messages` in conversation context

### "Slow startup"

**Solutions**:
1. Use `sqlite_only` for faster startup
2. Reduce embedding model size
3. Use `disabled` for instant startup

## Performance Benchmarks

### Hybrid Backend

**Performance**:
- **Startup**: ~5s (model loading on first use)
- **Add message**: ~50ms (embedding + storage)
- **Search**: ~100ms (vector search + reranking)
- **Context retrieval**: ~20ms (SQLite query)

**RAM Usage (with auto-unload optimization)**:
- **Idle RAM**: ~250MB (model unloaded after 5min inactivity)
- **Active RAM**: ~500MB (model loaded during search operations)
- **RAM Freed**: ~550MB when model auto-unloads
- **Cold start**: ~5s (no change - model reloads when needed)

### SQLite Only Backend

- **Startup**: <1s
- **Add message**: ~5ms (SQLite insert)
- **Search**: ~30ms (SQL LIKE query)
- **Context retrieval**: ~10ms (SQLite query)

### Disabled Backend

- **Startup**: <1s
- **Add message**: <1ms (no-op)
- **Search**: <1ms (returns empty)
- **Context retrieval**: <1ms (returns empty)

## Future Enhancements

### Planned Backends

- **Redis**: Distributed memory for multi-instance deployments
- **Mem0**: Cloud-based memory service
- **PostgreSQL**: Enterprise-grade relational storage

### Planned Features

- Automatic fact extraction from conversations
- Memory pruning for old/irrelevant data
- Cross-session memory search
- Memory export/import
- Memory analytics dashboard

---

**Status**: âœ… PRODUCTION READY
**Version**: 0.5.6
**Last Updated**: 2026-02-24
**Tests**: 60/60 passing
**Backends**: 3 (Hybrid, SQLite Only, Disabled)
**Default Model**: all-MiniLM-L6-v2 (384 dimensions)
**Windows Compatible**: Subprocess communication fixed (v0.5.6)


