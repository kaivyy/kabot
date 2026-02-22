"""REST API endpoints for cron job management."""

from aiohttp import web

from kabot.cron.service import CronService
from kabot.cron.types import CronSchedule


def create_cron_routes(cron: CronService) -> web.RouteTableDef:
    routes = web.RouteTableDef()

    @routes.get("/api/cron/status")
    async def status(request):
        return web.json_response(cron.status())

    @routes.get("/api/cron/jobs")
    async def list_jobs(request):
        jobs = cron.list_jobs(include_disabled=True)
        return web.json_response([_serialize_job(j) for j in jobs])

    @routes.post("/api/cron/jobs")
    async def add_job(request):
        data = await request.json()
        # Parse schedule from request
        sched_data = data.get("schedule", {})
        schedule = CronSchedule(
            kind=sched_data.get("kind", "at"),
            at_ms=sched_data.get("at_ms"),
            every_ms=sched_data.get("every_ms"),
            expr=sched_data.get("expr"),
            tz=sched_data.get("tz"),
        )
        job = cron.add_job(
            name=data.get("name", data.get("message", "")[:30]),
            schedule=schedule,
            message=data.get("message", ""),
            deliver=data.get("deliver", False),
            channel=data.get("channel"),
            to=data.get("to"),
            delete_after_run=data.get("delete_after_run", schedule.kind == "at"),
        )
        return web.json_response(_serialize_job(job), status=201)

    @routes.patch("/api/cron/jobs/{job_id}")
    async def update_job(request):
        job_id = request.match_info["job_id"]
        data = await request.json()
        job = cron.update_job(job_id, **data)
        if job:
            return web.json_response(_serialize_job(job))
        return web.json_response({"error": "Job not found"}, status=404)

    @routes.delete("/api/cron/jobs/{job_id}")
    async def remove_job(request):
        job_id = request.match_info["job_id"]
        if cron.remove_job(job_id):
            return web.json_response({"status": "deleted"})
        return web.json_response({"error": "Job not found"}, status=404)

    @routes.post("/api/cron/jobs/{job_id}/run")
    async def run_job(request):
        job_id = request.match_info["job_id"]
        if await cron.run_job(job_id, force=True):
            return web.json_response({"status": "executed"})
        return web.json_response({"error": "Job not found or disabled"}, status=404)

    @routes.get("/api/cron/jobs/{job_id}/runs")
    async def get_runs(request):
        job_id = request.match_info["job_id"]
        history = cron.get_run_history(job_id)
        return web.json_response(history)

    return routes


def _serialize_job(job) -> dict:
    """Serialize a CronJob to JSON-compatible dict."""
    return {
        "id": job.id,
        "name": job.name,
        "enabled": job.enabled,
        "schedule": {
            "kind": job.schedule.kind,
            "at_ms": job.schedule.at_ms,
            "every_ms": job.schedule.every_ms,
            "expr": job.schedule.expr,
            "tz": job.schedule.tz,
        },
        "payload": {
            "kind": job.payload.kind,
            "message": job.payload.message,
            "deliver": job.payload.deliver,
            "channel": job.payload.channel,
            "to": job.payload.to,
        },
        "state": {
            "next_run_at_ms": job.state.next_run_at_ms,
            "last_run_at_ms": job.state.last_run_at_ms,
            "last_status": job.state.last_status,
            "last_error": job.state.last_error,
        },
        "created_at_ms": job.created_at_ms,
        "updated_at_ms": job.updated_at_ms,
        "delete_after_run": job.delete_after_run,
    }
