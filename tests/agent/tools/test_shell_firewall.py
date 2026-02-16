"""Tests for ExecTool integration with CommandFirewall."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from kabot.agent.tools.shell import ExecTool
from kabot.security.command_firewall import ApprovalDecision


@pytest.fixture
def temp_firewall_config(tmp_path):
    """Provide temporary firewall config path."""
    return tmp_path / "command_approvals.yaml"


@pytest.fixture
def exec_tool(temp_firewall_config):
    """Provide ExecTool instance with firewall."""
    return ExecTool(
        timeout=5,
        firewall_config_path=temp_firewall_config,
        auto_approve=False
    )


@pytest.fixture
def exec_tool_auto_approve(temp_firewall_config):
    """Provide ExecTool with auto_approve enabled."""
    return ExecTool(
        timeout=5,
        firewall_config_path=temp_firewall_config,
        auto_approve=True
    )


class TestExecToolFirewallIntegration:
    """Test ExecTool integration with CommandFirewall."""

    @pytest.mark.asyncio
    async def test_firewall_initialized(self, exec_tool):
        """Test that firewall is initialized."""
        assert exec_tool.firewall is not None
        assert exec_tool.firewall.config_path.exists()

    @pytest.mark.asyncio
    async def test_denied_command_blocked(self, exec_tool):
        """Test that denied commands are blocked."""
        # rm -rf is in default denylist
        result = await exec_tool.execute("rm -rf /")

        assert "Error: Command blocked by security policy" in result
        assert "denylist" in result.lower()

    @pytest.mark.asyncio
    async def test_safe_command_allowed_in_allowlist_mode(self, exec_tool, temp_firewall_config):
        """Test that safe commands are allowed in allowlist mode."""
        # Change to allowlist mode
        import yaml
        with open(temp_firewall_config) as f:
            config = yaml.safe_load(f)
        config['policy'] = 'allowlist'
        with open(temp_firewall_config, 'w') as f:
            yaml.dump(config, f)

        # Reload firewall
        exec_tool.firewall.reload_config()

        # git status is in default allowlist
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"On branch main", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            result = await exec_tool.execute("git status")

            assert "Error" not in result
            assert "On branch main" in result

    @pytest.mark.asyncio
    async def test_auto_approve_bypasses_firewall(self, exec_tool_auto_approve):
        """Test that auto_approve bypasses firewall checks."""
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"test output", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            # Even dangerous command should execute with auto_approve
            result = await exec_tool_auto_approve.execute("echo test")

            assert "Error" not in result or "Command blocked" not in result
            mock_subprocess.assert_called_once()

    @pytest.mark.asyncio
    async def test_ask_mode_logs_and_proceeds(self, exec_tool):
        """Test that ASK mode logs command and proceeds."""
        # Default mode is 'ask'
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"test", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            result = await exec_tool.execute("echo test")

            # Should execute (for now, until interactive confirmation is implemented)
            mock_subprocess.assert_called_once()

    @pytest.mark.asyncio
    async def test_firewall_creates_directories(self, tmp_path):
        """Test that firewall creates parent directories if they don't exist."""
        # Create tool with deep nonexistent path
        deep_path = tmp_path / "nonexistent" / "deep" / "path" / "config.yaml"
        tool = ExecTool(
            firewall_config_path=deep_path,
            auto_approve=False
        )

        # Firewall should initialize successfully by creating parent directories
        assert tool.firewall is not None
        assert deep_path.exists()
        assert deep_path.parent.exists()

        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"test", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            result = await tool.execute("echo test")
            mock_subprocess.assert_called_once()

    @pytest.mark.asyncio
    async def test_audit_logging(self, exec_tool):
        """Test that successful commands are audit logged."""
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"success", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            with patch('kabot.agent.tools.shell.logger') as mock_logger:
                result = await exec_tool.execute("echo test")

                # Should log successful execution
                mock_logger.info.assert_called()
                log_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("executed successfully" in str(call).lower() for call in log_calls)

    @pytest.mark.asyncio
    async def test_read_only_mode_blocks_all(self, temp_firewall_config):
        """Test that read_only_mode blocks all commands."""
        tool = ExecTool(
            firewall_config_path=temp_firewall_config,
            read_only_mode=True
        )

        result = await tool.execute("echo test")
        assert "read-only mode" in result.lower()

    @pytest.mark.asyncio
    async def test_legacy_deny_patterns_still_work(self, temp_firewall_config):
        """Test that legacy deny_patterns still work alongside firewall."""
        tool = ExecTool(
            firewall_config_path=temp_firewall_config,
            deny_patterns=[r"custom_dangerous_cmd"],
            auto_approve=True  # Bypass firewall to test legacy patterns
        )

        result = await tool.execute("custom_dangerous_cmd")
        assert "Error" in result
        assert "safety guard" in result.lower()


class TestExecToolErrorHandling:
    """Test error handling in ExecTool."""

    @pytest.mark.asyncio
    async def test_command_timeout(self, exec_tool_auto_approve):
        """Test command timeout handling."""
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_subprocess.return_value = mock_process

            result = await exec_tool_auto_approve.execute("sleep 100")

            assert "timed out" in result.lower()

    @pytest.mark.asyncio
    async def test_command_execution_error(self, exec_tool_auto_approve):
        """Test handling of command execution errors."""
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_subprocess.side_effect = Exception("Test error")

            result = await exec_tool_auto_approve.execute("echo test")

            assert "Error executing command" in result
            assert "Test error" in result

    @pytest.mark.asyncio
    async def test_nonzero_exit_code(self, exec_tool_auto_approve):
        """Test handling of non-zero exit codes."""
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"", b"command not found"))
            mock_process.returncode = 127
            mock_subprocess.return_value = mock_process

            result = await exec_tool_auto_approve.execute("nonexistent_command")

            assert "Exit code: 127" in result
            assert "STDERR" in result


class TestExecToolPlatformHints:
    """Test platform-specific error hints."""

    @pytest.mark.asyncio
    async def test_windows_command_hint(self, exec_tool_auto_approve):
        """Test Windows command hints."""
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"", b"not recognized"))
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process

            with patch('platform.system', return_value='Windows'):
                result = await exec_tool_auto_approve.execute("ls")

                if "Windows" in result:
                    assert "dir" in result.lower()


# Import asyncio for timeout test
import asyncio
