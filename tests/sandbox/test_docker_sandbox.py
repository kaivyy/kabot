"""Tests for Docker sandbox (mocked Docker SDK)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kabot.sandbox.docker_sandbox import DockerSandbox


class TestDockerSandbox:
    def test_default_is_inactive(self):
        sb = DockerSandbox(image="kabot-sandbox")
        assert sb.image == "kabot-sandbox"
        assert sb.is_active is False

    def test_active_when_mode_all(self):
        sb = DockerSandbox(image="kabot-sandbox", mode="all")
        assert sb.is_active is True

    def test_workspace_access_defaults_rw(self):
        sb = DockerSandbox(image="kabot-sandbox")
        assert sb.workspace_access == "rw"

    @pytest.mark.asyncio
    async def test_exec_returns_output(self):
        sb = DockerSandbox(image="test", mode="all")
        with patch.object(sb, "_run_in_container", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "hello world"
            result = await sb.exec_command("echo hello world")
            assert result == "hello world"

    @pytest.mark.asyncio
    async def test_exec_noop_when_inactive(self):
        sb = DockerSandbox(image="test", mode="off")
        result = await sb.exec_command("echo test")
        assert result is None
