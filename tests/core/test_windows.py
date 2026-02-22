"""Tests for Windows native integration (Phase 12 - Task 36)."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from kabot.core.windows import clip_copy, get_windows_info, wsl_detect


def test_wsl_detect_not_linux():
    """Test WSL detection on non-Linux platforms."""
    with patch('sys.platform', 'win32'):
        result = wsl_detect()
        assert result["is_wsl"] is False
        assert result["version"] is None


def test_wsl_detect_no_proc_version():
    """Test WSL detection when /proc/version doesn't exist."""
    with patch('sys.platform', 'linux'):
        with patch('os.path.exists', return_value=False):
            result = wsl_detect()
            assert result["is_wsl"] is False
            assert result["version"] is None


def test_wsl_detect_wsl1():
    """Test WSL1 detection."""
    with patch('sys.platform', 'linux'):
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', MagicMock(return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock(
                    read=MagicMock(return_value="Linux version 4.4.0-19041-Microsoft")
                ))
            ))):
                result = wsl_detect()
                assert result["is_wsl"] is True
                assert result["version"] == 1


def test_wsl_detect_wsl2():
    """Test WSL2 detection."""
    with patch('sys.platform', 'linux'):
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', MagicMock(return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock(
                    read=MagicMock(return_value="Linux version 5.10.16.3-microsoft-standard-WSL2")
                ))
            ))):
                result = wsl_detect()
                assert result["is_wsl"] is True
                assert result["version"] == 2


def test_clip_copy_not_windows():
    """Test clipboard copy on non-Windows platforms."""
    with patch('sys.platform', 'darwin'):
        with patch('kabot.core.windows.wsl_detect', return_value={"is_wsl": False}):
            result = clip_copy("test text")
            assert result is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
def test_clip_copy_windows():
    """Test clipboard copy on Windows."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = clip_copy("test text")
        assert result is True
        mock_run.assert_called_once()


def test_clip_copy_wsl():
    """Test clipboard copy in WSL."""
    with patch('sys.platform', 'linux'):
        with patch('kabot.core.windows.wsl_detect', return_value={"is_wsl": True, "version": 2}):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = clip_copy("test text")
                assert result is True
                mock_run.assert_called_once()


def test_clip_copy_failure():
    """Test clipboard copy failure handling."""
    with patch('sys.platform', 'win32'):
        with patch('subprocess.run', side_effect=Exception("Failed")):
            result = clip_copy("test text")
            assert result is False


def test_get_windows_info():
    """Test getting Windows environment information."""
    info = get_windows_info()
    assert "platform" in info
    assert "wsl" in info
    assert info["platform"] == sys.platform
