"""Tests for SubagentDefaults schema."""

from kabot.config.schema import AgentDefaults, SubagentDefaults


class TestSubagentDefaults:
    def test_defaults(self):
        cfg = SubagentDefaults()
        assert cfg.max_spawn_depth == 1
        assert cfg.max_children_per_agent == 5
        assert cfg.archive_after_minutes == 60

    def test_custom_values(self):
        cfg = SubagentDefaults(max_spawn_depth=3, max_children_per_agent=10)
        assert cfg.max_spawn_depth == 3
        assert cfg.max_children_per_agent == 10

    def test_agent_defaults_has_subagents(self):
        defaults = AgentDefaults()
        assert hasattr(defaults, "subagents")
        assert isinstance(defaults.subagents, SubagentDefaults)
