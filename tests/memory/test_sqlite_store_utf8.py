from kabot.memory.sqlite_store import SQLiteMetadataStore


def test_add_message_with_unpaired_surrogate_is_utf8_safe(tmp_path):
    store = SQLiteMetadataStore(tmp_path / "utf8.db")
    store.create_session("s1", "telegram", "chat-1", user_id="u1")

    ok = store.add_message(
        message_id="m1",
        session_id="s1",
        role="assistant",
        content="bad surrogate \ud83d",
    )

    assert ok is True

    with store._get_connection() as conn:
        content = conn.execute(
            "SELECT content FROM messages WHERE message_id = ?",
            ("m1",),
        ).fetchone()[0]

    content.encode("utf-8")
    assert "\ud83d" not in content


def test_get_message_chain_repairs_missing_tool_result_pair(tmp_path):
    store = SQLiteMetadataStore(tmp_path / "repair.db")
    store.create_session("s1", "telegram", "chat-1", user_id="u1")

    assert store.add_message(
        message_id="m1",
        session_id="s1",
        role="assistant",
        content="checking",
        tool_calls=[{"id": "call-1", "name": "web_fetch", "arguments": {"url": "https://example.com"}}],
    )

    messages = store.get_message_chain("s1", limit=10)

    assert [msg["role"] for msg in messages] == ["assistant", "tool"]
    repaired = messages[-1]
    assert repaired["message_type"] == "tool_result_repair"
    assert repaired["metadata"]["synthetic_tool_result"] is True
    assert repaired["tool_results"][0]["tool_call_id"] == "call-1"
    assert "missing from persisted history" in repaired["content"]


def test_add_message_caps_large_tool_result_content(tmp_path):
    store = SQLiteMetadataStore(tmp_path / "tool-cap.db")
    store.create_session("s1", "telegram", "chat-1", user_id="u1")
    oversized = "x" * 25000

    assert store.add_message(
        message_id="m1",
        session_id="s1",
        role="tool",
        content=oversized,
        tool_results=[{"tool_call_id": "call-1", "name": "web_fetch", "result": oversized}],
    )

    with store._get_connection() as conn:
        row = conn.execute(
            "SELECT content, tool_results FROM messages WHERE message_id = ?",
            ("m1",),
        ).fetchone()

    assert row is not None
    content = row[0]
    assert len(content) <= 20000
    assert "truncated during persistence" in content
