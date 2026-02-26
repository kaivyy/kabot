from kabot.agent.loop import AgentLoop


def test_resolve_recovery_target_prefers_message_id_channel_chat():
    crash_data = {
        "session_id": "agent:main:main",
        "message_id": "telegram:8086618307:8086618307",
    }

    assert AgentLoop._resolve_recovery_target(crash_data) == (
        "telegram",
        "8086618307",
    )


def test_resolve_recovery_target_supports_instance_channel_keys():
    crash_data = {
        "session_id": "agent:main:main",
        "message_id": "telegram:team-a:chat-9:user-7",
    }

    assert AgentLoop._resolve_recovery_target(crash_data) == ("telegram:team-a", "chat-9")


def test_resolve_recovery_target_uses_session_id_when_message_id_invalid():
    crash_data = {
        "session_id": "telegram:chat-123",
        "message_id": "agent:main:main",
    }

    assert AgentLoop._resolve_recovery_target(crash_data) == ("telegram", "chat-123")


def test_resolve_recovery_target_returns_none_when_no_valid_target():
    crash_data = {
        "session_id": "agent:main:main",
        "message_id": "invalid-format",
    }

    assert AgentLoop._resolve_recovery_target(crash_data) is None
