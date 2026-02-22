"""Structured security audit trail (JSONL)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


class AuditTrail:
    """Append-only JSONL security audit log."""

    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._log_file = self.log_dir / f"audit-{date_str}.jsonl"

    def log(
        self,
        event: str,
        data: dict[str, Any],
        actor: str = "system",
        severity: str = "info",
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "epoch_ms": int(time.time() * 1000),
            "event": event,
            "actor": actor,
            "severity": severity,
            "data": data,
        }
        try:
            with self._log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=True) + "\n")
        except Exception as err:  # pragma: no cover - defensive logging branch
            logger.error(f"Audit write failed: {err}")

    def query(self, event: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for log_file in sorted(self.log_dir.glob("*.jsonl"), reverse=True):
            for line in log_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event and entry.get("event") != event:
                    continue
                results.append(entry)
                if len(results) >= limit:
                    return results
        return results
