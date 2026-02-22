import pytest

from kabot.agent.tools.cron import CronTool
from kabot.cron.service import CronService


def test_flat_params_recovery():
    """Test that flat params are recovered into proper structure.

    Weaker LLMs may send flat params like:
    action="add", message="test", at_time="2026-02-15T10:00"

    Instead of nested structure. Our tool should handle both formats.
    """
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        svc = CronService(Path(tmpdir) / "jobs.json")
        tool = CronTool(svc)
        tool.set_context("cli", "direct")

        # Test that flat params work (this is the current implementation)
        params = tool.parameters

        # Verify all schedule params are at top level (flat)
        assert "at_time" in params["properties"]
        assert "every_seconds" in params["properties"]
        assert "cron_expr" in params["properties"]
        assert "message" in params["properties"]

        # These should all be top-level, not nested under "schedule"
        assert "schedule" not in params["properties"]

@pytest.mark.asyncio
async def test_flat_params_execution():
    """Test that execute method accepts flat params."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        svc = CronService(Path(tmpdir) / "jobs.json")
        tool = CronTool(svc)
        tool.set_context("cli", "direct")

        # Execute with flat params (as weak models would send)
        result = await tool.execute(
            action="add",
            message="Test reminder",
            at_time="2026-02-15T10:00:00+07:00"
        )

        assert "Created job" in result
        assert "Test reminder" in result
