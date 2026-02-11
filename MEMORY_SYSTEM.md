# Kabot Memory System - Anti Amnesia & Anti Halu

## Deskripsi
Memory system untuk Kabot yang mencegah masalah **amnesia** (lupa konteks) dan **halu** (tidak nyambung) seperti yang terjadi pada OpenClaw.

## Arsitektur

```
┌─────────────────┐
│   User Message  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  Sentence-Transformers  │  ← Pure Python, Gratis
│  (Embedding Model)      │     all-MiniLM-L6-v2
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│       ChromaDB          │  ← Vector Storage
│   (Semantic Search)     │     Cosine Similarity
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│        SQLite           │  ← Metadata & Relationships
│  (Parent-Child Chain)   │     Proper Message Trees
└─────────────────────────┘
```

## Komponen

### 1. Sentence Embedding Provider
- **File**: `kabot/memory/sentence_embeddings.py`
- **Fungsi**: Mengubah teks menjadi vektor (embedding)
- **Model**: `all-MiniLM-L6-v2` (384 dimensi, cepat & akurat)
- **Keunggulan**:
  - Pure Python (tidak perlu Ollama/AI API)
  - Gratis & lokal
  - Caching untuk performa

### 2. ChromaDB Memory Manager
- **File**: `kabot/memory/chroma_memory.py`
- **Fungsi**: Mengelola penyimpanan dan pencarian memori
- **Fitur**:
  - Semantic search (mencari berdasarkan makna)
  - Session management
  - Long-term facts storage
  - Health monitoring

### 3. SQLite Metadata Store
- **File**: `kabot/memory/sqlite_store.py`
- **Fungsi**: Menyimpan metadata dan relasi parent-child
- **Tables**:
  - `sessions`: Data sesi percakapan
  - `messages`: Pesan dengan parent_id (mencegah amnesia)
  - `facts`: Fakta jangka panjang
  - `memory_index`: Index ke ChromaDB

## Integrasi dengan Agent Loop

Agent loop (`kabot/agent/loop.py`) sekarang menggunakan memory system:

```python
# Inisialisasi
self.memory = ChromaMemoryManager(workspace / "memory_db")

# Simpan pesan user
await self.memory.add_message(
    session_id=msg.session_key,
    role="user",
    content=msg.content
)

# Ambil konteks percakapan (30 pesan terakhir)
conversation_history = self.memory.get_conversation_context(
    session_id=msg.session_key,
    max_messages=30
)

# Simpan hasil tool call (mencegah amnesia!)
await self.memory.add_message(
    session_id=msg.session_key,
    role="tool",
    content=str(result),
    tool_results=[...]
)
```

## Keunggulan vs OpenClaw

| Aspek | OpenClaw | Kabot Memory System |
|-------|----------|---------------------|
| **Parent Chain** | Terputus saat compaction | Selalu terjaga |
| **Tool Results** | Ditruncate agresif | Disimpan lengkap |
| **Context Pruning** | Aggressive | Smart compaction |
| **Embeddings** | Tidak ada | Semantic search |
| **Long-term Facts** | Terbatas | Dedicated storage |

## Cara Kerja Anti-Amnesia

1. **Parent-Child Relationships**
   - Setiap pesan menyimpan `parent_id`
   - Memungkinkan rekonstruksi rantai percakapan
   - Tidak ada pesan yang "orphan"

2. **Full Context Preservation**
   - Tool calls disimpan lengkap
   - Tool results tidak dipotong (truncated)
   - Metadata disimpan di SQLite

3. **Semantic Search**
   - Mencari memori berdasarkan makna
   - Cosine similarity untuk relevansi
   - Tidak hanya keyword matching

## Testing

```bash
# Run test
python test_memory.py
```

Output yang diharapkan:
```
[OK] Memory manager initialized
[Health Check]:
   - SQLite: OK
   - Model: all-MiniLM-L6-v2
   - Dimensions: 384
[OK] Session created: test_session_001
[Adding messages...]
   [OK] user: Halo, nama saya Budi...
   [OK] assistant: Halo Budi! Senang bertemu denganmu...
...
[SUCCESS] Memory system test completed successfully!
```

## Dependencies

```bash
pip install chromadb>=0.4.18 sentence-transformers>=2.2.0
```

Sudah terinstall:
- ✅ chromadb 1.5.0
- ✅ sentence-transformers 5.2.2
- ✅ torch 2.10.0
- ✅ numpy 2.2.6

## Penggunaan

Memory system otomatis aktif saat gateway di-restart. Tidak perlu konfigurasi tambahan.

### Features:
- ✅ Simpan semua pesan user & assistant
- ✅ Simpan tool calls & results lengkap
- ✅ Semantic search untuk konteks relevan
- ✅ Long-term fact storage
- ✅ Session-based memory isolation

## File Structure

```
kabot/memory/
├── __init__.py              # Module exports
├── chroma_memory.py         # Main memory manager
├── sentence_embeddings.py   # Sentence-Transformers provider
├── ollama_embeddings.py     # Ollama provider (alternative)
└── sqlite_store.py          # SQLite metadata storage
```

## Next Steps

1. Restart gateway untuk mengaktifkan memory system
2. Test dengan percakapan panjang (>20 pesan)
3. Verifikasi tidak ada "amnesia" atau "halu"

---

**Status**: ✅ IMPLEMENTED & TESTED
**Tanggal**: 2026-02-10
**Model**: all-MiniLM-L6-v2 (384 dimensi)
