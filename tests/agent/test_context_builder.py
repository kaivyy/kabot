from pathlib import Path

import pytest

from kabot.agent.context import ContextBuilder, TokenBudget
from kabot.agent.loop_core.message_runtime_parts.helpers import _build_temporal_context_note
from kabot.memory.graph_memory import GraphMemory


def _write_skill(skill_root: Path, skill_name: str, body: str, *, description: str = "test skill") -> None:
    skill_dir = skill_root / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )


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


def test_context_builder_loads_auto_selected_skill_content_for_decorated_unavailable_names(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    _write_skill(
        workspace / "skills",
        "1password",
        "Use 1Password vaults to fetch and manage credentials.",
        description="vault credential manager",
    )

    builder = ContextBuilder(workspace)
    builder.skills.match_skills = lambda _msg, _profile: ["1password [NEEDS: ENV: OP_SESSION]"]  # type: ignore[assignment]

    prompt = builder.build_system_prompt(
        profile="GENERAL",
        current_message="please use the 1password skill for this vault task",
    )

    assert "Auto-Selected Skills" in prompt
    assert "1password [NEEDS: ENV: OP_SESSION]" in prompt
    assert "Use 1Password vaults to fetch and manage credentials." in prompt


def test_context_builder_skips_skills_summary_for_explicit_skill_usage_prompt(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    builder.skills.match_skills = lambda _msg, _profile: ["weather"]  # type: ignore[assignment]
    builder.skills.load_skills_for_context = lambda _skills: "Bring weather context into the reply."  # type: ignore[assignment]

    calls = {"summary": 0}

    def _summary() -> str:
        calls["summary"] += 1
        return "<skills><skill /></skills>"

    builder.skills.build_skills_summary = _summary  # type: ignore[assignment]

    prompt = builder.build_system_prompt(
        profile="GENERAL",
        current_message="Please use the weather skill for this request.",
    )

    assert "Auto-Selected Skills" in prompt
    assert "Bring weather context into the reply." in prompt
    assert "Available Skills (Reference Documents)" not in prompt
    assert calls["summary"] == 0


def test_context_builder_includes_skills_summary_for_catalog_question(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    builder.skills.match_skills = lambda _msg, _profile: []  # type: ignore[assignment]

    calls = {"summary": 0}

    def _summary() -> str:
        calls["summary"] += 1
        return "<skills><skill><name>weather</name></skill></skills>"

    builder.skills.build_skills_summary = _summary  # type: ignore[assignment]

    prompt = builder.build_system_prompt(
        profile="GENERAL",
        current_message="Skill apa yang tersedia di workspace ini?",
    )

    assert "Available Skills (Reference Documents)" in prompt
    assert "<skills><skill><name>weather</name></skill></skills>" in prompt
    assert calls["summary"] == 1


def test_context_builder_probe_mode_uses_compact_general_prompt_without_bootstrap_bloat(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "AGENTS.md").write_text("A" * 5000, encoding="utf-8")

    builder = ContextBuilder(workspace)
    builder.skills.match_skills = lambda _msg, _profile: ["weather"]  # type: ignore[assignment]
    builder.skills.load_skills_for_context = lambda _skills: "Use live weather tools."  # type: ignore[assignment]

    normal_prompt = builder.build_messages(
        history=[],
        current_message="Please use the weather skill for this request.",
        profile="GENERAL",
    )[0]["content"]
    compact_prompt = builder.build_messages(
        history=[],
        current_message="Please use the weather skill for this request.",
        profile="GENERAL",
        budget_hints={"probe_mode": True},
    )[0]["content"]

    assert "## AGENTS.md" in normal_prompt
    assert "## AGENTS.md" not in compact_prompt
    assert "Auto-Selected Skills" in compact_prompt
    assert "Use live weather tools." in compact_prompt
    assert len(compact_prompt) < len(normal_prompt)


def test_context_builder_identity_includes_explicit_timezone_label(tmp_path: Path):
    builder = ContextBuilder(tmp_path)

    prompt = builder.build_system_prompt(profile="GENERAL", current_message="hari apa sekarang")

    assert "## Current Time" in prompt
    assert "Timezone:" in prompt
    assert "UTC" in prompt


def test_context_builder_probe_mode_skips_auto_skill_match_for_light_general_turn(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    calls = {"match": 0}

    def _match(_msg: str, _profile: str):
        calls["match"] += 1
        return ["weather"]

    builder.skills.match_skills = _match  # type: ignore[assignment]

    builder.build_messages(
        history=[],
        current_message="hari apa sekarang?",
        profile="GENERAL",
        budget_hints={"probe_mode": True},
    )

    assert calls["match"] == 0


def test_context_builder_probe_mode_skips_memory_context_for_light_general_turn(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    builder.memory.get_memory_context = lambda: "VERY LARGE MEMORY BLOCK"  # type: ignore[assignment]

    prompt = builder.build_messages(
        history=[],
        current_message="hari apa sekarang?",
        profile="GENERAL",
        budget_hints={"probe_mode": True},
    )[0]["content"]

    assert "VERY LARGE MEMORY BLOCK" not in prompt


def test_context_builder_probe_mode_still_loads_explicit_skill_context(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    builder.skills.match_skills = lambda _msg, _profile: ["weather"]  # type: ignore[assignment]
    builder.skills.load_skills_for_context = lambda _skills: "Use live weather tools."  # type: ignore[assignment]

    prompt = builder.build_messages(
        history=[],
        current_message="Please use the weather skill for this request.",
        profile="GENERAL",
        budget_hints={"probe_mode": True},
    )[0]["content"]

    assert "Auto-Selected Skills" in prompt
    assert "Use live weather tools." in prompt


def test_context_builder_probe_mode_still_includes_memory_for_recall_turn(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    builder.memory.get_memory_context = lambda: "VERY LARGE MEMORY BLOCK"  # type: ignore[assignment]

    prompt = builder.build_messages(
        history=[],
        current_message="ingat preferensi saya apa?",
        profile="GENERAL",
        budget_hints={"probe_mode": True},
    )[0]["content"]

    assert "VERY LARGE MEMORY BLOCK" in prompt


def test_context_builder_probe_mode_keeps_temporal_system_note_turns_lean(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    calls = {"match": 0, "memory": 0}

    def _match(_msg: str, _profile: str):
        calls["match"] += 1
        return ["weather"]

    def _memory() -> str:
        calls["memory"] += 1
        return "VERY LARGE MEMORY BLOCK"

    builder.skills.match_skills = _match  # type: ignore[assignment]
    builder.memory.get_memory_context = _memory  # type: ignore[assignment]

    prompt = builder.build_messages(
        history=[],
        current_message=f"hari apa sekarang?\n\n{_build_temporal_context_note()}",
        profile="GENERAL",
        budget_hints={"probe_mode": True},
    )[0]["content"]

    assert calls["match"] == 0
    assert calls["memory"] == 0
    assert "VERY LARGE MEMORY BLOCK" not in prompt


def test_context_builder_mcp_context_mode_skips_auto_skill_match_for_explicit_mcp_context(
    tmp_path: Path,
):
    builder = ContextBuilder(tmp_path)
    calls = {"match": 0}

    def _match(_msg: str, _profile: str):
        calls["match"] += 1
        return ["weather"]

    builder.skills.match_skills = _match  # type: ignore[assignment]

    builder.build_messages(
        history=[],
        current_message=(
            "gunakan prompt briefing dari server local lalu jawab satu kata.\n\n"
            "[MCP Context Note]\n"
            "Use the MCP prompt below as explicit context."
        ),
        profile="GENERAL",
        budget_hints={"mcp_context_mode": True},
    )

    assert calls["match"] == 0


def test_context_builder_mcp_context_mode_skips_memory_context_for_explicit_mcp_context(
    tmp_path: Path,
):
    builder = ContextBuilder(tmp_path)
    builder.memory.get_memory_context = lambda: "VERY LARGE MEMORY BLOCK"  # type: ignore[assignment]

    prompt = builder.build_messages(
        history=[],
        current_message=(
            "baca resource memory://field-guide dari server local.\n\n"
            "[MCP Context Note]\n"
            "Use the MCP resource below as explicit context."
        ),
        profile="GENERAL",
        budget_hints={"mcp_context_mode": True},
    )[0]["content"]

    assert "VERY LARGE MEMORY BLOCK" not in prompt
