import pytest

from kabot.agent.loop import AgentLoop
from kabot.bus.events import InboundMessage


@pytest.mark.asyncio
async def test_finalize_session_continues_when_session_save_fails():
    class _Memory:
        async def add_message(self, session_key, role, content):
            return None

    class _Sessions:
        def save(self, session):
            raise RuntimeError("session lock busy")

    class _Session:
        def add_message(self, role, content):
            return None

    fake_self = type("_FakeLoop", (), {"memory": _Memory(), "sessions": _Sessions()})()
    session = _Session()
    msg = InboundMessage(
        channel="cli",
        sender_id="user",
        chat_id="direct",
        content="hello",
        _session_key="cli:default",
    )

    result = await AgentLoop._finalize_session(fake_self, msg, session, "ok")

    assert result.content == "ok"
