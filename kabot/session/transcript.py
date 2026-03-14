"""Session transcript mirror helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kabot.session.delivery_route import normalize_delivery_route
from kabot.utils.helpers import ensure_dir, safe_filename


def resolve_transcript_path(transcripts_dir: Path, session_key: str) -> Path:
    safe_key = safe_filename(str(session_key or "").replace(":", "_"))
    return ensure_dir(transcripts_dir) / f"{safe_key}.jsonl"


def write_session_transcript(transcripts_dir: Path, session: Any) -> Path:
    path = resolve_transcript_path(transcripts_dir, getattr(session, "key", "session"))
    metadata = getattr(session, "metadata", None)
    session_meta = metadata if isinstance(metadata, dict) else {}
    header = {
        "_type": "transcript",
        "session_key": getattr(session, "key", ""),
        "created_at": getattr(getattr(session, "created_at", None), "isoformat", lambda: "")(),
        "updated_at": getattr(getattr(session, "updated_at", None), "isoformat", lambda: "")(),
        "cwd": str(session_meta.get("working_directory") or "").strip() or None,
        "delivery_route": normalize_delivery_route(session_meta.get("delivery_route")),
    }
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(header, ensure_ascii=False) + "\n")
        for message in list(getattr(session, "messages", []) or []):
            if not isinstance(message, dict):
                continue
            fh.write(json.dumps(message, ensure_ascii=False) + "\n")
    return path
