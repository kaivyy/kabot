"""Persistent subagent registry for tracking background tasks across restarts."""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime

from loguru import logger

from kabot.utils.pid_lock import PIDLock


@dataclass
class SubagentRunRecord:
    """Record of a subagent run."""
    run_id: str
    task: str
    label: str
    parent_session_key: str
    origin_channel: str
    origin_chat_id: str
    status: str  # "running", "completed", "failed"
    created_at: float
    completed_at: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None


class SubagentRegistry:
    """
    Persistent registry for subagent tasks.

    Pattern from OpenClaw: src/agents/subagent-registry.ts
    Tracks subagent lifecycle across process restarts.
    """

    def __init__(self, registry_path: Path):
        """
        Initialize subagent registry.

        Args:
            registry_path: Path to registry file (e.g., ~/.kabot/subagents/runs.json)
        """
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._runs: Dict[str, SubagentRunRecord] = {}
        self._load_registry()

    def register(
        self,
        run_id: str,
        task: str,
        label: str,
        parent_session_key: str,
        origin_channel: str,
        origin_chat_id: str,
    ) -> None:
        """
        Register a new subagent run.

        Args:
            run_id: Unique run identifier
            task: Task description
            label: Human-readable label
            parent_session_key: Parent session key
            origin_channel: Origin channel for results
            origin_chat_id: Origin chat ID for results
        """
        record = SubagentRunRecord(
            run_id=run_id,
            task=task,
            label=label,
            parent_session_key=parent_session_key,
            origin_channel=origin_channel,
            origin_chat_id=origin_chat_id,
            status="running",
            created_at=time.time(),
        )

        self._runs[run_id] = record
        self._save_registry()
        logger.info(f"Registered subagent run: {run_id} - {label}")

    def complete(
        self,
        run_id: str,
        result: str,
        status: str = "completed",
        error: Optional[str] = None,
    ) -> None:
        """
        Mark a subagent run as completed.

        Args:
            run_id: Run identifier
            result: Result message
            status: Final status ("completed" or "failed")
            error: Optional error message
        """
        if run_id not in self._runs:
            logger.warning(f"Attempted to complete unknown run: {run_id}")
            return

        self._runs[run_id].status = status
        self._runs[run_id].completed_at = time.time()
        self._runs[run_id].result = result
        self._runs[run_id].error = error

        self._save_registry()
        logger.info(f"Completed subagent run: {run_id} - {status}")

    def get(self, run_id: str) -> Optional[SubagentRunRecord]:
        """
        Get a subagent run record.

        Args:
            run_id: Run identifier

        Returns:
            SubagentRunRecord or None if not found
        """
        return self._runs.get(run_id)

    def list_running(self) -> List[SubagentRunRecord]:
        """
        List all running subagent tasks.

        Returns:
            List of running SubagentRunRecords
        """
        return [r for r in self._runs.values() if r.status == "running"]

    def list_all(self) -> List[SubagentRunRecord]:
        """
        List all subagent runs.

        Returns:
            List of all SubagentRunRecords
        """
        return list(self._runs.values())

    def cleanup_old_runs(self, max_age_seconds: int = 86400) -> int:
        """
        Clean up old completed runs.

        Args:
            max_age_seconds: Maximum age in seconds (default: 24 hours)

        Returns:
            Number of runs cleaned up
        """
        current_time = time.time()
        to_remove = []

        for run_id, record in self._runs.items():
            if record.status in ("completed", "failed"):
                if record.completed_at and (current_time - record.completed_at) > max_age_seconds:
                    to_remove.append(run_id)

        for run_id in to_remove:
            del self._runs[run_id]

        if to_remove:
            self._save_registry()
            logger.info(f"Cleaned up {len(to_remove)} old subagent runs")

        return len(to_remove)

    def _load_registry(self) -> None:
        """Load registry from disk."""
        if not self.registry_path.exists():
            logger.debug("No existing subagent registry found, starting fresh")
            return

        try:
            with open(self.registry_path) as f:
                data = json.load(f)

            self._runs = {}
            for run_id, record_dict in data.get("runs", {}).items():
                self._runs[run_id] = SubagentRunRecord(**record_dict)

            logger.info(f"Loaded {len(self._runs)} subagent runs from registry")

            # Log any running tasks from previous session
            running = self.list_running()
            if running:
                logger.warning(
                    f"Found {len(running)} subagent tasks that were running "
                    f"when the process last stopped"
                )

        except Exception as e:
            logger.error(f"Failed to load subagent registry: {e}")
            self._runs = {}

    def _save_registry(self) -> None:
        """Save registry to disk with PID locking."""
        try:
            # Use PIDLock for multi-process safety
            with PIDLock(self.registry_path):
                # Convert records to dict
                data = {
                    "runs": {
                        run_id: asdict(record)
                        for run_id, record in self._runs.items()
                    },
                    "last_updated": time.time(),
                    "last_updated_iso": datetime.now().isoformat(),
                }

                # Write to temp file first for atomic replacement
                temp_path = self.registry_path.with_suffix(".tmp")
                with open(temp_path, "w") as f:
                    json.dump(data, f, indent=2)

                # Atomic rename
                import os
                if os.name == 'nt':  # Windows
                    if self.registry_path.exists():
                        os.remove(self.registry_path)
                    os.rename(temp_path, self.registry_path)
                else:  # Unix
                    os.replace(temp_path, self.registry_path)

        except Exception as e:
            logger.error(f"Failed to save subagent registry: {e}")
