from pathlib import Path

import pytest

from kabot.agent.context import ContextBuilder, TokenBudget
from kabot.agent.loop_core.message_runtime_parts.helpers import _build_temporal_context_note
from kabot.memory.graph_memory import GraphMemory
from kabot.utils.workspace_templates import ensure_workspace_templates


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


def test_build_messages_includes_explicit_history_context_marker_when_history_present(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    history = [
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "lanjutkan"},
    ]

    messages = builder.build_messages(history=history, current_message="pakai data terbaru")

    assert any(
        isinstance(msg, dict)
        and msg.get("role") == "system"
        and "[Chat messages since your last reply - for context]" in str(msg.get("content") or "")
        for msg in messages
    )
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


def test_context_builder_exposes_summary_first_skill_guidance_for_auto_selected_matches(tmp_path: Path):
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

    assert "## Skills (mandatory)" in prompt
    assert "references/" in prompt
    assert "scripts/" in prompt
    assert "If `web_search` is unavailable" in prompt
    assert "<available_skills>" in prompt
    assert "1password" in prompt
    assert "Use 1Password vaults to fetch and manage credentials." not in prompt


def test_context_builder_general_prompt_includes_diagnostics_and_api_skill_guidance(tmp_path: Path):
    builder = ContextBuilder(tmp_path)

    prompt = builder.build_system_prompt(
        profile="GENERAL",
        current_message="kenapa whatsapp kabot error dan tolong buat skill dari API ini",
    )

    assert "inspect real local evidence first" in prompt
    assert "config files, logs, docs, status output" in prompt
    assert "when creating a skill from an API" in prompt
    assert "`references/` for API notes" in prompt
    assert "`scripts/` for deterministic wrappers" in prompt


def test_context_builder_includes_openclaw_style_memory_recall_and_docs_guidance(tmp_path: Path):
    builder = ContextBuilder(tmp_path)

    prompt = builder.build_system_prompt(
        profile="GENERAL",
        current_message="what did you save about me and why is kabot behaving like this",
        tool_names=["memory_search", "get_memory", "read_file", "exec"],
    )

    assert "## Memory Recall" in prompt
    assert "use `memory_search` first" in prompt
    assert "use `get_memory` to pull only the needed details" in prompt
    assert "## Documentation & Diagnostics" in prompt
    assert "~/.kabot/config.json" in prompt
    assert "~/.kabot/logs/" in prompt


