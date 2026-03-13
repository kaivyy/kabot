import pytest

from kabot.agent.loop import AgentLoop
from kabot.bus.events import InboundMessage
from kabot.session.manager import Session, SessionManager


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


@pytest.mark.asyncio
async def test_finalize_session_appends_daily_notes_summary():
    class _Memory:
        async def add_message(self, session_key, role, content):
            return None

    class _Sessions:
        def save(self, session):
            return None

    class _Session:
        def add_message(self, role, content):
            return None

    class _DailyMemory:
        def __init__(self):
            self.entries = []

        def append_today(self, content):
            self.entries.append(content)

    daily = _DailyMemory()
    context = type("_Context", (), {"memory": daily})()
    fake_self = type(
        "_FakeLoop",
        (),
        {"memory": _Memory(), "sessions": _Sessions(), "context": context},
    )()

    session = _Session()
    msg = InboundMessage(
        channel="telegram",
        sender_id="user",
        chat_id="chat-42",
        content="halo kabot",
        _session_key="telegram:chat-42",
    )

    result = await AgentLoop._finalize_session(fake_self, msg, session, "siap, saya bantu")

    assert result.content == "siap, saya bantu"
    assert len(daily.entries) == 1
    assert "[telegram:chat-42]" in daily.entries[0]
    assert "U: halo kabot" in daily.entries[0]


@pytest.mark.asyncio
async def test_finalize_session_persists_durable_history_snapshot():
    class _Memory:
        async def add_message(self, session_key, role, content):
            return None

    class _Sessions:
        def save(self, session):
            return None

    fake_self = type("_FakeLoop", (), {"memory": _Memory(), "sessions": _Sessions()})()
    session = Session(key="cli:default")
    msg = InboundMessage(
        channel="cli",
        sender_id="user",
        chat_id="default",
        content="lanjut bikin file",
        _session_key="cli:default",
    )

    result = await AgentLoop._finalize_session(fake_self, msg, session, "siap, saya buatkan")

    assert result.content == "siap, saya buatkan"
    assert session.metadata["durable_history"] == [
        {"role": "user", "content": "lanjut bikin file"},
        {"role": "assistant", "content": "siap, saya buatkan"},
    ]


def test_session_manager_restores_history_from_durable_snapshot(tmp_path):
    manager = SessionManager(tmp_path)
    session = Session(
        key="telegram:chat-9",
        metadata={
            "durable_history": [
                {"role": "user", "content": "cuaca cilacap sekarang bagaimana"},
                {
                    "role": "assistant",
                    "content": "Sekarang berawan, paling aman bawa payung kecil.",
                },
            ]
        },
    )
    manager.save(session)

    restored = SessionManager(tmp_path).get_or_create("telegram:chat-9")
    restored.messages = []

    assert restored.get_history(max_messages=10) == [
        {"role": "user", "content": "cuaca cilacap sekarang bagaimana"},
        {"role": "assistant", "content": "Sekarang berawan, paling aman bawa payung kecil."},
    ]


@pytest.mark.asyncio
async def test_finalize_session_persists_last_navigated_path_from_message_metadata():
    class _Memory:
        async def add_message(self, session_key, role, content):
            return None

    class _Sessions:
        def save(self, session):
            return None

    fake_self = type("_FakeLoop", (), {"memory": _Memory(), "sessions": _Sessions()})()
    session = Session(key="telegram:chat-42")
    msg = InboundMessage(
        channel="telegram",
        sender_id="user",
        chat_id="chat-42",
        content="kirim file tes.md ke sini",
        _session_key="telegram:chat-42",
        metadata={"last_navigated_path": r"C:\Users\Arvy Kairi\Desktop\bot"},
    )

    result = await AgentLoop._finalize_session(fake_self, msg, session, "Message sent")

    assert result.content == "Message sent"
    assert session.metadata.get("last_navigated_path") == r"C:\Users\Arvy Kairi\Desktop\bot"


@pytest.mark.asyncio
async def test_init_session_hydrates_last_navigated_path_into_inbound_metadata():
    class _Memory:
        def create_session(self, session_key, channel, chat_id, sender_id):
            return None

        async def add_message(self, session_key, role, content):
            return None

    class _Sessions:
        def __init__(self, session):
            self._session = session

        def get_or_create(self, key):
            return self._session

    class _Sentinel:
        def mark_session_active(self, **_kwargs):
            return None

    class _Tools:
        def __init__(self):
            self._run_id = None

        def get(self, _name):
            return None

    session = Session(
        key="cli:direct",
        metadata={"last_navigated_path": r"C:\Users\Arvy Kairi\Desktop\bot"},
    )
    fake_self = type(
        "_FakeLoop",
        (),
        {
            "memory": _Memory(),
            "sessions": _Sessions(session),
            "sentinel": _Sentinel(),
            "tools": _Tools(),
            "runtime_performance": None,
        },
    )()

    msg = InboundMessage(
        channel="cli",
        sender_id="user",
        chat_id="direct",
        content="kirim file tes.md",
        _session_key="cli:direct",
        metadata={},
    )

    restored = await AgentLoop._init_session(fake_self, msg)

    assert restored is session
    assert msg.metadata.get("last_navigated_path") == r"C:\Users\Arvy Kairi\Desktop\bot"
    assert msg.metadata.get("last_tool_context", {}).get("path") == r"C:\Users\Arvy Kairi\Desktop\bot"


@pytest.mark.asyncio
async def test_init_session_hydrates_last_delivery_path_into_inbound_metadata():
    class _Memory:
        def create_session(self, session_key, channel, chat_id, sender_id):
            return None

        async def add_message(self, session_key, role, content):
            return None

    class _Sessions:
        def __init__(self, session):
            self._session = session

        def get_or_create(self, key):
            return self._session

    class _Sentinel:
        def mark_session_active(self, **_kwargs):
            return None

    class _Tools:
        def __init__(self):
            self._run_id = None

        def get(self, _name):
            return None

    session = Session(
        key="cli:direct",
        metadata={"last_delivery_path": r"C:\Users\Arvy Kairi\Desktop\bot\tes.md"},
    )
    fake_self = type(
        "_FakeLoop",
        (),
        {
            "memory": _Memory(),
            "sessions": _Sessions(session),
            "sentinel": _Sentinel(),
            "tools": _Tools(),
            "runtime_performance": None,
        },
    )()

    msg = InboundMessage(
        channel="cli",
        sender_id="user",
        chat_id="direct",
        content="kirim langsung",
        _session_key="cli:direct",
        metadata={},
    )

    restored = await AgentLoop._init_session(fake_self, msg)

    assert restored is session
    assert msg.metadata.get("last_delivery_path") == r"C:\Users\Arvy Kairi\Desktop\bot\tes.md"
