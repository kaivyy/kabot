from pathlib import Path

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
