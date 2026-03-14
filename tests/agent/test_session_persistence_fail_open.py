import json

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
async def test_finalize_session_persists_last_delivery_path_from_message_metadata():
    class _Memory:
        async def add_message(self, session_key, role, content):
            return None

    class _Sessions:
        def save(self, session):
            return None

    fake_self = type("_FakeLoop", (), {"memory": _Memory(), "sessions": _Sessions()})()
    session = Session(key="telegram:chat-43")
    msg = InboundMessage(
        channel="telegram",
        sender_id="user",
        chat_id="chat-43",
        content="kirim langsung",
        _session_key="telegram:chat-43",
        metadata={"last_delivery_path": r"C:\Users\Arvy Kairi\Desktop\bot\tes.md"},
    )

    result = await AgentLoop._finalize_session(fake_self, msg, session, "Message sent")

    assert result.content == "Message sent"
    assert session.metadata.get("last_delivery_path") == r"C:\Users\Arvy Kairi\Desktop\bot\tes.md"


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
async def test_finalize_session_persists_working_directory_from_message_metadata():
    class _Memory:
        async def add_message(self, session_key, role, content):
            return None

    class _Sessions:
        def save(self, session):
            return None

    fake_self = type("_FakeLoop", (), {"memory": _Memory(), "sessions": _Sessions()})()
    session = Session(key="telegram:chat-44")
    msg = InboundMessage(
        channel="telegram",
        sender_id="user",
        chat_id="chat-44",
        content="kirim file tes.md ke sini",
        _session_key="telegram:chat-44",
        metadata={"working_directory": r"C:\Users\Arvy Kairi\Desktop\bot"},
    )

    result = await AgentLoop._finalize_session(fake_self, msg, session, "Message sent")

    assert result.content == "Message sent"
    assert session.metadata.get("working_directory") == r"C:\Users\Arvy Kairi\Desktop\bot"


@pytest.mark.asyncio
async def test_finalize_session_prefers_working_directory_over_redundant_last_navigated_path():
    class _Memory:
        async def add_message(self, session_key, role, content):
            return None

    class _Sessions:
        def save(self, session):
            return None

    fake_self = type("_FakeLoop", (), {"memory": _Memory(), "sessions": _Sessions()})()
    session = Session(key="telegram:chat-45")
    msg = InboundMessage(
        channel="telegram",
        sender_id="user",
        chat_id="chat-45",
        content="open folder bot",
        _session_key="telegram:chat-45",
        metadata={
            "working_directory": r"C:\Users\Arvy Kairi\Desktop\bot",
            "last_navigated_path": r"C:\Users\Arvy Kairi\Desktop\bot",
        },
    )

    result = await AgentLoop._finalize_session(fake_self, msg, session, "opened")

    assert result.content == "opened"
    assert session.metadata.get("working_directory") == r"C:\Users\Arvy Kairi\Desktop\bot"
    assert "last_navigated_path" not in session.metadata


@pytest.mark.asyncio
async def test_finalize_session_persists_structured_delivery_route():
    class _Memory:
        async def add_message(self, session_key, role, content):
            return None

    class _Sessions:
        def save(self, session):
            return None

    fake_self = type("_FakeLoop", (), {"memory": _Memory(), "sessions": _Sessions()})()
    session = Session(key="slack:channel-77")
    msg = InboundMessage(
        channel="slack",
        sender_id="user",
        chat_id="channel-77",
        content="send it here",
        _session_key="slack:channel-77",
        account_id="acct-1",
        peer_kind="group",
        peer_id="channel-77",
        team_id="team-9",
        thread_id="171717.0001",
        metadata={},
    )

    result = await AgentLoop._finalize_session(fake_self, msg, session, "sent")

    assert result.content == "sent"
    assert session.metadata.get("delivery_route") == {
        "channel": "slack",
        "chat_id": "channel-77",
        "account_id": "acct-1",
        "peer_kind": "group",
        "peer_id": "channel-77",
        "team_id": "team-9",
        "thread_id": "171717.0001",
    }


@pytest.mark.asyncio
async def test_finalize_session_formats_plain_text_as_json_when_json_directive_is_active():
    class _Memory:
        async def add_message(self, session_key, role, content):
            return None

    class _Sessions:
        def save(self, session):
            return None

    fake_self = type("_FakeLoop", (), {"memory": _Memory(), "sessions": _Sessions()})()
    session = Session(key="cli:json")
    msg = InboundMessage(
        channel="cli",
        sender_id="user",
        chat_id="direct",
        content="/json hello",
        _session_key="cli:json",
        metadata={"directive_json_output": True},
    )

    result = await AgentLoop._finalize_session(fake_self, msg, session, "hello there")

    assert json.loads(result.content) == {"response": "hello there"}
    assert result.metadata["response_format"] == "json"


@pytest.mark.asyncio
async def test_finalize_session_marks_raw_output_to_disable_markdown_rendering():
    class _Memory:
        async def add_message(self, session_key, role, content):
            return None

    class _Sessions:
        def save(self, session):
            return None

    fake_self = type("_FakeLoop", (), {"memory": _Memory(), "sessions": _Sessions()})()
    session = Session(key="cli:raw")
    msg = InboundMessage(
        channel="cli",
        sender_id="user",
        chat_id="direct",
        content="/raw hello",
        _session_key="cli:raw",
        metadata={"directive_raw": True},
    )

    result = await AgentLoop._finalize_session(fake_self, msg, session, "**hello**")

    assert result.content == "**hello**"
    assert result.metadata["render_markdown"] is False
    assert getattr(fake_self, "_last_outbound_metadata", {})["render_markdown"] is False


