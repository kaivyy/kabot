def test_build_agent_session_key():
    from kabot.session.session_key import build_agent_session_key

    # Test per-channel-peer format (non-main DM scope)
    key = build_agent_session_key(
        agent_id="work",
        channel="telegram",
        peer_kind="direct",
        peer_id="123456",
        dm_scope="per-channel-peer"
    )
    assert key == "agent:work:telegram:direct:123456"

def test_parse_agent_session_key():
    from kabot.session.session_key import parse_agent_session_key

    parsed = parse_agent_session_key("agent:work:telegram:direct:123456")
    assert parsed["agent_id"] == "work"
    assert parsed["channel"] == "telegram"
    assert parsed["peer_kind"] == "direct"
    assert parsed["peer_id"] == "123456"
