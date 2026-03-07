from pathlib import Path

import pytest

from kabot.agent.context import ContextBuilder, TokenBudget
from kabot.memory.graph_memory import GraphMemory


def test_truncate_history_skips_non_dict_entries():
    budget = TokenBudget(model="gpt-4", max_context=8192)
    history = [
        {"role": "user", "content": "first"},
        ["unexpected", "list", "entry"],
        {"role": "assistant", "content": "second"},
    ]

    truncated = budget.truncate_history(history, budget=10_000)
    assert all(isinstance(msg, dict) for msg in truncated)
    assert [msg["content"] for msg in truncated] == ["first", "second"]


def test_build_messages_does_not_crash_on_malformed_history(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    history = [
        {"role": "assistant", "content": "ok"},
        ["malformed"],
    ]

    messages = builder.build_messages(history=history, current_message="halo")
    assert all(isinstance(msg, dict) for msg in messages)
    assert messages[-1]["role"] == "user"


def test_context_builder_passes_skills_config_to_loader(tmp_path: Path):
    managed_dir = tmp_path / "managed-skills"
    builder = ContextBuilder(
        tmp_path,
        skills_config={"load": {"managed_dir": str(managed_dir)}},
    )

    assert builder.skills.managed_skills == managed_dir


def test_context_builder_includes_graph_memory_when_available(tmp_path: Path):
    graph_db = tmp_path / "memory_db" / "graph_memory.db"
    graph = GraphMemory(graph_db, enabled=True)
    graph.ingest_text(
        session_id="s1",
        role="assistant",
        content="kabot uses chromadb for long-term memory",
    )

    builder = ContextBuilder(
        tmp_path,
        memory_config={"enable_graph_memory": True, "graph_injection_limit": 5},
    )
    prompt = builder.build_system_prompt(profile="GENERAL", current_message="what does kabot use?")
    assert "# Graph Memory" in prompt
    assert "kabot uses chromadb" in prompt.lower()


def test_context_builder_skips_auto_skill_match_for_heartbeat(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    calls = {"count": 0}

    def _match_skills(_msg: str, _profile: str):
        calls["count"] += 1
        return ["healthcheck"]

    builder.skills.match_skills = _match_skills  # type: ignore[assignment]
    prompt = builder.build_system_prompt(
        profile="GENERAL",
        current_message="Heartbeat task: Autopilot patrol: review recent context",
    )

    assert calls["count"] == 0
    assert "Auto-Selected Skills" not in prompt


def test_context_builder_skips_skills_summary_for_heartbeat(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    called = {"summary": 0}

    def _summary() -> str:
        called["summary"] += 1
        return "<skills><skill /></skills>"

    builder.skills.build_skills_summary = _summary  # type: ignore[assignment]
    prompt = builder.build_system_prompt(
        profile="GENERAL",
        current_message="Heartbeat task: Autopilot patrol: review pending schedules",
    )

    assert called["summary"] == 0
    assert "Available Skills (Reference Documents)" not in prompt


def test_token_budget_accepts_component_overrides():
    budget = TokenBudget(
        model="gpt-4",
        max_context=8192,
        component_overrides={"history": 0.18, "current": 0.14},
    )

    # History budget should downshift from default 0.30.
    assert budget.budgets["history"] < 0.30
    # Current-message budget should be larger than default 0.10.
    assert budget.budgets["current"] > 0.10
    # Total distribution stays normalized.
    assert sum(budget.budgets.values()) == pytest.approx(1.0, abs=1e-6)


def test_build_messages_exposes_dropped_history_summary(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    history = [{"role": "system", "content": "sys"}]
    for idx in range(20):
        history.append({"role": "user", "content": f"pesan lama user {idx} " + ("x" * 180)})
        history.append({"role": "assistant", "content": f"balasan lama {idx} " + ("y" * 180)})

    builder.build_messages(
        history=history,
        current_message="lanjut",
        max_context=700,
        budget_hints={"load_level": "high"},
    )
    summary_meta = builder.consume_last_truncation_summary()

    assert isinstance(summary_meta, dict)
    assert int(summary_meta.get("dropped_count", 0)) > 0
    assert "summary" in summary_meta
    assert len(str(summary_meta.get("summary") or "").strip()) > 0


def test_context_builder_budget_overrides_support_token_mode_hemat(tmp_path: Path):
    builder = ContextBuilder(tmp_path)

    overrides = builder._resolve_budget_overrides({"token_mode": "hemat"})

    assert isinstance(overrides, dict)
    assert overrides["history"] < 0.30
    assert overrides["current"] > 0.10
