"""ChromaDB-based memory manager with Ollama embeddings and SQLite metadata."""

import hashlib
import math
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger


from .ollama_embeddings import OllamaEmbeddingProvider
from .reranker import Reranker
from .sentence_embeddings import SentenceEmbeddingProvider
from .smart_router import SmartRouter
from .sqlite_store import SQLiteMetadataStore


class HybridMemoryManager:
    """
    Hybrid memory system combining:
    - ChromaDB: Vector storage for semantic search
    - Ollama: Local embeddings (no API cost)
    - SQLite: Metadata and parent-child relationships

    Prevents OpenClaw's amnesia issues by:
    1. Maintaining proper parent-child message chains
    2. Never truncating tool results aggressively
    3. Preserving full conversation context
    4. Using vector similarity for accurate memory retrieval
    """

    def __init__(self, workspace: Path, embedding_provider: str = "sentence",
                 embedding_model: str | None = None, enable_hybrid_memory: bool = True):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.enable_hybrid_memory = enable_hybrid_memory

        self.router = SmartRouter()
        self.reranker = Reranker(threshold=0.6, top_k=3, max_tokens=500)

        # Initialize embedding provider (sentence-transformers or ollama)
        if embedding_provider == "sentence":
            model = embedding_model or "all-MiniLM-L6-v2"
            self.embeddings = SentenceEmbeddingProvider(model)
            logger.info(f"Using Sentence-Transformers with model: {model}")
        elif embedding_provider == "ollama":
            model = embedding_model or "nomic-embed-text"
            self.embeddings = OllamaEmbeddingProvider("http://localhost:11434", model)
            logger.info(f"Using Ollama with model: {model}")
        else:
            raise ValueError(f"Unknown embedding provider: {embedding_provider}")

        db_path = self.workspace / "metadata.db"
        self.metadata = SQLiteMetadataStore(db_path)

        # Initialize BM25 index components lazily
        self.bm25 = None
        self.bm25_documents = []
        self.bm25_ids = []  # List of (type, id) tuples
        self._bm25_built = False

        if not self.enable_hybrid_memory:
            logger.info("Hybrid memory (BM25) disabled via config")
        else:
            logger.debug("BM25 index will be built lazily on first search")

        # ChromaDB will be initialized lazily
        self._chroma_client = None
        self._collection = None
        import threading
        self._lock = threading.Lock()

    async def warmup(self):
        """Pre-load embedding model and ChromaDB in background (non-blocking)."""
        try:
            if isinstance(self.embeddings, SentenceEmbeddingProvider):
                await self.embeddings.warmup()
            self._init_chroma()
            logger.info("Memory warmup completed")
        except Exception as e:
            logger.warning(f"Memory warmup failed (will lazy-load later): {e}")

    def _init_chroma(self):
        """Initialize ChromaDB connection lazily."""
        if self._chroma_client is not None:
            return

        with self._lock:
            # Double-check inside lock
            if self._chroma_client is not None:
                return

            try:
                import chromadb
                from chromadb.config import Settings

                chroma_dir = self.workspace / "chroma"
                chroma_dir.mkdir(parents=True, exist_ok=True)

                self._chroma_client = chromadb.PersistentClient(
                    path=str(chroma_dir),
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )

                # Get or create collection
                self._collection = self._chroma_client.get_or_create_collection(
                    name="kabot_memory",
                    metadata={"hnsw:space": "cosine"}
                )

                logger.info("ChromaDB initialized successfully")

            except ImportError:
                logger.error("ChromaDB not installed. Run: pip install chromadb")
                raise
            except Exception as e:
                logger.error(f"Error initializing ChromaDB: {e}")
                raise

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenizer for BM25."""
        return re.findall(r'\w+', text.lower())

    def _build_bm25_index(self):
        """Build BM25 index from all messages and facts in SQLite."""
        try:
            documents = []
            doc_ids = []

            # Connect directly to SQLite to fetch all text
            with sqlite3.connect(self.metadata.db_path) as conn:
                # 1. Fetch messages
                cursor = conn.execute("SELECT message_id, content FROM messages")
                for row in cursor:
                    message_id, content = row
                    documents.append(content)
                    doc_ids.append(('message', message_id))

                # 2. Fetch facts
                cursor = conn.execute("SELECT fact_id, value, category FROM facts")
                for row in cursor:
                    fact_id, value, category = row
                    # Add category to content for better matching
                    content = f"[{category}] {value}"
                    documents.append(content)
                    doc_ids.append(('fact', fact_id))

            if not documents:
                self.bm25 = None
                self.bm25_documents = []
                self.bm25_ids = []
                self._bm25_built = True # Mark as built, even if empty
                return

            # Tokenize and build index
            tokenized_corpus = [self._tokenize(doc) for doc in documents]
            from rank_bm25 import BM25Okapi
            self.bm25 = BM25Okapi(tokenized_corpus)
            self.bm25_documents = documents
            self.bm25_ids = doc_ids
            self._bm25_built = True

            logger.info(f"Built BM25 index with {len(documents)} documents")

        except Exception as e:
            logger.error(f"Error building BM25 index: {e}")

    async def add_message(self, session_id: str, role: str, content: str,
                         parent_id: str | None = None,
                         tool_calls: list | None = None,
                         tool_results: list | None = None,
                         metadata: dict | None = None) -> bool:
        """
        Add a message to memory with full context preservation.

        This maintains proper conversation chains to prevent amnesia.
        """
        try:
            message_id = str(uuid.uuid4())

            # 1. Store in SQLite with parent relationship
            success = self.metadata.add_message(
                message_id=message_id,
                session_id=session_id,
                role=role,
                content=content,
                parent_id=parent_id,
                tool_calls=tool_calls,
                tool_results=tool_results,
                metadata=metadata
            )

            if not success:
                return False

            # 2. Generate embedding and store in ChromaDB
            await self._index_message(session_id, message_id, content, metadata)

            # 3. Invalidate BM25 index to force rebuild on next search
            if self.enable_hybrid_memory:
                self._bm25_built = False

            return True

        except Exception as e:
            logger.error(f"Error adding message: {e}")
            return False

    async def _index_message(self, session_id: str, message_id: str,
                            content: str, metadata: dict | None = None):
        """Index message in ChromaDB for semantic search."""
        try:
            # Generate embedding
            embedding = await self.embeddings.embed(content)

            if embedding:
                self._init_chroma()

                content_hash = hashlib.md5(content.encode()).hexdigest()
                chroma_id = f"{session_id}_{message_id}"

                # Store in ChromaDB
                self._collection.add(
                    ids=[chroma_id],
                    embeddings=[embedding],
                    documents=[content],
                    metadatas=[{
                        "session_id": session_id,
                        "message_id": message_id,
                        "content_hash": content_hash,
                        "timestamp": datetime.now().isoformat()
                    }]
                )

                # Save index reference in SQLite
                self.metadata.save_memory_index(
                    session_id, message_id, chroma_id, content_hash
                )

        except Exception as e:
            logger.error(f"Error indexing message: {e}")


    def _perform_bm25_search(self, query: str, limit: int = 5) -> list[dict]:
        """Perform keyword search using BM25."""
        if not self.bm25:
            return []

        try:
            tokenized_query = self._tokenize(query)
            scores = self.bm25.get_scores(tokenized_query)

            # Get top N indices
            top_n = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:limit]

            results = []
            for i in top_n:
                if scores[i] <= 0:
                    continue

                doc_type, doc_id = self.bm25_ids[i]

                if doc_type == 'message':
                    item = self._get_message_by_id(doc_id)
                else:
                    item = self._get_fact_by_id(doc_id)

                if item:
                    item['bm25_score'] = scores[i]
                    results.append(item)

            return results
        except Exception as e:
            logger.error(f"Error in BM25 search: {e}")
            return []

    @staticmethod
    def _temporal_decay_multiplier(
        age_hours: float,
        half_life_hours: float = 24.0 * 7.0,
        floor: float = 0.65,
    ) -> float:
        """Compute a bounded temporal decay factor.

        Newer memories get multiplier near 1.0 while very old memories decay
        toward `floor` (never fully zeroed out).
        """
        if age_hours <= 0:
            return 1.0
        decay = math.exp(-math.log(2.0) * (age_hours / max(1.0, half_life_hours)))
        return floor + ((1.0 - floor) * decay)

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _normalize_scores(values: list[float]) -> list[float]:
        """Normalize values to 0..1 while handling degenerate ranges."""
        if not values:
            return []
        lo = min(values)
        hi = max(values)
        if abs(hi - lo) < 1e-12:
            return [1.0 for _ in values]
        return [(v - lo) / (hi - lo) for v in values]

    def _extract_item_datetime(self, item: dict) -> datetime | None:
        """Extract best-effort timestamp from memory item."""
        raw_candidates = [
            item.get("updated_at"),
            item.get("created_at"),
            (item.get("metadata") or {}).get("timestamp") if isinstance(item.get("metadata"), dict) else None,
        ]

        for raw in raw_candidates:
            if raw is None:
                continue
            if isinstance(raw, (int, float)):
                try:
                    ts = raw / 1000 if raw > 10_000_000_000 else raw
                    return datetime.fromtimestamp(ts)
                except Exception:
                    continue
            if isinstance(raw, str):
                text = raw.strip()
                if not text:
                    continue
                normalized = text.replace("Z", "+00:00")
                try:
                    dt = datetime.fromisoformat(normalized)
                except ValueError:
                    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                        try:
                            dt = datetime.strptime(text, fmt)
                            break
                        except ValueError:
                            dt = None
                    if dt is None:
                        continue
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                return dt
        return None

    def _apply_temporal_decay_to_candidates(self, candidates: list[dict]) -> list[dict]:
        """Apply temporal decay to fused candidates and resort by adjusted score."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        adjusted: list[dict] = []
        for candidate in candidates:
            item = candidate.get("item", {})
            base_score = float(candidate.get("score", 0.0))
            item_dt = self._extract_item_datetime(item) if isinstance(item, dict) else None
            age_hours = 0.0
            if item_dt:
                age_hours = max(0.0, (now - item_dt).total_seconds() / 3600.0)
            temporal_mult = self._temporal_decay_multiplier(age_hours)
            adjusted.append({
                **candidate,
                "score": base_score * temporal_mult,
                "temporal_multiplier": temporal_mult,
            })
        adjusted.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return adjusted

    async def _prepare_mmr_candidates(self, candidates: list[dict]) -> list[dict]:
        """Attach embeddings for MMR reranking with lightweight content cache."""
        cache: dict[str, list[float] | None] = {}
        prepared: list[dict] = []
        for candidate in candidates:
            item = candidate.get("item", {})
            content = item.get("content", "") if isinstance(item, dict) else ""
            embedding: list[float] | None = None
            if isinstance(content, str) and content.strip():
                if content in cache:
                    embedding = cache[content]
                else:
                    try:
                        embedding = await self.embeddings.embed(content)
                    except Exception:
                        embedding = None
                    cache[content] = embedding
            prepared.append({**candidate, "embedding": embedding})
        return prepared

    def _mmr_select_candidates(
        self,
        candidates: list[dict],
        query_embedding: list[float],
        limit: int,
        lambda_mult: float = 0.75,
    ) -> list[dict]:
        """Select diverse-yet-relevant candidates using MMR."""
        if limit <= 0 or not candidates:
            return []
        if len(candidates) <= 1:
            return candidates[:limit]

        score_values = [float(c.get("score", 0.0)) for c in candidates]
        norm_scores = self._normalize_scores(score_values)

        query_sims: list[float] = []
        for candidate in candidates:
            emb = candidate.get("embedding")
            if isinstance(emb, list) and emb:
                query_sims.append(self._cosine_similarity(query_embedding, emb))
            else:
                query_sims.append(0.0)
        norm_query = self._normalize_scores(query_sims)

        for idx, candidate in enumerate(candidates):
            candidate["_mmr_relevance"] = (0.5 * norm_scores[idx]) + (0.5 * norm_query[idx])

        selected: list[dict] = []
        remaining = list(range(len(candidates)))
        while remaining and len(selected) < limit:
            if not selected:
                pick_idx = max(remaining, key=lambda i: candidates[i]["_mmr_relevance"])
            else:
                def _mmr_value(i: int) -> float:
                    relevance = candidates[i]["_mmr_relevance"]
                    emb_i = candidates[i].get("embedding")
                    max_sim = 0.0
                    if isinstance(emb_i, list) and emb_i:
                        for chosen in selected:
                            emb_j = chosen.get("embedding")
                            if isinstance(emb_j, list) and emb_j:
                                max_sim = max(max_sim, self._cosine_similarity(emb_i, emb_j))
                    return (lambda_mult * relevance) - ((1.0 - lambda_mult) * max_sim)

                pick_idx = max(remaining, key=_mmr_value)

            selected.append(candidates[pick_idx])
            remaining.remove(pick_idx)

        return selected[:limit]

    async def search_memory(self, query: str, session_id: str | None = None,
                           limit: int = 5) -> list[dict]:
        """
        Search memory using Hybrid Search (Vector + BM25) with RRF Fusion.

        Args:
            query: Search query
            session_id: Optional session filter
            limit: Maximum results

        Returns:
            List of relevant messages with fused scores
        """
        try:
            # 0. Route query intent
            route = self.router.route(query)
            logger.debug(f"Search memory route: {route} for query '{query}'")

            # 1. Run Vector Search
            vector_results = []
            # Generate query embedding
            query_embedding = await self.embeddings.embed(query)

            if query_embedding:
                self._init_chroma()
                # Prepare filter
                where_filter = {"session_id": session_id} if session_id else None

                # Search ChromaDB
                results = self._collection.query(
                    query_embeddings=[query_embedding],
                    n_results=limit,
                    where=where_filter,
                    include=["documents", "metadatas", "distances"]
                )

                # Format results
                if results["ids"] and len(results["ids"][0]) > 0:
                    for i, chroma_id in enumerate(results["ids"][0]):
                        metadata = results["metadatas"][0][i]
                        document = results["documents"][0][i]
                        distance = results["distances"][0][i]

                        # Get full message from SQLite
                        message_id = metadata.get("message_id")
                        msg_data = self._get_message_by_id(message_id)

                        item = None
                        if msg_data:
                            item = msg_data
                        else:
                            # If not found in messages table, check facts table
                            fact_data = self._get_fact_by_id(message_id)
                            if fact_data:
                                item = fact_data
                            elif document:
                                # Fallback: use ChromaDB document directly
                                item = {
                                    "content": document,
                                    "metadata": metadata,
                                    "message_id": message_id # Ensure ID exists
                                }

                        if item:
                            item["similarity_score"] = 1.0 - distance
                            vector_results.append(item)

            # 2. Run BM25 Search
            bm25_results = []
            if self.enable_hybrid_memory:
                if route == "episodic":
                    # Explicit intention to hit episodic DB
                    logger.debug("Executing episodic-only search (BM25 exact match)")

                    if not self._bm25_built:
                        self._build_bm25_index()

                    if self.bm25 and self.bm25_documents:
                        bm25_results = self._perform_bm25_search(query, limit=limit)
                elif route == "hybrid":
                    logger.debug("Executing hybrid search (Semantic + BM25)")

                    # Lazy BM25 building
                    if not self._bm25_built:
                        self._build_bm25_index()

                    # Execute BM25 search
                    if self.bm25 and self.bm25_documents:
                        bm25_results = self._perform_bm25_search(query, limit=limit)
                elif route != "knowledge": # For other routes, if hybrid is enabled, do BM25
                    if not self._bm25_built:
                        self._build_bm25_index()
                    if self.bm25 and self.bm25_documents:
                        bm25_results = self._perform_bm25_search(query, limit=limit)


            # Filter BM25 results by session_id if needed
            if session_id:
                bm25_results = [r for r in bm25_results if r.get('session_id') == session_id]

            # 3. Apply Reciprocal Rank Fusion (RRF)
            k = 60
            fused_scores = {}

            # Process Vector Results
            for rank, item in enumerate(vector_results):
                # Use message_id or fact_id as unique key
                item_id = item.get('message_id') or item.get('fact_id')
                if not item_id:
                    continue

                if item_id not in fused_scores:
                    fused_scores[item_id] = {'item': item, 'score': 0.0}

                fused_scores[item_id]['score'] += 1.0 / (k + rank + 1)
                fused_scores[item_id]['item']['vector_rank'] = rank + 1

            # Process BM25 Results
            if self.enable_hybrid_memory:
                for rank, item in enumerate(bm25_results):
                    item_id = item.get('message_id') or item.get('fact_id')
                    if not item_id:
                        continue

                    if item_id not in fused_scores:
                        fused_scores[item_id] = {'item': item, 'score': 0.0}

                    # If item was already in vector results, this updates the score
                    # Note: We merge fields if needed, but here we assume items are similar enough
                    # or we just keep the one we have (usually the first one encountered is fine,
                    # but merging metadata might be better if they differ).
                    # Since both fetch from SQLite, they should be identical.

                    fused_scores[item_id]['score'] += 1.0 / (k + rank + 1)
                    fused_scores[item_id]['item']['bm25_rank'] = rank + 1

                    # Ensure BM25 score is preserved if it wasn't there
                    if 'bm25_score' in item:
                        fused_scores[item_id]['item']['bm25_score'] = item['bm25_score']

            # Sort by fused score, then apply temporal decay weighting.
            final_results = sorted(fused_scores.values(), key=lambda x: x['score'], reverse=True)
            ranked = self._apply_temporal_decay_to_candidates(final_results)

            # Optional MMR reranking for diversity (top candidate pool only).
            if query_embedding and len(ranked) > 1 and limit > 1:
                candidate_pool_size = max(limit * 4, limit)
                candidate_pool = ranked[:candidate_pool_size]
                mmr_candidates = await self._prepare_mmr_candidates(candidate_pool)
                selected = self._mmr_select_candidates(
                    candidates=mmr_candidates,
                    query_embedding=query_embedding,
                    limit=limit,
                )
                return self.reranker.rank(query, [x['item'] for x in selected])

            return self.reranker.rank(query, [x['item'] for x in ranked[:limit]])

        except Exception as e:
            logger.error(f"Error searching memory: {e}")
            return []

    def _get_message_by_id(self, message_id: str) -> dict | None:
        """Get message data from SQLite by ID."""
        try:
            messages = self.metadata.get_message_tree(message_id)
            if messages:
                return messages[-1]
            return None
        except Exception:
            return None

    def _get_fact_by_id(self, fact_id: str) -> dict | None:
        """Get fact data from SQLite by ID."""
        try:
            fact = self.metadata.get_fact(fact_id)
            if fact:
                # Add role='system' to make it look like a message
                fact["role"] = "system"
                fact["content"] = f"[{fact['category']}] {fact['value']}"
                return fact
            return None
        except Exception:
            return None

    def get_conversation_context(self, session_id: str,
                                 max_messages: int = 20) -> list[dict]:
        """
        Get recent conversation context with full message chains.

        Unlike OpenClaw's aggressive pruning, this preserves:
        - Full tool call details
        - Complete tool results
        - Proper parent-child relationships
        """
        try:
            messages = self.metadata.get_message_chain(
                session_id, limit=max_messages
            )

            # Format for LLM consumption
            context = []
            for msg in messages:
                formatted = {
                    "role": msg["role"],
                    "content": msg["content"],
                }

                # Include tool calls if present
                if msg.get("tool_calls"):
                    formatted["tool_calls"] = msg["tool_calls"]

                if msg.get("tool_results"):
                    formatted["tool_results"] = msg["tool_results"]

                context.append(formatted)

            return context

        except Exception as e:
            logger.error(f"Error getting conversation context: {e}")
            return []

    async def remember_fact(self, fact: str, category: str = "general",
                           session_id: str | None = None,
                           confidence: float = 1.0) -> bool:
        """
        Store a long-term fact/memory.

        Args:
            fact: The fact to remember
            category: Category (e.g., "user_preference", "project_info")
            session_id: Optional session association
            confidence: Confidence level (0.0-1.0)
        """
        try:
            fact_id = str(uuid.uuid4())

            # Store in SQLite
            success = self.metadata.add_fact(
                fact_id=fact_id,
                category=category,
                key=fact[:50],  # First 50 chars as key
                value=fact,
                session_id=session_id,
                confidence=confidence
            )

            if success:
                # Also index in ChromaDB for semantic search
                await self._index_message(
                    session_id or "global",
                    fact_id,
                    f"[{category}] {fact}",
                    {"type": "fact", "category": category}
                )

                # Update BM25 index
                if self.enable_hybrid_memory:
                    self._build_bm25_index()

            return success

        except Exception as e:
            logger.error(f"Error remembering fact: {e}")
            return False

    def get_relevant_facts(self, category: str | None = None,
                          session_id: str | None = None) -> list[str]:
        """Get relevant facts from long-term memory."""
        try:
            facts = self.metadata.get_facts(
                session_id=session_id,
                category=category
            )

            return [f["value"] for f in facts]

        except Exception as e:
            logger.error(f"Error getting facts: {e}")
            return []

    def create_session(self, session_id: str, channel: str, chat_id: str,
                      user_id: str | None = None) -> bool:
        """Create a new conversation session."""
        return self.metadata.create_session(
            session_id, channel, chat_id, user_id
        )

    async def compact_session(self, session_id: str) -> bool:
        """
        Compact old messages while preserving important context.

        Unlike OpenClaw's aggressive compaction, this:
        1. Keeps recent N messages intact
        2. Summarizes older messages into key facts
        3. Maintains tool result references
        """
        try:
            messages = self.metadata.get_message_chain(session_id, limit=1000)

            if len(messages) <= 50:
                return True  # No need to compact

            # Keep last 30 messages intact
            recent = messages[-30:]
            older = messages[:-30]

            # Extract key facts from older messages
            # (In production, you might use LLM to summarize)
            key_facts = []
            for msg in older:
                if msg["role"] == "assistant" and len(msg["content"]) > 100:
                    key_facts.append(msg["content"][:200])

            # Store key facts
            if key_facts:
                summary = " | ".join(key_facts[:5])  # Top 5 key points
                await self.remember_fact(
                    f"Earlier conversation summary: {summary}",
                    category="conversation_summary",
                    session_id=session_id
                )

            logger.info(f"Compacted session {session_id}: {len(messages)} -> {len(recent)} messages")
            return True

        except Exception as e:
            logger.error(f"Error compacting session: {e}")
            return False

    def get_stats(self) -> dict:
        """Get memory system statistics."""
        stats = self.metadata.get_stats()

        if self._chroma_client:
            try:
                chroma_count = self._collection.count()
                stats["chroma_documents"] = chroma_count
            except Exception:
                stats["chroma_documents"] = 0

        return stats

    def health_check(self) -> dict:
        """Check memory system health."""
        provider_info = {
            "sqlite_connected": self.metadata is not None,
            "chroma_initialized": self._chroma_client is not None,
            "embedding_available": self.embeddings.check_connection(),
            "embedding_model": getattr(self.embeddings, 'model_name', getattr(self.embeddings, 'model', 'unknown')),
            "embedding_dimensions": self.embeddings.dimensions
        }

        # Add provider-specific info
        if hasattr(self.embeddings, 'get_model_info'):
            provider_info.update(self.embeddings.get_model_info())

        return provider_info

    # ── Lessons (Metacognition) ─────────────────────────────────

    async def save_lesson(self, trigger: str, mistake: str, fix: str,
                          guardrail: str, score_before: int | None = None,
                          score_after: int | None = None,
                          task_type: str | None = None) -> bool:
        """Save a metacognition lesson to SQLite."""
        import uuid
        lesson_id = str(uuid.uuid4())[:12]
        return self.metadata.add_lesson(
            lesson_id=lesson_id,
            trigger=trigger,
            mistake=mistake,
            fix=fix,
            guardrail=guardrail,
            score_before=score_before,
            score_after=score_after,
            task_type=task_type,
        )

    def get_recent_lessons(self, limit: int = 10,
                           task_type: str | None = None) -> list[dict]:
        """Get recent lessons from SQLite."""
        return self.metadata.get_recent_lessons(limit=limit, task_type=task_type)

    def get_guardrails(self, limit: int = 5) -> list[str]:
        """Get distilled guardrail strings for prompt injection."""
        return self.metadata.get_guardrails(limit=limit)

# Backward compatibility alias
ChromaMemoryManager = HybridMemoryManager
