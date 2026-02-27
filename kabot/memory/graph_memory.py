"""Native graph-memory store (entity-relation memory) for Kabot."""
from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GraphMemory:
    """Lightweight relational memory using SQLite."""

    _RELATION_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
        (re.compile(r"\b(?P<src>[\w./:-]{2,64})\s+(?:uses?|pakai|menggunakan)\s+(?P<dst>[\w./:-]{2,96})\b", re.IGNORECASE), "uses", 0.9),
        (re.compile(r"\b(?P<src>[\w./:-]{2,64})\s+(?:depends on|needs?|butuh)\s+(?P<dst>[\w./:-]{2,96})\b", re.IGNORECASE), "depends_on", 0.85),
        (re.compile(r"\b(?P<src>[\w./:-]{2,64})\s+(?:integrates? with|connects? to|terhubung ke)\s+(?P<dst>[\w./:-]{2,96})\b", re.IGNORECASE), "integrates_with", 0.85),
        (re.compile(r"\b(?:i|aku|saya)\s+(?:prefer|like|suka|lebih suka)\s+(?P<dst>[^.,;]{2,80})", re.IGNORECASE), "prefers", 0.8),
    ]

    def __init__(self, db_path: Path, enabled: bool = True) -> None:
        self.db_path = Path(db_path)
        self.enabled = bool(enabled)
        if not self.enabled:
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    entity_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    name_key TEXT NOT NULL UNIQUE,
                    entity_type TEXT DEFAULT 'unknown',
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    mentions INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS relations (
                    relation_id TEXT PRIMARY KEY,
                    src_entity_id TEXT NOT NULL,
                    dst_entity_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    session_id TEXT,
                    role TEXT,
                    evidence TEXT,
                    confidence REAL NOT NULL DEFAULT 0.7,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    mentions INTEGER NOT NULL DEFAULT 1
                );

                CREATE INDEX IF NOT EXISTS idx_rel_src ON relations(src_entity_id);
                CREATE INDEX IF NOT EXISTS idx_rel_dst ON relations(dst_entity_id);
                CREATE INDEX IF NOT EXISTS idx_rel_session ON relations(session_id);
                """
            )

    @staticmethod
    def _normalize_entity(raw: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(raw or "").strip())
        cleaned = cleaned.strip("`'\".,;:()[]{}")
        return cleaned

    @staticmethod
    def _entity_key(name: str) -> str:
        return re.sub(r"\s+", " ", name.lower().strip())

    def _ensure_entity(self, conn: sqlite3.Connection, name: str, entity_type: str = "unknown") -> str:
        normalized = self._normalize_entity(name)
        if not normalized:
            return ""
        key = self._entity_key(normalized)
        now = _now_iso()
        row = conn.execute(
            "SELECT entity_id, mentions FROM entities WHERE name_key = ?",
            (key,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE entities SET last_seen = ?, mentions = ? WHERE entity_id = ?",
                (now, int(row["mentions"]) + 1, row["entity_id"]),
            )
            return str(row["entity_id"])

        entity_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO entities (entity_id, name, name_key, entity_type, first_seen, last_seen, mentions)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (entity_id, normalized, key, entity_type, now, now),
        )
        return entity_id

    def _upsert_relation(
        self,
        conn: sqlite3.Connection,
        src_entity_id: str,
        dst_entity_id: str,
        relation: str,
        session_id: str | None,
        role: str | None,
        evidence: str,
        confidence: float,
    ) -> None:
        now = _now_iso()
        row = conn.execute(
            """
            SELECT relation_id, mentions, confidence
            FROM relations
            WHERE src_entity_id = ? AND dst_entity_id = ? AND relation = ?
              AND COALESCE(session_id, '') = COALESCE(?, '')
            """,
            (src_entity_id, dst_entity_id, relation, session_id),
        ).fetchone()
        if row:
            conn.execute(
                """
                UPDATE relations
                SET last_seen = ?, mentions = ?, confidence = ?, evidence = ?
                WHERE relation_id = ?
                """,
                (
                    now,
                    int(row["mentions"]) + 1,
                    max(float(row["confidence"]), float(confidence)),
                    evidence[:400],
                    row["relation_id"],
                ),
            )
            return

        conn.execute(
            """
            INSERT INTO relations
            (relation_id, src_entity_id, dst_entity_id, relation, session_id, role, evidence, confidence, first_seen, last_seen, mentions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                str(uuid.uuid4()),
                src_entity_id,
                dst_entity_id,
                relation,
                session_id,
                role,
                evidence[:400],
                float(confidence),
                now,
                now,
            ),
        )

    def _extract_relations(self, content: str) -> list[tuple[str, str, str, float]]:
        text = str(content or "").strip()
        if len(text) < 4:
            return []

        relations: list[tuple[str, str, str, float]] = []
        for pattern, relation, confidence in self._RELATION_PATTERNS:
            for match in pattern.finditer(text):
                src = self._normalize_entity(match.groupdict().get("src", "") or "user")
                dst = self._normalize_entity(match.groupdict().get("dst", ""))
                if not dst:
                    continue
                if not src:
                    src = "user"
                if src.lower() == dst.lower():
                    continue
                relations.append((src, dst, relation, confidence))

        # Soft fallback: code/backtick tokens imply contextual relation
        code_tokens = [self._normalize_entity(tok) for tok in re.findall(r"`([^`]{2,64})`", text)]
        code_tokens = [tok for tok in code_tokens if tok]
        if len(code_tokens) >= 2:
            for idx in range(len(code_tokens) - 1):
                a = code_tokens[idx]
                b = code_tokens[idx + 1]
                if a.lower() != b.lower():
                    relations.append((a, b, "related_to", 0.55))
        return relations

    def ingest_text(
        self,
        *,
        session_id: str | None,
        role: str | None,
        content: str,
        category: str | None = None,
    ) -> dict[str, int]:
        """Extract and persist graph relations from text."""
        if not self.enabled:
            return {"entities": 0, "relations": 0}

        extracted = self._extract_relations(content)
        if category and category.lower() in {"preference", "fact"}:
            candidate = self._normalize_entity(content)
            if candidate and len(candidate) <= 80:
                extracted.append(("user", candidate, "states", 0.6))

        if not extracted:
            return {"entities": 0, "relations": 0}

        entity_ids: set[str] = set()
        relation_count = 0
        try:
            with self._conn() as conn:
                for src, dst, relation, confidence in extracted:
                    src_id = self._ensure_entity(conn, src)
                    dst_id = self._ensure_entity(conn, dst)
                    if not src_id or not dst_id:
                        continue
                    entity_ids.add(src_id)
                    entity_ids.add(dst_id)
                    self._upsert_relation(
                        conn,
                        src_entity_id=src_id,
                        dst_entity_id=dst_id,
                        relation=relation,
                        session_id=session_id,
                        role=role,
                        evidence=content,
                        confidence=confidence,
                    )
                    relation_count += 1
            return {"entities": len(entity_ids), "relations": relation_count}
        except Exception as exc:
            logger.warning(f"GraphMemory ingest failed: {exc}")
            return {"entities": 0, "relations": 0}

    def query_related(self, entity: str, limit: int = 10) -> list[dict[str, Any]]:
        """Query outgoing/incoming relations for a named entity."""
        if not self.enabled:
            return []
        key = self._entity_key(entity)
        if not key:
            return []
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT entity_id, name FROM entities WHERE name_key = ?",
                    (key,),
                ).fetchone()
                if not row:
                    # Soft contains match fallback
                    row = conn.execute(
                        """
                        SELECT entity_id, name
                        FROM entities
                        WHERE name_key LIKE ?
                        ORDER BY mentions DESC, last_seen DESC
                        LIMIT 1
                        """,
                        (f"%{key}%",),
                    ).fetchone()
                if not row:
                    return []

                entity_id = str(row["entity_id"])
                rows = conn.execute(
                    """
                    SELECT
                        r.relation,
                        s.name AS src_name,
                        d.name AS dst_name,
                        r.session_id,
                        r.role,
                        r.confidence,
                        r.mentions,
                        r.last_seen
                    FROM relations r
                    JOIN entities s ON s.entity_id = r.src_entity_id
                    JOIN entities d ON d.entity_id = r.dst_entity_id
                    WHERE r.src_entity_id = ? OR r.dst_entity_id = ?
                    ORDER BY r.mentions DESC, r.last_seen DESC
                    LIMIT ?
                    """,
                    (entity_id, entity_id, max(1, int(limit))),
                ).fetchall()
                return [dict(item) for item in rows]
        except Exception as exc:
            logger.warning(f"GraphMemory query failed: {exc}")
            return []

    def summarize(self, query: str | None = None, limit: int = 8) -> str:
        """Render compact graph summary for prompt injection."""
        rows: list[dict[str, Any]]
        if query:
            rows = self.query_related(query, limit=limit)
        else:
            if not self.enabled:
                return ""
            try:
                with self._conn() as conn:
                    fetched = conn.execute(
                        """
                        SELECT
                            r.relation,
                            s.name AS src_name,
                            d.name AS dst_name,
                            r.mentions,
                            r.last_seen
                        FROM relations r
                        JOIN entities s ON s.entity_id = r.src_entity_id
                        JOIN entities d ON d.entity_id = r.dst_entity_id
                        ORDER BY r.mentions DESC, r.last_seen DESC
                        LIMIT ?
                        """,
                        (max(1, int(limit)),),
                    ).fetchall()
                rows = [dict(item) for item in fetched]
            except Exception as exc:
                logger.warning(f"GraphMemory summarize failed: {exc}")
                return ""

        if not rows:
            return ""

        lines = []
        for row in rows[: max(1, int(limit))]:
            src = str(row.get("src_name", "")).strip()
            rel = str(row.get("relation", "")).strip()
            dst = str(row.get("dst_name", "")).strip()
            mentions = int(row.get("mentions", 1) or 1)
            if not src or not rel or not dst:
                continue
            lines.append(f"- {src} {rel} {dst} (mentions={mentions})")
        if not lines:
            return ""
        return "\n".join(lines)

    def get_stats(self) -> dict[str, Any]:
        """Return graph-memory stats."""
        if not self.enabled:
            return {"enabled": False, "entities": 0, "relations": 0}
        try:
            with self._conn() as conn:
                entities = conn.execute("SELECT COUNT(*) AS c FROM entities").fetchone()["c"]
                relations = conn.execute("SELECT COUNT(*) AS c FROM relations").fetchone()["c"]
            return {"enabled": True, "entities": int(entities), "relations": int(relations)}
        except Exception as exc:
            logger.warning(f"GraphMemory stats failed: {exc}")
            return {"enabled": True, "entities": 0, "relations": 0, "error": str(exc)}

    def health_check(self) -> dict[str, Any]:
        """Health check for graph-memory store."""
        if not self.enabled:
            return {"status": "disabled"}
        try:
            with self._conn() as conn:
                conn.execute("SELECT 1").fetchone()
            return {"status": "ok"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

