"""Tool loop detection — detect stuck agents calling same tools repeatedly."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal

HISTORY_SIZE = 30
WARNING_THRESHOLD = 10
CRITICAL_THRESHOLD = 20


@dataclass
class LoopDetectionResult:
    stuck: bool = False
    level: Literal["warning", "critical"] | None = None
    detector: str = ""
    count: int = 0
    message: str = ""
    paired_tool: str | None = None


def _hash_call(tool_name: str, params: Any) -> str:
    """Create stable hash of tool name + params."""
    try:
        serialized = json.dumps(params, sort_keys=True, default=str)
    except (TypeError, ValueError):
        serialized = str(params)
    raw = f"{tool_name}:{serialized}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


class LoopDetector:
    def __init__(
        self,
        history_size: int = HISTORY_SIZE,
        warning_threshold: int = WARNING_THRESHOLD,
        critical_threshold: int = CRITICAL_THRESHOLD,
    ):
        self.history_size = history_size
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self._history: list[dict[str, str]] = []

    def record(self, tool_name: str, params: Any, tool_call_id: str | None = None) -> None:
        entry = {
            "tool_name": tool_name,
            "args_hash": _hash_call(tool_name, params),
        }
        self._history.append(entry)
        if len(self._history) > self.history_size:
            self._history = self._history[-self.history_size :]

    def check(self, tool_name: str, params: Any) -> LoopDetectionResult:
        current_hash = _hash_call(tool_name, params)

        # Generic repeat detection
        repeat_count = sum(
            1 for h in self._history
            if h["args_hash"] == current_hash
        )

        if repeat_count >= self.critical_threshold:
            return LoopDetectionResult(
                stuck=True, level="critical", detector="generic_repeat",
                count=repeat_count,
                message=f"Tool '{tool_name}' called {repeat_count} times with same params — blocked.",
            )
        if repeat_count >= self.warning_threshold:
            return LoopDetectionResult(
                stuck=True, level="warning", detector="generic_repeat",
                count=repeat_count,
                message=f"Tool '{tool_name}' called {repeat_count} times with same params — warning.",
            )

        # Ping-pong detection
        if len(self._history) >= 4:
            recent = self._history[-4:]
            signatures = [f"{h['tool_name']}:{h['args_hash']}" for h in recent]
            if len(signatures) == 4 and signatures[0] == signatures[2] and signatures[1] == signatures[3]:
                pair_count = sum(1 for i in range(0, len(self._history) - 1, 2)
                    if i + 1 < len(self._history)
                    and f"{self._history[i]['tool_name']}:{self._history[i]['args_hash']}" == signatures[0]
                    and f"{self._history[i+1]['tool_name']}:{self._history[i+1]['args_hash']}" == signatures[1]
                )
                if pair_count >= self.warning_threshold // 2:
                    return LoopDetectionResult(
                        stuck=True, level="critical" if pair_count >= self.critical_threshold // 2 else "warning",
                        detector="ping_pong", count=pair_count,
                        message=f"Ping-pong detected: {recent[0]['tool_name']} ↔ {recent[1]['tool_name']} ({pair_count} cycles)",
                        paired_tool=recent[1]["tool_name"],
                    )

        return LoopDetectionResult()