@pytest.mark.asyncio
async def test_init_session_promotes_legacy_last_navigated_path_to_working_directory_metadata():
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
    assert msg.metadata.get("working_directory") == r"C:\Users\Arvy Kairi\Desktop\bot"
    assert "last_navigated_path" not in msg.metadata
    assert msg.metadata.get("last_tool_context", {}).get("path") == r"C:\Users\Arvy Kairi\Desktop\bot"


@pytest.mark.asyncio
async def test_init_session_hydrates_working_directory_into_inbound_metadata():
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
        metadata={"working_directory": r"C:\Users\Arvy Kairi\Desktop\bot"},
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
    assert msg.metadata.get("working_directory") == r"C:\Users\Arvy Kairi\Desktop\bot"
    assert msg.metadata.get("last_tool_context", {}).get("path") == r"C:\Users\Arvy Kairi\Desktop\bot"


@pytest.mark.asyncio
async def test_init_session_prefers_working_directory_over_last_navigated_path_when_both_exist():
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
        metadata={
            "working_directory": r"C:\Users\Arvy Kairi\Desktop\bot",
            "last_navigated_path": r"C:\Users\Arvy Kairi\Desktop",
        },
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
    assert msg.metadata.get("working_directory") == r"C:\Users\Arvy Kairi\Desktop\bot"
    assert msg.metadata.get("last_tool_context", {}).get("path") == r"C:\Users\Arvy Kairi\Desktop\bot"
    assert "last_navigated_path" not in msg.metadata


@pytest.mark.asyncio
async def test_init_session_keeps_last_delivery_path_in_session_fallback_not_active_metadata():
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
    assert "last_delivery_path" not in msg.metadata


@pytest.mark.asyncio
async def test_init_session_hydrates_delivery_route_into_inbound_metadata():
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

    class _MessageTool:
        def __init__(self):
            self.calls = []

        def set_context(self, channel, chat_id, delivery_route=None):
            self.calls.append((channel, chat_id, delivery_route))

    class _Tools:
        def __init__(self, message_tool):
            self._run_id = None
            self._message_tool = message_tool

        def get(self, name):
            if name == "message":
                return self._message_tool
            return None

    session = Session(
        key="slack:channel-77",
        metadata={
            "delivery_route": {
                "channel": "slack",
                "chat_id": "channel-77",
                "account_id": "acct-1",
                "peer_kind": "group",
                "peer_id": "channel-77",
                "team_id": "team-9",
                "thread_id": "171717.0001",
            }
        },
    )
    message_tool = _MessageTool()
    fake_self = type(
        "_FakeLoop",
        (),
        {
            "memory": _Memory(),
            "sessions": _Sessions(session),
            "sentinel": _Sentinel(),
            "tools": _Tools(message_tool),
            "runtime_performance": None,
        },
    )()

    msg = InboundMessage(
        channel="slack",
        sender_id="user",
        chat_id="channel-77",
        content="send it",
        _session_key="slack:channel-77",
        metadata={},
    )

    restored = await AgentLoop._init_session(fake_self, msg)

    assert restored is session
    assert msg.metadata.get("delivery_route") == {
        "channel": "slack",
        "chat_id": "channel-77",
        "account_id": "acct-1",
        "peer_kind": "group",
        "peer_id": "channel-77",
        "team_id": "team-9",
        "thread_id": "171717.0001",
    }
    assert message_tool.calls == [
        (
            "slack",
            "channel-77",
            {
                "channel": "slack",
                "chat_id": "channel-77",
                "account_id": "acct-1",
                "peer_kind": "group",
                "peer_id": "channel-77",
                "team_id": "team-9",
                "thread_id": "171717.0001",
            },
        )
    ]


def test_session_manager_writes_transcript_mirror_with_header_and_messages(tmp_path):
    manager = SessionManager(tmp_path)
    session = Session(
        key="cli:direct",
        metadata={
            "working_directory": str((tmp_path / "workspace").resolve()),
            "delivery_route": {
                "channel": "cli",
                "chat_id": "direct",
            },
        },
    )
    session.add_message("user", "open the project folder")
    session.add_message("assistant", "I opened the project folder.")

    manager.save(session)

    transcript_path = manager.transcripts_dir / "cli_direct.jsonl"
    assert transcript_path.exists()
    lines = transcript_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    header = __import__("json").loads(lines[0])
    first = __import__("json").loads(lines[1])
    second = __import__("json").loads(lines[2])

    assert header["_type"] == "transcript"
    assert header["session_key"] == "cli:direct"
    assert header["cwd"] == str((tmp_path / "workspace").resolve())
    assert header["delivery_route"] == {"channel": "cli", "chat_id": "direct"}
    assert first["role"] == "user"
    assert first["content"] == "open the project folder"
    assert second["role"] == "assistant"
    assert second["content"] == "I opened the project folder."
