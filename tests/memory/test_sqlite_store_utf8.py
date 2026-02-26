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
