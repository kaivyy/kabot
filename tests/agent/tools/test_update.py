import json
from unittest.mock import AsyncMock, patch

import pytest

from kabot.agent.tools import update as update_module
from kabot.agent.tools.update import CheckUpdateTool, SystemUpdateTool


@pytest.mark.asyncio
async def test_check_update_tool_git_install():
    """Test CheckUpdateTool detects git install."""
    tool = CheckUpdateTool()

    with patch.object(tool, '_detect_install_method', return_value='git'), \
         patch.object(tool, '_get_current_version', return_value='0.5.2'), \
         patch.object(tool, '_fetch_github_release', new_callable=AsyncMock, return_value={
             'tag_name': 'v0.5.3',
             'html_url': 'https://github.com/kaivyy/kabot/releases/tag/v0.5.3'
         }), \
         patch.object(tool, '_check_commits_behind', return_value=5):

        result = await tool.execute()
        assert 'install_method' in result
        assert 'git' in result
        assert '0.5.3' in result
        assert 'update_available' in result


@pytest.mark.asyncio
async def test_check_update_tool_pip_install():
    """Test CheckUpdateTool detects pip install."""
    tool = CheckUpdateTool()

    with patch.object(tool, '_detect_install_method', return_value='pip'), \
         patch.object(tool, '_get_current_version', return_value='0.5.2'), \
         patch.object(tool, '_fetch_github_release', new_callable=AsyncMock, return_value={
             'tag_name': 'v0.5.3',
             'html_url': 'https://github.com/kaivyy/kabot/releases/tag/v0.5.3'
         }):

        result = await tool.execute()
        assert 'pip' in result
        assert 'commits_behind' in result


@pytest.mark.asyncio
async def test_system_update_tool_dirty_tree():
    """Test SystemUpdateTool blocks update on dirty working tree."""
    tool = SystemUpdateTool()

    with patch.object(tool, '_detect_install_method', return_value='git'), \
         patch.object(tool, '_can_update_git', return_value=False):

        result = await tool.execute(confirm_restart=False)
        assert 'dirty_working_tree' in result
        assert 'success' in result


@pytest.mark.asyncio
async def test_system_update_tool_git_success():
    """Test SystemUpdateTool git update success."""
    tool = SystemUpdateTool()

    with patch.object(tool, '_detect_install_method', return_value='git'), \
         patch.object(tool, '_can_update_git', return_value=True), \
         patch.object(tool, '_get_current_version', side_effect=['0.5.2', '0.5.3']), \
         patch.object(tool, '_git_update', return_value=(True, 'Success')), \
         patch.object(tool, '_install_dependencies'):

        result = await tool.execute(confirm_restart=False)
        assert 'success' in result
        assert 'true' in result.lower()


def test_check_update_compare_versions_normalizes_v_prefix():
    tool = CheckUpdateTool()
    assert tool._compare_versions("0.5.9", "v0.5.9") is False
    assert tool._compare_versions("0.5.8", "v0.5.9") is True


@pytest.mark.asyncio
async def test_system_update_tool_includes_notify_message_for_user():
    tool = SystemUpdateTool()

    with patch.object(tool, "_detect_install_method", return_value="pip"), \
         patch.object(tool, "_fetch_latest_release", new_callable=AsyncMock, return_value=("v0.5.9", "https://example.com/release")), \
         patch.object(tool, "_get_current_version", side_effect=["0.5.8", "0.5.9"]), \
         patch.object(tool, "_pip_update", return_value=(True, "Pip update successful")), \
         patch.object(tool, "_install_dependencies"):

        result = await tool.execute(confirm_restart=False)
        payload = json.loads(result)
        assert payload["success"] is True
        assert payload["latest_version"] == "v0.5.9"
        assert payload["notify_user"] is True
        assert "0.5.9" in payload["notify_message"]


def test_read_installed_version_prefers_kabot_distribution_metadata():
    with patch.object(update_module.importlib_metadata, "version") as version_mock:
        version_mock.side_effect = ["0.5.9"]
        assert update_module._read_installed_version() == "0.5.9"
        version_mock.assert_called_once_with("kabot")


def test_read_installed_version_falls_back_to_legacy_distribution_name():
    def _version(name: str) -> str:
        if name == "kabot":
            raise update_module.importlib_metadata.PackageNotFoundError
        if name == "kabot-ai":
            return "0.5.9"
        raise AssertionError("unexpected package name")

    with patch.object(update_module.importlib_metadata, "version", side_effect=_version):
        assert update_module._read_installed_version() == "0.5.9"
