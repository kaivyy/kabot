import pytest
from unittest.mock import Mock, patch, AsyncMock
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
