"""Tests for tool policy profiles."""

from kabot.agent.tools.tool_policy import (
    TOOL_GROUPS,
    apply_tool_policy,
    is_owner_only_tool,
    resolve_profile_policy,
)


def test_minimal_profile_only_allows_session_status():
    policy = resolve_profile_policy("minimal")
    assert "session_status" in policy.expand_groups()


def test_coding_profile_includes_fs_group():
    policy = resolve_profile_policy("coding")
    expanded = policy.expand_groups()
    assert "read_file" in expanded
    assert "write_file" in expanded


def test_full_profile_allows_everything():
    policy = resolve_profile_policy("full")
    assert policy.allow is None and policy.deny is None
    # Full profile should allow any tool
    assert policy.is_allowed("any_tool")


def test_owner_only_tools():
    assert is_owner_only_tool("cron") is True
    assert is_owner_only_tool("exec") is True
    assert is_owner_only_tool("read_file") is False


def test_apply_policy_filters_tools():
    tools = ["read_file", "exec", "cron", "weather"]
    policy = resolve_profile_policy("coding")
    filtered = apply_tool_policy(tools, policy)
    assert "read_file" in filtered
    assert "cron" not in filtered  # automation group denied
    assert "exec" not in filtered  # runtime group denied


def test_group_expansion():
    """Test that @group references expand correctly."""
    assert "read_file" in TOOL_GROUPS["fs"]
    assert "exec" in TOOL_GROUPS["runtime"]
    assert "cron" in TOOL_GROUPS["automation"]


def test_messaging_profile():
    policy = resolve_profile_policy("messaging")
    expanded = policy.expand_groups()
    assert "session_status" in expanded
    assert "gmail" in expanded
    # Should not have runtime tools
    assert "exec" not in expanded


def test_analysis_profile():
    policy = resolve_profile_policy("analysis")
    expanded = policy.expand_groups()
    assert "stock" in expanded
    assert "crypto" in expanded
    assert "weather" in expanded
    # Should not have filesystem tools
    assert "read_file" not in expanded
