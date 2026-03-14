"""Session management for conversation history."""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from kabot.core.context_engine import LegacyContextEngine
from kabot.core.queue import DormantQueue
from kabot.session.transcript import resolve_transcript_path, write_session_transcript
from kabot.utils.helpers import ensure_dir, safe_filename
from kabot.utils.pid_lock import PIDLock

_DURABLE_HISTORY_METADATA_KEY = "durable_history"


def _normalize_durable_history(messages: list[dict[str, Any]] | None, *, max_messages: int = 50) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in list(messages or []):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if not role or not content:
            continue
        normalized.append({"role": role, "content": content})
    if max_messages > 0:
        return normalized[-max_messages:]
    return normalized


@dataclass
class Session:
    """
    A conversation session.

    Stores messages in JSONL format for easy reading and persistence.
    """

    key: str  # channel:chat_id
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()

    def get_history(self, max_messages: int = 50) -> list[dict[str, Any]]:
        """
        Get message history for LLM context.

        Args:
            max_messages: Maximum messages to return.

        Returns:
            List of messages in LLM format.
        """
        return self.compile_context(max_messages=max_messages)

    def compile_context(self, max_messages: int = 50) -> list[dict[str, Any]]:
        """Compile LLM-ready history through the legacy context engine."""
        if not self.messages:
            return self.get_durable_history_snapshot(max_messages=max_messages)
        engine = LegacyContextEngine(max_messages=max_messages)
        return engine.compile(self)

    def get_durable_history_snapshot(self, max_messages: int = 50) -> list[dict[str, Any]]:
        """Return the persisted bounded history snapshot used for lightweight hydration."""
        snapshot = self.metadata.get(_DURABLE_HISTORY_METADATA_KEY, [])
        if isinstance(snapshot, list):
            return _normalize_durable_history(snapshot, max_messages=max_messages)
        return []

    def refresh_durable_history_snapshot(self, max_messages: int = 24) -> list[dict[str, Any]]:
        """Refresh the persisted bounded history snapshot from the latest session state."""
        if self.messages:
            snapshot = _normalize_durable_history(self.compile_context(max_messages=max_messages), max_messages=max_messages)
        else:
            snapshot = self.get_durable_history_snapshot(max_messages=max_messages)
        if snapshot:
            self.metadata[_DURABLE_HISTORY_METADATA_KEY] = snapshot
        else:
            self.metadata.pop(_DURABLE_HISTORY_METADATA_KEY, None)
        self.updated_at = datetime.now()
        return snapshot

    def clear(self) -> None:
        """Clear conversation history and transient runtime metadata."""
        self.messages = []
        self.metadata = {}
        self.updated_at = datetime.now()

    def enqueue_pending_work(self, payload: Any) -> None:
        """Persist resumable pending work alongside session metadata."""
        queue = DormantQueue({self.key: self._pending_work_items()})
        queue.enqueue(self.key, payload)
        self.metadata["pending_work"] = queue.snapshot().get(self.key, [])
        self.updated_at = datetime.now()

    def has_pending_work(self) -> bool:
        """Return True when the session has queued work to resume."""
        queue = DormantQueue({self.key: self._pending_work_items()})
        return queue.has_pending(self.key)

    def drain_pending_work(self) -> list[Any]:
        """Drain any queued pending work for this session."""
        queue = DormantQueue({self.key: self._pending_work_items()})
        items = queue.drain(self.key)
        if items:
            self.metadata.pop("pending_work", None)
            self.updated_at = datetime.now()
        return items

    def _pending_work_items(self) -> list[Any]:
        pending = self.metadata.get("pending_work", [])
        if isinstance(pending, list):
            return list(pending)
        return []


class SessionManager:
    """
    Manages conversation sessions.

    Sessions are stored as JSONL files in the sessions directory.
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sessions_dir = ensure_dir(Path.home() / ".kabot" / "sessions")
        self.transcripts_dir = ensure_dir(self.sessions_dir / "transcripts")
        self._cache: dict[str, Session] = {}

    def _get_session_path(self, key: str) -> Path:
        """Get the file path for a session."""
        safe_key = safe_filename(key.replace(":", "_"))
        return self.sessions_dir / f"{safe_key}.jsonl"

    def get_or_create(self, key: str) -> Session:
        """
        Get an existing session or create a new one.

        Args:
            key: Session key (usually channel:chat_id).

        Returns:
            The session.
        """
        # Check cache
        if key in self._cache:
            return self._cache[key]

        # Try to load from disk
        session = self._load(key)
        if session is None:
            session = Session(key=key)

        self._cache[key] = session
        return session

    def _load(self, key: str) -> Session | None:
        """Load a session from disk."""
        path = self._get_session_path(key)

        if not path.exists():
            return None

        try:
            messages = []
            metadata = {}
            created_at = None

            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)

                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
                    else:
                        messages.append(data)

            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                metadata=metadata
            )
        except Exception as e:
            logger.warning(f"Failed to load session {key}: {e}")
            return None

    def save(self, session: Session) -> None:
        """Save a session to disk with PID-based locking and atomic writes."""
        path = self._get_session_path(session.key)
        transcript_path = resolve_transcript_path(self.transcripts_dir, session.key)
        session.metadata["transcript_path"] = str(transcript_path)

        # Use PIDLock for multi-process safety (Phase 13 fix)
        with PIDLock(path):
            # Write to temp file first for atomic replacement
            temp_path = path.with_suffix(".tmp")

            with open(temp_path, "w") as f:
                # Write metadata first
                metadata_line = {
                    "_type": "metadata",
                    "created_at": session.created_at.isoformat(),
                    "updated_at": session.updated_at.isoformat(),
                    "metadata": session.metadata
                }
                f.write(json.dumps(metadata_line) + "\n")

                # Write messages
                for msg in session.messages:
                    f.write(json.dumps(msg) + "\n")

            # Atomic rename (replace existing if possible)
            if os.name == 'nt':  # Windows
                if path.exists():
                    os.remove(path)
                os.rename(temp_path, path)
            else:  # Unix
                os.replace(temp_path, path)

        self._cache[session.key] = session
        try:
            write_session_transcript(self.transcripts_dir, session)
        except Exception as e:
            logger.warning(f"Failed to update session transcript for {session.key}: {e}")

    def delete(self, key: str) -> bool:
        """
        Delete a session.

        Args:
            key: Session key.

        Returns:
            True if deleted, False if not found.
        """
        # Remove from cache
        self._cache.pop(key, None)

        # Remove file
        path = self._get_session_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all sessions.

        Returns:
            List of session info dicts.
        """
        sessions = []

        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                # Read just the metadata line
                with open(path) as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            sessions.append({
                                "key": path.stem.replace("_", ":"),
                                "created_at": data.get("created_at"),
                                "updated_at": data.get("updated_at"),
                                "path": str(path)
                            })
            except Exception:
                continue

        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
