import pytest
import asyncio
from pathlib import Path
from kabot.cron.service import CronService
from kabot.cron.types import CronSchedule
from kabot.agent.tools.cron import CronTool

@pytest.fixture
def cron_tool(tmp_path):
    svc = CronService(tmp_path / "jobs.json")
    tool = CronTool(svc)
    tool.set_context("whatsapp", "628123456")
    return tool, svc

def test_actions_include_update_run_status(cron_tool):
    tool, _ = cron_tool
    params = tool.parameters
    actions = params["properties"]["action"]["enum"]
    for action in [
        "add",
        "list",
        "list_groups",
        "remove",
        "remove_group",
        "update",
        "update_group",
        "run",
        "runs",
        "status",
    ]:
        assert action in actions, f"Missing action: {action}"
    assert "start_at" in params["properties"]

@pytest.mark.asyncio
async def test_status_action(cron_tool):
    tool, svc = cron_tool
    await svc.start()
    result = await tool.execute(action="status")
    assert "enabled" in result.lower() or "jobs" in result.lower()

@pytest.mark.asyncio
async def test_update_action(cron_tool):
    tool, svc = cron_tool
    # Add a job first
    svc.add_job("test", CronSchedule(kind="every", every_ms=60000), "hello",
                deliver=True, channel="cli", to="direct")
    jobs = svc.list_jobs()
    job_id = jobs[0].id
    result = await tool.execute(action="update", job_id=job_id, message="updated message")
    assert "updated" in result.lower() or job_id in result

@pytest.mark.asyncio
async def test_run_action(cron_tool):
    tool, svc = cron_tool
    executed = []
    async def on_job(job):
        executed.append(job.id)
        return "done"
    svc.on_job = on_job
    svc.add_job("test", CronSchedule(kind="every", every_ms=60000), "hello",
                deliver=True, channel="cli", to="direct")
    jobs = svc.list_jobs()
    result = await tool.execute(action="run", job_id=jobs[0].id)
    assert len(executed) == 1

@pytest.mark.asyncio
async def test_runs_action(cron_tool):
    tool, svc = cron_tool
    svc.add_job("test", CronSchedule(kind="every", every_ms=60000), "hello",
                deliver=True, channel="cli", to="direct")
    jobs = svc.list_jobs()
    result = await tool.execute(action="runs", job_id=jobs[0].id)
    assert "history" in result.lower() or "no runs" in result.lower()


@pytest.mark.asyncio
async def test_add_action_supports_every_with_start_anchor(cron_tool):
    tool, svc = cron_tool
    result = await tool.execute(
        action="add",
        message="shift-cycle-start",
        every_seconds=12 * 86400,
        start_at="2026-02-20T00:00:00+07:00",
    )
    assert "Created job" in result

    jobs = svc.list_jobs(include_disabled=True)
    assert len(jobs) == 1
    assert jobs[0].schedule.kind == "every"
    assert jobs[0].schedule.every_ms == 12 * 86400 * 1000
    assert jobs[0].schedule.start_at_ms is not None


@pytest.mark.asyncio
async def test_add_action_localizes_response_from_context_text(cron_tool):
    tool, _ = cron_tool
    result = await tool.execute(
        action="add",
        message="drink water",
        every_seconds=3600,
        context_text="tolong ingatkan saya tiap jam",
    )
    assert "berhasil membuat job" in result.lower()
    assert "created job" not in result.lower()


@pytest.mark.asyncio
async def test_list_groups_shows_group_title_and_id(cron_tool):
    tool, _ = cron_tool
    await tool.execute(
        action="add",
        message="mulai shift",
        title="Shift Team A",
        group_id="grp_shift_a",
        every_seconds=12 * 86400,
        start_at="2026-02-20T00:00:00+07:00",
    )
    await tool.execute(
        action="add",
        message="selesai shift",
        title="Shift Team A",
        group_id="grp_shift_a",
        every_seconds=12 * 86400,
        start_at="2026-02-20T08:00:00+07:00",
    )

    result = await tool.execute(action="list_groups")
    assert "Shift Team A" in result
    assert "grp_shift_a" in result
    assert "jobs: 2" in result


@pytest.mark.asyncio
async def test_remove_group_removes_all_group_jobs(cron_tool):
    tool, svc = cron_tool
    await tool.execute(
        action="add",
        message="mulai shift",
        title="Shift Team B",
        group_id="grp_shift_b",
        every_seconds=12 * 86400,
        start_at="2026-02-20T00:00:00+07:00",
    )
    await tool.execute(
        action="add",
        message="selesai shift",
        title="Shift Team B",
        group_id="grp_shift_b",
        every_seconds=12 * 86400,
        start_at="2026-02-20T08:00:00+07:00",
    )

    result = await tool.execute(action="remove_group", group_id="grp_shift_b")
    assert "Removed group" in result
    assert len(svc.list_jobs(include_disabled=True)) == 0


@pytest.mark.asyncio
async def test_update_group_can_rename_and_reschedule(cron_tool):
    tool, svc = cron_tool
    await tool.execute(
        action="add",
        message="standup harian",
        title="Team Ops",
        group_id="grp_ops",
        every_seconds=86400,
        start_at="2026-02-20T09:00:00+07:00",
    )

    result = await tool.execute(
        action="update_group",
        group_id="grp_ops",
        new_title="Team Ops Updated",
        every_seconds=2 * 86400,
        start_at="2026-02-20T10:00:00+07:00",
    )
    assert "Updated group" in result

    jobs = svc.list_jobs(include_disabled=True)
    assert len(jobs) == 1
    assert jobs[0].payload.group_title == "Team Ops Updated"
    assert jobs[0].schedule.kind == "every"
    assert jobs[0].schedule.every_ms == 2 * 86400 * 1000


@pytest.mark.asyncio
async def test_list_groups_uses_cron_ops_delegate(monkeypatch, cron_tool):
    tool, _ = cron_tool
    from kabot.agent.tools.cron_ops import actions as cron_actions

    def _fake_handle_list_groups(tool_instance):
        assert tool_instance is tool
        return "delegated-groups"

    monkeypatch.setattr(cron_actions, "handle_list_groups", _fake_handle_list_groups)
    result = await tool.execute(action="list_groups")
    assert result == "delegated-groups"
