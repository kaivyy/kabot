from pathlib import Path

from kabot.agent.context import ContextBuilder, TokenBudget


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
