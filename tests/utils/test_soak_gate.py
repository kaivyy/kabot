from pathlib import Path

from kabot.utils.soak_gate import evaluate_alpha_soak_gate, load_soak_metrics, parse_soak_metrics


def test_evaluate_alpha_soak_gate_passes_when_all_targets_met():
    metrics = parse_soak_metrics(
        {
            "runtime_hours": 24,
            "duplicate_side_effects": 0,
            "tool_protocol_breaks": 0,
            "p95_first_response_ms": 3900,
            "max_first_response_ms_soft": 4000,
        }
    )
    gate = evaluate_alpha_soak_gate(metrics)

    assert gate["passed"] is True
    assert gate["failures"] == []


def test_evaluate_alpha_soak_gate_reports_failures():
    metrics = parse_soak_metrics(
        {
            "runtime_hours": 8,
            "duplicate_side_effects": 2,
            "tool_protocol_breaks": 1,
            "p95_first_response_ms": 5300,
            "max_first_response_ms_soft": 4000,
        }
    )
    gate = evaluate_alpha_soak_gate(metrics)

    assert gate["passed"] is False
    assert set(gate["failures"]) == {
        "runtime_hours",
        "duplicate_side_effects",
        "tool_protocol_breaks",
        "p95_first_response_ms",
    }


def test_load_soak_metrics_returns_none_for_invalid_payload(tmp_path):
    metrics_path = Path(tmp_path) / "soak_latest.json"
    metrics_path.write_text('"oops"', encoding="utf-8")
    assert load_soak_metrics(metrics_path) is None
