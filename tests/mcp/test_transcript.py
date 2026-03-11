from kabot.mcp.transcript import make_mcp_missing_tool_result


def test_make_mcp_missing_tool_result_is_error_shaped():
    event = make_mcp_missing_tool_result(
        call_id="call-123",
        server_name="github",
        tool_name="list_prs",
    )

    assert event["role"] == "tool"
    assert event["tool_call_id"] == "call-123"
    assert event["tool_name"] == "mcp__github__list_prs"
    assert event["is_error"] is True
    assert "synthetic" in event["content"].lower()