def test_context_builder_uses_summary_first_block_for_explicit_skill_usage_prompt(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    builder.skills.match_skills = lambda _msg, _profile: ["weather"]  # type: ignore[assignment]
    builder.skills.load_skills_for_context = lambda _skills: "Bring weather context into the reply."  # type: ignore[assignment]

    calls = {"summary": 0}

    def _summary(_skills: list[str]) -> str:
        calls["summary"] += 1
        return "<skills><skill><name>weather</name></skill></skills>"

    builder.skills.build_skills_summary_for_names = _summary  # type: ignore[assignment]

    prompt = builder.build_system_prompt(
        profile="GENERAL",
        current_message="Please use the weather skill for this request.",
    )

    assert "## Skills (mandatory)" in prompt
    assert "<available_skills>" in prompt
    assert "Bring weather context into the reply." not in prompt
    assert calls["summary"] == 1


def test_context_builder_loads_forced_skill_names_even_without_auto_match(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    builder.skills.match_skills = lambda _msg, _profile: []  # type: ignore[assignment]
    builder.skills.load_skills_for_context = lambda skills: (
        "Forced weather skill context loaded." if skills == ["weather"] else ""
    )  # type: ignore[assignment]

    prompt = builder.build_system_prompt(
        profile="GENERAL",
        current_message="prediksi 3-6 jam ke depan",
        skill_names=["weather"],
    )

    assert "Forced weather skill context loaded." in prompt
    assert "### Skill: weather" not in prompt
    assert "# Requested Skills" in prompt


def test_context_builder_keeps_external_requested_skills_summary_first_when_requested(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    builder.skills.match_skills = lambda _msg, _profile: []  # type: ignore[assignment]
    builder.skills.load_skills_for_context = lambda skills: (
        "Forced weather skill context loaded." if skills == ["weather"] else ""
    )  # type: ignore[assignment]
    builder.skills.build_skills_summary_for_names = (  # type: ignore[assignment]
        lambda skills: "<skills><skill><name>weather</name></skill></skills>"
        if skills == ["weather"]
        else ""
    )

    prompt = builder.build_system_prompt(
        profile="GENERAL",
        current_message="prediksi 3-6 jam ke depan",
        skill_names=["weather"],
        budget_hints={"summary_only_requested_skills": True},
    )

    assert "Forced weather skill context loaded." not in prompt
    assert "# Requested Skills" not in prompt
    assert "## Skills (mandatory)" in prompt
    assert "<available_skills>" in prompt
    assert "<skill><name>weather</name></skill>" in prompt


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

    assert "## Skills (mandatory)" in prompt
    assert "<available_skills>" in prompt
    assert "<skill><name>weather</name></skill>" in prompt
    assert calls["summary"] == 1


def test_context_builder_probe_mode_uses_compact_general_prompt_without_bootstrap_bloat(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    ensure_workspace_templates(workspace)
    (workspace / "AGENTS.md").write_text("A" * 600, encoding="utf-8")

    builder = ContextBuilder(workspace)
    builder.skills.match_skills = lambda _msg, _profile: ["weather"]  # type: ignore[assignment]
    builder.skills.load_skills_for_context = lambda _skills: "Use live weather tools."  # type: ignore[assignment]

    normal_prompt = builder.build_system_prompt(
        profile="GENERAL",
        current_message="Please use the weather skill for this request.",
    )
    compact_prompt = builder.build_system_prompt(
        profile="GENERAL",
        current_message="Please use the weather skill for this request.",
        budget_hints={"probe_mode": True},
    )

    assert "## AGENTS.md" in normal_prompt
    assert "## AGENTS.md" not in compact_prompt
    assert "## BOOTSTRAP.md" in normal_prompt
    assert "## BOOTSTRAP.md" not in compact_prompt
    assert "## SOUL.md" in compact_prompt
    assert "## TOOLS.md" in compact_prompt
    assert "## Workspace Persona & Local Truth" in compact_prompt
    assert "## Skills (mandatory)" in compact_prompt
    assert "Use live weather tools." not in compact_prompt
    assert len(compact_prompt) < len(normal_prompt)


def test_context_builder_identity_includes_explicit_timezone_label(tmp_path: Path):
    builder = ContextBuilder(tmp_path)

    prompt = builder.build_system_prompt(profile="GENERAL", current_message="hari apa sekarang")

    assert "## Current Time" in prompt
    assert "Timezone:" in prompt
    assert "UTC" in prompt


def test_context_builder_loads_bootstrap_md_when_present(tmp_path: Path):
    (tmp_path / "BOOTSTRAP.md").write_text(
        "# Bootstrap\n\nAsk onboarding questions before regular conversation.",
        encoding="utf-8",
    )
    builder = ContextBuilder(tmp_path)

    prompt = builder.build_system_prompt(profile="GENERAL", current_message="/start")

    assert "## BOOTSTRAP.md" in prompt
    assert "Ask onboarding questions before regular conversation." in prompt


def test_context_builder_loads_tools_md_when_present(tmp_path: Path):
    (tmp_path / "TOOLS.md").write_text(
        "# Tools\n\n- home-server -> 192.168.1.10",
        encoding="utf-8",
    )
    builder = ContextBuilder(tmp_path)

    prompt = builder.build_system_prompt(profile="GENERAL", current_message="cek status server")

    assert "## TOOLS.md" in prompt
    assert "home-server -> 192.168.1.10" in prompt


def test_context_builder_backfills_missing_identity_for_legacy_workspace(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# Agent Instructions\n", encoding="utf-8")
    (tmp_path / "SOUL.md").write_text("# SOUL.md - Who You Are\n", encoding="utf-8")
    (tmp_path / "TOOLS.md").write_text("# TOOLS.md - Local Notes\n", encoding="utf-8")
    (tmp_path / "USER.md").write_text("# USER.md - About Your Human\n", encoding="utf-8")

    assert not (tmp_path / "IDENTITY.md").exists()

    ContextBuilder(tmp_path)

    assert (tmp_path / "IDENTITY.md").exists()


def test_context_builder_prioritizes_workspace_persona_before_generic_profile(tmp_path: Path):
    ensure_workspace_templates(tmp_path)
    builder = ContextBuilder(tmp_path)

    prompt = builder.build_system_prompt(profile="GENERAL", current_message="halo")

    assert "## Workspace Persona & Local Truth" in prompt
    assert "## SOUL.md" in prompt
    assert "# Role: General Assistant" in prompt
    assert prompt.index("## SOUL.md") < prompt.index("# Role: General Assistant")


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
    builder.skills.build_skills_summary_for_names = (  # type: ignore[assignment]
        lambda _skills: "<skills><skill><name>weather</name></skill></skills>"
    )

    prompt = builder.build_messages(
        history=[],
        current_message="Please use the weather skill for this request.",
        profile="GENERAL",
        budget_hints={"probe_mode": True},
    )[0]["content"]

    assert "## Skills (mandatory)" in prompt
    assert "Use live weather tools." not in prompt


def test_context_builder_keeps_requested_skill_content_even_with_summary_first_prompting(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    builder.skills.match_skills = lambda _msg, _profile: ["weather"]  # type: ignore[assignment]
    builder.skills.load_skills_for_context = lambda skills: (
        "Requested weather skill context loaded." if skills == ["weather"] else ""
    )  # type: ignore[assignment]
    builder.skills.build_skills_summary_for_names = (  # type: ignore[assignment]
        lambda _skills: "<skills><skill><name>weather</name></skill></skills>"
    )

    prompt = builder.build_system_prompt(
        profile="GENERAL",
        current_message="tolong cek cuaca cilacap sekarang",
        skill_names=["weather"],
    )

    assert "# Requested Skills" in prompt
    assert "Requested weather skill context loaded." in prompt
    assert "## Skills (mandatory)" in prompt


def test_context_builder_does_not_auto_match_extra_skills_when_requested_skill_is_forced(tmp_path: Path):
    builder = ContextBuilder(tmp_path)
    builder.skills.match_skills = lambda _msg, _profile: ["brainstorming"]  # type: ignore[assignment]
    builder.skills.load_skills_for_context = lambda skills: (
        "Moon cheese skill context loaded." if skills == ["moon-cheese-protocol"] else ""
    )  # type: ignore[assignment]
    builder.skills.build_skills_summary_for_names = (  # type: ignore[assignment]
        lambda skills: "".join(
            f"<skill><name>{name}</name></skill>" for name in skills
        )
    )

    prompt = builder.build_system_prompt(
        profile="GENERAL",
        current_message="please explain the moon cheese protocol",
        skill_names=["moon-cheese-protocol"],
    )

    assert "Moon cheese skill context loaded." in prompt
    assert "moon-cheese-protocol" in prompt
    assert "<skill><name>brainstorming</name></skill>" not in prompt
    assert "Current best skill candidates from this request: moon-cheese-protocol" in prompt


def test_context_builder_skips_disable_model_invocation_skills_from_summary(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    hidden_skill_dir = workspace / "skills" / "internal-ledger"
    hidden_skill_dir.mkdir(parents=True, exist_ok=True)
    (hidden_skill_dir / "SKILL.md").write_text(
        (
            "---\n"
            "name: internal-ledger\n"
            "description: Internal ledger control skill\n"
            "disable-model-invocation: true\n"
            "---\n\n"
            "# Skill\n"
        ),
        encoding="utf-8",
    )
    visible_skill_dir = workspace / "skills" / "weather"
    visible_skill_dir.mkdir(parents=True, exist_ok=True)
    (visible_skill_dir / "SKILL.md").write_text(
        "---\nname: weather\ndescription: Weather helper\n---\n\n# Skill\n",
        encoding="utf-8",
    )

    builder = ContextBuilder(workspace)
    prompt = builder.build_system_prompt(
        profile="RESEARCH",
        current_message="research the weather today",
    )

    assert "weather" in prompt
    assert "internal-ledger" not in prompt


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
