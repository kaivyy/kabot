import pytest
from kabot.agent.tools.cron import build_reminder_context

def test_build_reminder_context():
    history = [
        {"role": "user", "content": "Besok ada meeting jam 9"},
        {"role": "assistant", "content": "Noted, meeting jam 9 pagi"},
    ]
    context = build_reminder_context(history, max_messages=5)
    assert "User: Besok ada meeting jam 9" in context
    assert "Assistant: Noted" in context

def test_context_truncation():
    history = [{"role": "user", "content": "x" * 500}]
    context = build_reminder_context(history, max_messages=5, max_per_message=100)
    assert len(context) < 250  # Should be truncated
