from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from kabot.core.cost_tracker import CostTracker
from kabot.core.costs import estimate_cost_usd


def _append_jsonl(path, payload: dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")


def test_cost_tracker_summary_includes_daily_history_and_model_breakdown(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    log_path = sessions_dir / "demo.jsonl"

    today = date.today()
    yesterday = today - timedelta(days=1)

    _append_jsonl(
        log_path,
        {
            "role": "assistant",
            "timestamp": f"{today.isoformat()}T09:30:00",
            "model": "gpt-4o-mini",
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
        },
    )
    _append_jsonl(
        log_path,
        {
            "role": "assistant",
            "timestamp": f"{yesterday.isoformat()}T07:15:00",
            "model": "claude-3-haiku",
            "usage": {"prompt_tokens": 200, "completion_tokens": 800},
        },
    )
    _append_jsonl(
        log_path,
        {
            "role": "user",
            "timestamp": f"{today.isoformat()}T09:31:00",
            "content": "ignored user event",
        },
    )

    summary = CostTracker(sessions_dir).get_summary()

    today_cost = estimate_cost_usd("gpt-4o-mini", 1000, 500)
    yesterday_cost = estimate_cost_usd("claude-3-haiku", 200, 800)

    assert summary["today"] == pytest.approx(today_cost)
    assert summary["total"] == pytest.approx(today_cost + yesterday_cost)
    assert summary["token_usage"] == {"input": 1200, "output": 1300, "total": 2500}
    assert summary["model_usage"] == {
        "gpt-4o-mini": 1500,
        "claude-3-haiku": 1000,
    }
    assert summary["model_costs"]["gpt-4o-mini"] == pytest.approx(today_cost)
    assert summary["model_costs"]["claude-3-haiku"] == pytest.approx(yesterday_cost)

    history = {entry["date"]: entry for entry in summary["cost_history"]}
    assert history[today.isoformat()]["cost"] == pytest.approx(today_cost)
    assert history[today.isoformat()]["tokens"] == 1500
    assert history[yesterday.isoformat()]["cost"] == pytest.approx(yesterday_cost)
    assert history[yesterday.isoformat()]["tokens"] == 1000


def test_cost_tracker_empty_summary_includes_extended_fields(tmp_path):
    summary = CostTracker(tmp_path / "missing").get_summary()

    assert summary["today"] == 0.0
    assert summary["total"] == 0.0
    assert summary["projected_monthly"] == 0.0
    assert summary["token_usage"] == {"input": 0, "output": 0, "total": 0}
    assert summary["model_usage"] == {}
    assert summary["model_costs"] == {}
    assert summary["cost_history"] == []
