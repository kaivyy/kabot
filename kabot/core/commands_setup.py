"""
Built-in slash command handlers for Kabot.

Registers all default commands with the CommandRouter.
"""

import logging
from typing import Any

from kabot.core.command_router import CommandContext, CommandRouter
from kabot.core.status import StatusService, BenchmarkService
from kabot.core.doctor import DoctorService
from kabot.core.update import UpdateService, SystemControl

logger = logging.getLogger(__name__)


def register_builtin_commands(
    router: CommandRouter,
    status_service: StatusService,
    benchmark_service: BenchmarkService,
    doctor_service: DoctorService,
    update_service: UpdateService,
    system_control: SystemControl,
) -> None:
    """Register all built-in slash commands."""

    # ─── /help ───
    async def cmd_help(ctx: CommandContext) -> str:
        return router.get_help_text()

    router.register("/help", cmd_help, "Show available commands")

    # ─── /status ───
    async def cmd_status(ctx: CommandContext) -> str:
        return status_service.get_status()

    router.register("/status", cmd_status, "Show system health & stats")

    # ─── /benchmark ───
    async def cmd_benchmark(ctx: CommandContext) -> str:
        models = ctx.args if ctx.args else None
        return await benchmark_service.run_benchmark(models)

    router.register("/benchmark", cmd_benchmark, "Run LLM performance benchmark")

    # ─── /switch ───
    async def cmd_switch(ctx: CommandContext) -> str:
        if not ctx.args:
            loop = ctx.agent_loop
            current = getattr(loop, 'model', 'unknown') if loop else 'unknown'
            return f"Current model: `{current}`\nUsage: `/switch <model_name>`"

        new_model = ctx.args[0]
        loop = ctx.agent_loop
        if loop:
            old_model = getattr(loop, 'model', 'unknown')
            loop.model = new_model
            return f"✅ Switched model: `{old_model}` → `{new_model}`"
        return "❌ Cannot switch model: agent loop not available."

    router.register("/switch", cmd_switch, "Switch active LLM model")

    # ─── /doctor ───
    async def cmd_doctor(ctx: CommandContext) -> str:
        auto_fix = "fix" in ctx.args
        return await doctor_service.run_all(auto_fix=auto_fix)

    router.register("/doctor", cmd_doctor, "Run system diagnostics")

    # ─── /update ───
    async def cmd_update(ctx: CommandContext) -> str:
        if "check" in ctx.args:
            return await update_service.check_for_updates()
        return await update_service.run_update()

    router.register("/update", cmd_update, "Update Kabot from git", admin_only=True)

    # ─── /restart ───
    async def cmd_restart(ctx: CommandContext) -> str:
        return await system_control.restart()

    router.register("/restart", cmd_restart, "Restart the bot process", admin_only=True)

    # ─── /sysinfo ───
    async def cmd_sysinfo(ctx: CommandContext) -> str:
        return await system_control.get_system_info()

    router.register("/sysinfo", cmd_sysinfo, "Show system information")

    # ─── /uptime ───
    async def cmd_uptime(ctx: CommandContext) -> str:
        from datetime import timedelta
        uptime = timedelta(seconds=int(router.uptime_seconds))
        return f"⏱ *Uptime*: {uptime}"

    router.register("/uptime", cmd_uptime, "Show bot uptime")

    # ─── /clip ───
    async def cmd_clip(ctx: CommandContext) -> str:
        if not ctx.args:
            return "Usage: `/clip <text>`"

        text = " ".join(ctx.args)
        from kabot.core.windows import clip_copy
        if clip_copy(text):
            return "✅ Copied to clipboard!"
        return "❌ Failed to copy (is clip.exe available?)"

    router.register("/clip", cmd_clip, "Copy text to system clipboard")

    logger.info(f"Registered {len(router._commands)} built-in commands")
