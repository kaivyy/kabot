"""SQLite metadata store for conversation relationships and metadata."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from loguru import logger


class SQLiteMetadataStore:
    """
    SQLite database for storing conversation metadata and parent-child relationships.

    Prevents amnesia by maintaining proper message chains and session history.
    """

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database tables."""
        with self._get_connection() as conn:
            # Sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    channel TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    user_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)

            # Messages table with parent-child relationships
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    parent_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_type TEXT DEFAULT 'chat',
                    tool_calls TEXT,
                    tool_results TEXT,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    FOREIGN KEY (parent_id) REFERENCES messages(message_id)
                )
            """)

            # Memory index table (links to ChromaDB)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_index (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    chroma_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    FOREIGN KEY (message_id) REFERENCES messages(message_id)
                )
            """)

            # Long-term facts/memory
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    fact_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source_message_id TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)

            # Lessons table (metacognition — structured failure patterns)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lessons (
                    lesson_id TEXT PRIMARY KEY,
                    trigger TEXT NOT NULL,
                    mistake TEXT NOT NULL,
                    fix TEXT NOT NULL,
                    guardrail TEXT NOT NULL,
                    score_before INTEGER,
                    score_after INTEGER,
                    task_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Models table (scanned from APIs)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    context_window INTEGER,
                    max_output INTEGER,
                    pricing_input REAL,
                    pricing_output REAL,
                    capabilities TEXT,
                    is_premium INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # System logs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    module TEXT NOT NULL,
                    message TEXT NOT NULL,
                    exception TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON system_logs(level)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_created ON system_logs(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_parent ON messages(parent_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_session ON facts(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_lessons_type ON lessons(task_type)")

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def create_session(self, session_id: str, channel: str, chat_id: str,
                      user_id: str | None = None, metadata: dict | None = None) -> bool:
        """Create a new session."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO sessions
                       (session_id, channel, chat_id, user_id, metadata, updated_at)
                       VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (session_id, channel, chat_id, user_id,
                     json.dumps(metadata) if metadata else None)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return False

    def add_message(self, message_id: str, session_id: str, role: str,
                   content: str, parent_id: str | None = None,
                   message_type: str = "chat", tool_calls: list | None = None,
                   tool_results: list | None = None,
                   metadata: dict | None = None) -> bool:
        """
        Add a message with proper parent-child relationship.

        Args:
            message_id: Unique message ID
            session_id: Session ID
            role: user/assistant/system/tool
            content: Message content
            parent_id: Parent message ID (maintains conversation chain)
            message_type: Type of message
            tool_calls: Tool calls (for assistant messages)
            tool_results: Tool results (for tool messages)
            metadata: Additional metadata
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT INTO messages
                       (message_id, session_id, parent_id, role, content,
                        message_type, tool_calls, tool_results, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (message_id, session_id, parent_id, role, content,
                     message_type,
                     json.dumps(tool_calls) if tool_calls else None,
                     json.dumps(tool_results) if tool_results else None,
                     json.dumps(metadata) if metadata else None)
                )

                # Update session timestamp
                conn.execute(
                    "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                    (session_id,)
                )

                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            return False

    def get_message_chain(self, session_id: str, limit: int = 50) -> list[dict]:
        """
        Get conversation chain for a session.

        Returns messages in order with proper parent-child relationships.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """SELECT * FROM messages
                       WHERE session_id = ?
                       ORDER BY created_at DESC
                       LIMIT ?""",
                    (session_id, limit)
                )

                rows = cursor.fetchall()
                messages = []

                for row in rows:
                    msg = dict(row)
                    # Parse JSON fields
                    if msg.get("tool_calls"):
                        msg["tool_calls"] = json.loads(msg["tool_calls"])
                    if msg.get("tool_results"):
                        msg["tool_results"] = json.loads(msg["tool_results"])
                    if msg.get("metadata"):
                        msg["metadata"] = json.loads(msg["metadata"])
                    messages.append(msg)

                # Reverse to get chronological order
                messages.reverse()
                return messages

        except Exception as e:
            logger.error(f"Error getting message chain: {e}")
            return []

    def get_message_tree(self, message_id: str) -> list[dict]:
        """
        Get full conversation tree from a message (ancestors + descendants).

        This prevents amnesia by rebuilding full context.
        """
        try:
            with self._get_connection() as conn:
                # Get all ancestors (parents)
                ancestors = []
                current_id = message_id
                while current_id:
                    cursor = conn.execute(
                        "SELECT * FROM messages WHERE message_id = ?",
                        (current_id,)
                    )
                    row = cursor.fetchone()
                    if row:
                        msg = dict(row)
                        ancestors.append(msg)
                        current_id = msg.get("parent_id")
                    else:
                        break

                ancestors.reverse()
                return ancestors

        except Exception as e:
            logger.error(f"Error getting message tree: {e}")
            return []

    def add_fact(self, fact_id: str, category: str, key: str, value: str,
                session_id: str | None = None, confidence: float = 1.0,
                source_message_id: str | None = None) -> bool:
        """Add a long-term fact/memory."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO facts
                       (fact_id, session_id, category, key, value, confidence,
                        source_message_id, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (fact_id, session_id, category, key, value,
                     confidence, source_message_id)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding fact: {e}")
            return False

    def get_fact(self, fact_id: str) -> dict | None:
        """Get a specific fact by ID."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM facts WHERE fact_id = ?",
                    (fact_id,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Error getting fact: {e}")
            return None

    def get_facts(self, session_id: str | None = None,
                 category: str | None = None) -> list[dict]:
        """Get facts with optional filtering."""
        try:
            with self._get_connection() as conn:
                query = "SELECT * FROM facts WHERE 1=1"
                params = []

                if session_id:
                    query += " AND session_id = ?"
                    params.append(session_id)

                if category:
                    query += " AND category = ?"
                    params.append(category)

                query += " ORDER BY confidence DESC, updated_at DESC"

                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting facts: {e}")
            return []

    # ── Lessons (Metacognition) ─────────────────────────────────

    def add_lesson(self, lesson_id: str, trigger: str, mistake: str,
                   fix: str, guardrail: str, score_before: int | None = None,
                   score_after: int | None = None, task_type: str | None = None) -> bool:
        """Record a lesson from a failed/retried interaction."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO lessons
                       (lesson_id, trigger, mistake, fix, guardrail,
                        score_before, score_after, task_type)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (lesson_id, trigger, mistake, fix, guardrail,
                     score_before, score_after, task_type)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding lesson: {e}")
            return False

    def get_recent_lessons(self, limit: int = 10,
                           task_type: str | None = None) -> list[dict]:
        """Get recent lessons, optionally filtered by task type."""
        try:
            with self._get_connection() as conn:
                if task_type:
                    cursor = conn.execute(
                        """SELECT * FROM lessons
                           WHERE task_type = ?
                           ORDER BY created_at DESC LIMIT ?""",
                        (task_type, limit)
                    )
                else:
                    cursor = conn.execute(
                        """SELECT * FROM lessons
                           ORDER BY created_at DESC LIMIT ?""",
                        (limit,)
                    )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting lessons: {e}")
            return []

    def get_guardrails(self, limit: int = 5) -> list[str]:
        """Get unique guardrails for injection into system prompt."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """SELECT DISTINCT guardrail FROM lessons
                       ORDER BY created_at DESC LIMIT ?""",
                    (limit,)
                )
                return [row["guardrail"] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting guardrails: {e}")
            return []

    def save_memory_index(self, session_id: str, message_id: str,
                         chroma_id: str, content_hash: str) -> bool:
        """Save ChromaDB memory index reference."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT INTO memory_index
                       (session_id, message_id, chroma_id, content_hash)
                       VALUES (?, ?, ?, ?)""",
                    (session_id, message_id, chroma_id, content_hash)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving memory index: {e}")
            return False

    def get_stats(self) -> dict:
        """Get database statistics."""
        try:
            with self._get_connection() as conn:
                sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
                messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
                facts = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]

                return {
                    "sessions": sessions,
                    "messages": messages,
                    "facts": facts,
                    "db_size_mb": self.db_path.stat().st_size / (1024 * 1024)
                }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

    def save_model(self, model_data: dict) -> bool:
        """Save or update scanned model metadata."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO models
                       (id, name, provider, context_window, max_output,
                        pricing_input, pricing_output, capabilities, is_premium, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (
                        model_data["id"],
                        model_data["name"],
                        model_data["provider"],
                        model_data.get("context_window"),
                        model_data.get("max_output"),
                        model_data.get("pricing_input"),
                        model_data.get("pricing_output"),
                        json.dumps(model_data.get("capabilities", [])),
                        1 if model_data.get("is_premium") else 0
                    )
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return False

    def get_scanned_models(self) -> list[dict]:
        """Get all scanned models from the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT * FROM models")
                rows = cursor.fetchall()
                models = []
                for row in rows:
                    m = dict(row)
                    if m.get("capabilities"):
                        m["capabilities"] = json.loads(m["capabilities"])
                    models.append(m)
                return models
        except Exception as e:
            logger.error(f"Error getting scanned models: {e}")
            return []

    # ── System Logs ─────────────────────────────────────────────

    def add_log(self, level: str, module: str, message: str,
                metadata: dict | None = None, exception: str | None = None) -> bool:
        """Add a system log entry."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT INTO system_logs
                       (level, module, message, metadata, exception)
                       VALUES (?, ?, ?, ?, ?)""",
                    (level, module, message,
                     json.dumps(metadata) if metadata else None,
                     exception)
                )
                conn.commit()
                return True
        except Exception as e:
            # Don't log this error to avoid recursion if logger uses this DB
            print(f"Error adding log: {e}")
            return False

    def cleanup_logs(self, retention_days: int = 30) -> int:
        """Delete logs older than retention period."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """DELETE FROM system_logs
                       WHERE created_at < datetime('now', ?)""",
                    (f"-{retention_days} days",)
                )
                deleted = cursor.rowcount
                conn.commit()
                return deleted
        except Exception as e:
            print(f"Error cleaning logs: {e}")
            return 0
