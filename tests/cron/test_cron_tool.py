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
    for action in ["add", "list", "remove", "update", "run", "runs", "status"]:
        assert action in actions, f"Missing action: {action}"

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
