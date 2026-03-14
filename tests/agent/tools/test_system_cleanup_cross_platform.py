from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kabot.agent.tools.cleanup import CleanupTool
from kabot.agent.tools.system import ServerMonitorTool, SystemInfoTool


@pytest.mark.asyncio
async def test_server_monitor_linux_script_stays_posix_sh_compatible(monkeypatch):
    tool = ServerMonitorTool()
    captured = {}

    async def _fake_run(script: str) -> str:
        captured["script"] = script
        return "ok"

    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr(tool, "_run_shell", _fake_run)

    result = await tool.execute()

    assert result == "ok"
    script = captured["script"]
    assert "command -v ip >/dev/null 2>&1" in script
    assert "&>/dev/null" not in script


@pytest.mark.asyncio
async def test_cleanup_linux_uses_noninteractive_sudo(monkeypatch):
    tool = CleanupTool()
    captured = {}

    async def _fake_run(script: str) -> str:
        captured["script"] = script
        return "ok"

    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr(tool, "_run_shell", _fake_run)

    result = await tool.execute(level="deep")

    assert result == "ok"
    script = captured["script"]
    assert "sudo -n apt-get clean" in script
    assert "sudo -n journalctl --vacuum-time=3d" in script
    assert "sudo -n apt-get autoremove -y" in script
    assert "sudo apt-get clean" not in script


@pytest.mark.asyncio
async def test_cleanup_macos_uses_noninteractive_sudo(monkeypatch):
    tool = CleanupTool()
    captured = {}

    async def _fake_run(script: str) -> str:
        captured["script"] = script
        return "ok"

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(tool, "_run_shell", _fake_run)

    result = await tool.execute(level="deep")

    assert result == "ok"
    script = captured["script"]
    assert "sudo -n periodic daily weekly monthly" in script
    assert "sudo periodic daily weekly monthly" not in script


@pytest.mark.asyncio
async def test_system_info_linux_uses_optional_command_fallbacks(monkeypatch):
    tool = SystemInfoTool()
    captured = {}

    async def _fake_run(script: str) -> str:
        captured["script"] = script
        return "ok"

    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr(tool, "_run_shell", _fake_run)

    result = await tool.execute()

    assert result == "ok"
    script = captured["script"]
    assert "command -v lscpu >/dev/null 2>&1" in script
    assert "grep -m1 'model name'" in script
    assert "command -v lsblk >/dev/null 2>&1" in script
    assert "df -h /" in script


@pytest.mark.asyncio
async def test_server_monitor_macos_avoids_bc_dependency(monkeypatch):
    tool = ServerMonitorTool()
    captured = {}

    async def _fake_run(script: str) -> str:
        captured["script"] = script
        return "ok"

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr(tool, "_run_shell", _fake_run)

    result = await tool.execute()

    assert result == "ok"
    script = captured["script"]
    assert "| bc" not in script
    assert "awk -v mem=" in script
    assert "BEGIN {printf" in script


@pytest.mark.asyncio
async def test_cleanup_linux_supports_multiple_package_managers(monkeypatch):
    tool = CleanupTool()
    captured = {}

    async def _fake_run(script: str) -> str:
        captured["script"] = script
        return "ok"

    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr(tool, "_run_shell", _fake_run)

    result = await tool.execute(level="deep")

    assert result == "ok"
    script = captured["script"]
    assert "command -v apt-get >/dev/null 2>&1" in script
    assert "command -v dnf >/dev/null 2>&1" in script
    assert "command -v yum >/dev/null 2>&1" in script
    assert "command -v pacman >/dev/null 2>&1" in script
    assert "command -v apk >/dev/null 2>&1" in script
    assert "command -v zypper >/dev/null 2>&1" in script
