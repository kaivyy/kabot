"""Tests for Docker sandbox (mocked Docker SDK)."""

from unittest.mock import MagicMock, patch

import pytest

from kabot.sandbox.docker_sandbox import DockerSandbox


class TestDockerSandbox:
    def test_init_sets_defaults(self):
        sb = DockerSandbox(image="kabot-sandbox")
        assert sb.image == "kabot-sandbox"
        assert sb.workspace_access == "rw"

    @pytest.mark.asyncio
    async def test_exec_command_returns_output(self):
        with patch("kabot.sandbox.docker_sandbox.docker") as mock_docker:
            mock_container = MagicMock()
            mock_container.exec_run.return_value = (0, b"hello\n")
            mock_docker.from_env.return_value.containers.run.return_value = mock_container
            sb = DockerSandbox(image="test")
            result = await sb.exec_command("echo hello")
            assert "hello" in result

    def test_sandbox_off_is_noop(self):
        sb = DockerSandbox(image="test", mode="off")
        assert sb.is_active is False
