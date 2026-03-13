from pathlib import Path
from types import SimpleNamespace

import pytest

from kabot.core.command_router import CommandContext, CommandRouter
from kabot.core.commands_setup import register_builtin_commands


class _DummyStatusService:
    def get_status(self) -> str:
        return "status"


class _DummyBenchmarkService:
    async def run_benchmark(self, models=None) -> str:
        return "benchmark"


class _DummyDoctorService:
    async def run_all(self, auto_fix=False) -> str:
        return "doctor"


class _DummyUpdateService:
    async def check_for_updates(self) -> str:
        return "check"

    async def run_update(self) -> str:
        return "update"


class _DummySystemControl:
    async def restart(self) -> str:
        return "restart"

    async def get_system_info(self) -> str:
        return "sysinfo"


@pytest.mark.asyncio
async def test_builtin_help_includes_workspace_skill_surfaces_when_agent_loop_has_workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    skill_dir = workspace / "skills" / "meta-threads-official"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: meta-threads-official\ndescription: Use Meta Threads integration\n---\n\n# Skill\n",
        encoding="utf-8",
    )

    router = CommandRouter()
    register_builtin_commands(
        router,
        _DummyStatusService(),
        _DummyBenchmarkService(),
        _DummyDoctorService(),
        _DummyUpdateService(),
        _DummySystemControl(),
    )

    ctx = CommandContext(
        message="/help",
        args=[],
        sender_id="u1",
        channel="telegram",
        chat_id="c1",
        session_key="telegram:c1",
        agent_loop=SimpleNamespace(workspace=Path(workspace)),
    )
    result = await router.route("/help", ctx)

    assert result is not None
    assert "/status" in result
    assert "/update" in result
    assert "[admin]" in result
    assert "*Skills:*" in result
    assert "/meta_threads_official" in result
