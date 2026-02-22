import pytest
from aiohttp import web

from kabot.cron.service import CronService
from kabot.cron.types import CronSchedule
from kabot.gateway.api.cron import create_cron_routes


@pytest.fixture
def cron_service(tmp_path):
    return CronService(tmp_path / "jobs.json")

def test_create_cron_routes(cron_service):
    """Test that cron routes are created."""
    routes = create_cron_routes(cron_service)
    assert routes is not None
    # Verify it's a RouteTableDef
    assert isinstance(routes, web.RouteTableDef)

@pytest.mark.asyncio
async def test_cron_routes_can_be_registered(cron_service):
    """Test that cron routes can be registered to an app."""
    routes = create_cron_routes(cron_service)
    app = web.Application()

    # This should not raise an error
    app.router.add_routes(routes)

    # Verify routes were added
    assert len(app.router.routes()) > 0

@pytest.mark.asyncio
async def test_cron_api_basic_functionality(cron_service):
    """Test basic cron API functionality."""
    await cron_service.start()

    # Add a test job
    cron_service.add_job(
        name="test",
        schedule=CronSchedule(kind="every", every_ms=60000),
        message="test message",
        deliver=True,
        channel="cli",
        to="direct"
    )

    # Verify job was added
    jobs = cron_service.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].name == "test"
