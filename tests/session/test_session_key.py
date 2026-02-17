def test_build_agent_session_key():
    from kabot.session.session_key import build_agent_session_key

    key = build_agent_session_key("work", "telegram", "123456")
    assert key == "agent:work:telegram:123456"

def test_parse_agent_session_key():
    from kabot.session.session_key import parse_agent_session_key

    parsed = parse_agent_session_key("agent:work:telegram:123456")
    assert parsed["agent_id"] == "work"
    assert parsed["channel"] == "telegram"
    assert parsed["chat_id"] == "123456"
