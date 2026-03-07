from datetime import datetime

from kabot.session.manager import Session


def test_session_clear_resets_messages_and_metadata():
    session = Session(
        key="telegram:123",
        messages=[{"role": "user", "content": "hello"}],
        metadata={"pending_followup_tool": {"tool": "stock"}, "runtime_locale": "id"},
        updated_at=datetime.now(),
    )

    session.clear()

    assert session.messages == []
    assert session.metadata == {}
