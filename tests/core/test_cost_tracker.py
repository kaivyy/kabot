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
    assert summary["usage_windows"]["7d"]["token_usage"] == {"input": 0, "output": 0, "total": 0}
    assert summary["usage_windows"]["30d"]["cost_history"] == []
    assert summary["usage_windows"]["all"]["model_usage"] == {}


def test_cost_tracker_reads_rich_transcript_usage_and_explicit_costs(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    log_path = sessions_dir / "rich.jsonl"
    today = date.today()

    _append_jsonl(
        log_path,
        {
            "timestamp": f"{today.isoformat()}T09:30:00",
            "message": {
                "role": "assistant",
                "provider": "openai-codex",
                "model": "gpt-5.3-codex",
                "usage": {
                    "prompt_tokens": 750,
                    "completion_tokens": 250,
                    "total_tokens": 1000,
                    "cost": {"total": 0.0123},
                },
            },
        },
    )
    _append_jsonl(
        log_path,
        {
            "role": "assistant",
            "timestamp": f"{today.isoformat()}T09:31:00",
            "model": "openai/gpt-4o-mini",
            "usage": {
                "input": 100,
                "output": 50,
                "total": 150,
                "estimated_cost_usd": 0.0002,
            },
        },
    )

    summary = CostTracker(sessions_dir).get_summary()

    assert summary["token_usage"] == {"input": 850, "output": 300, "total": 1150}
    assert summary["model_usage"] == {
        "openai-codex/gpt-5.3-codex": 1000,
        "openai/gpt-4o-mini": 150,
    }
    assert summary["model_costs"]["openai-codex/gpt-5.3-codex"] == pytest.approx(0.0123)
    assert summary["model_costs"]["openai/gpt-4o-mini"] == pytest.approx(0.0002)
    assert summary["today"] == pytest.approx(0.0125)


def test_cost_tracker_builds_usage_windows_for_7d_30d_and_all(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    log_path = sessions_dir / "windowed.jsonl"

    today = date.today()
    within_30d = today - timedelta(days=10)
    outside_30d = today - timedelta(days=40)

    _append_jsonl(
        log_path,
        {
            "role": "assistant",
            "timestamp": f"{today.isoformat()}T10:00:00",
            "model": "openai/gpt-4o-mini",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        },
    )
    _append_jsonl(
        log_path,
        {
            "role": "assistant",
            "timestamp": f"{within_30d.isoformat()}T10:00:00",
            "model": "openai-codex/gpt-5.3-codex",
            "usage": {"prompt_tokens": 200, "completion_tokens": 100},
        },
    )
    _append_jsonl(
        log_path,
        {
            "role": "assistant",
            "timestamp": f"{outside_30d.isoformat()}T10:00:00",
            "model": "groq/llama-3.3-70b",
            "usage": {"prompt_tokens": 300, "completion_tokens": 150},
        },
    )

    summary = CostTracker(sessions_dir).get_summary()

    usage_windows = summary["usage_windows"]
    assert usage_windows["7d"]["token_usage"] == {"input": 100, "output": 50, "total": 150}
    assert usage_windows["7d"]["model_usage"] == {"openai/gpt-4o-mini": 150}
    assert [entry["date"] for entry in usage_windows["7d"]["cost_history"]] == [today.isoformat()]

    assert usage_windows["30d"]["token_usage"] == {"input": 300, "output": 150, "total": 450}
    assert usage_windows["30d"]["model_usage"] == {
        "openai-codex/gpt-5.3-codex": 300,
        "openai/gpt-4o-mini": 150,
    }
    assert [entry["date"] for entry in usage_windows["30d"]["cost_history"]] == [
        within_30d.isoformat(),
        today.isoformat(),
    ]

    assert usage_windows["all"]["token_usage"] == {"input": 600, "output": 300, "total": 900}
    assert usage_windows["all"]["model_usage"] == {
        "groq/llama-3.3-70b": 450,
        "openai-codex/gpt-5.3-codex": 300,
        "openai/gpt-4o-mini": 150,
    }
    assert [entry["date"] for entry in usage_windows["all"]["cost_history"]] == [
        outside_30d.isoformat(),
        within_30d.isoformat(),
        today.isoformat(),
    ]
