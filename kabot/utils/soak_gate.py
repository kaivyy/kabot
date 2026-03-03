"""Wave 1 soak-gate metrics loader and evaluator."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class SoakGateMetrics:
    """Normalized soak metrics required for the 0.5.8-alpha gate."""

    runtime_hours: float = 0.0
    duplicate_side_effects: int = 0
    tool_protocol_breaks: int = 0
    p95_first_response_ms: float = 0.0
    max_first_response_ms_soft: int = 4000
    required_hours: int = 24


def parse_soak_metrics(payload: dict[str, Any]) -> SoakGateMetrics:
    """Parse raw metrics payload into typed gate metrics."""
    return SoakGateMetrics(
        runtime_hours=float(payload.get("runtime_hours", 0.0) or 0.0),
        duplicate_side_effects=int(payload.get("duplicate_side_effects", 0) or 0),
        tool_protocol_breaks=int(payload.get("tool_protocol_breaks", 0) or 0),
        p95_first_response_ms=float(payload.get("p95_first_response_ms", 0.0) or 0.0),
        max_first_response_ms_soft=int(payload.get("max_first_response_ms_soft", 4000) or 4000),
        required_hours=int(payload.get("required_hours", 24) or 24),
    )


def load_soak_metrics(metrics_path: Path) -> SoakGateMetrics | None:
    """Load soak metrics from json file; return None when unreadable/invalid."""
    try:
        raw = json.loads(metrics_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return parse_soak_metrics(raw)
    except Exception:
        return None


def evaluate_alpha_soak_gate(metrics: SoakGateMetrics) -> dict[str, Any]:
    """Evaluate alpha soak gate with deterministic pass/fail checks."""
    checks = [
        {
            "name": "runtime_hours",
            "passed": metrics.runtime_hours >= float(metrics.required_hours),
            "value": metrics.runtime_hours,
            "target": metrics.required_hours,
            "operator": ">=",
        },
        {
            "name": "duplicate_side_effects",
            "passed": metrics.duplicate_side_effects == 0,
            "value": metrics.duplicate_side_effects,
            "target": 0,
            "operator": "==",
        },
        {
            "name": "tool_protocol_breaks",
            "passed": metrics.tool_protocol_breaks == 0,
            "value": metrics.tool_protocol_breaks,
            "target": 0,
            "operator": "==",
        },
        {
            "name": "p95_first_response_ms",
            "passed": metrics.p95_first_response_ms <= float(metrics.max_first_response_ms_soft),
            "value": metrics.p95_first_response_ms,
            "target": metrics.max_first_response_ms_soft,
            "operator": "<=",
        },
    ]
    failures = [check["name"] for check in checks if not bool(check["passed"])]
    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "checks": checks,
        "metrics": asdict(metrics),
    }
