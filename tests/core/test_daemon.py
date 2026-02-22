"""Tests for multi-platform daemon support (Phase 12 - Task 37)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from kabot.core.daemon import (
    generate_launchagent_plist,
    generate_systemd_unit,
    get_service_status,
    install_launchd_service,
    install_systemd_service,
)


def test_generate_systemd_unit():
    """Test systemd unit file generation."""
    unit = generate_systemd_unit(
        user="testuser",
        workdir="/home/testuser/kabot"
    )

    assert "[Unit]" in unit
    assert "[Service]" in unit
    assert "[Install]" in unit
    assert "User=testuser" in unit
    assert "WorkingDirectory=/home/testuser/kabot" in unit
    assert "ExecStart=/home/testuser/kabot/venv/bin/python -m kabot.cli start" in unit
    assert "Restart=always" in unit


def test_generate_systemd_unit_custom_python():
    """Test systemd unit with custom Python path."""
    unit = generate_systemd_unit(
        user="testuser",
        workdir="/opt/kabot",
        python_path="/usr/bin/python3"
    )

    assert "ExecStart=/usr/bin/python3 -m kabot.cli start" in unit


def test_generate_launchagent_plist():
    """Test launchd plist file generation."""
    plist = generate_launchagent_plist(
        label="com.test.kabot",
        workdir="/Users/test/kabot"
    )

    assert '<?xml version="1.0"' in plist
    assert "<plist version=\"1.0\">" in plist
    assert "<key>Label</key>" in plist
    assert "<string>com.test.kabot</string>" in plist
    assert "<key>WorkingDirectory</key>" in plist
    assert "<string>/Users/test/kabot</string>" in plist
    assert "<key>RunAtLoad</key>" in plist
    assert "<key>KeepAlive</key>" in plist


def test_generate_launchagent_plist_custom_python():
    """Test launchd plist with custom Python path."""
    plist = generate_launchagent_plist(
        label="com.test.kabot",
        workdir="/opt/kabot",
        python_path="/usr/local/bin/python3"
    )

    assert "<string>/usr/local/bin/python3</string>" in plist


def test_install_systemd_service_not_linux():
    """Test systemd installation fails on non-Linux."""
    with patch('sys.platform', 'darwin'):
        success, message = install_systemd_service()
        assert success is False
        assert "only available on Linux" in message


def test_install_systemd_service_success():
    """Test successful systemd service installation."""
    with patch('sys.platform', 'linux'):
        with patch('os.getenv', return_value='testuser'):
            with patch('os.getcwd', return_value='/home/testuser/kabot'):
                mock_path = MagicMock(spec=Path)
                mock_path.write_text = MagicMock()

                with patch('kabot.core.daemon.Path') as mock_path_class:
                    mock_path_class.home.return_value.__truediv__.return_value.__truediv__.return_value.__truediv__.return_value.__truediv__.return_value = mock_path
                    mock_path.__truediv__.return_value = mock_path

                    success, message = install_systemd_service()
                    assert success is True
                    assert "Service file created" in message
                    assert "systemctl --user enable" in message


def test_install_launchd_service_not_macos():
    """Test launchd installation fails on non-macOS."""
    with patch('sys.platform', 'linux'):
        success, message = install_launchd_service()
        assert success is False
        assert "only available on macOS" in message


def test_install_launchd_service_success():
    """Test successful launchd service installation."""
    with patch('sys.platform', 'darwin'):
        with patch('os.getcwd', return_value='/Users/test/kabot'):
            mock_path = MagicMock(spec=Path)
            mock_path.write_text = MagicMock()

            with patch('kabot.core.daemon.Path') as mock_path_class:
                mock_path_class.home.return_value.__truediv__.return_value.__truediv__.return_value = mock_path
                mock_path.__truediv__.return_value = mock_path

                success, message = install_launchd_service()
                assert success is True
                assert "Service file created" in message
                assert "launchctl load" in message


def test_get_service_status_linux():
    """Test service status on Linux."""
    with patch('sys.platform', 'linux'):
        with patch('pathlib.Path.exists', return_value=False):
            status = get_service_status()
            assert status["platform"] == "linux"
            assert status["service_available"] is True
            assert status["service_type"] == "systemd"
            assert status["installed"] is False


def test_get_service_status_macos():
    """Test service status on macOS."""
    with patch('sys.platform', 'darwin'):
        with patch('pathlib.Path.exists', return_value=True):
            status = get_service_status()
            assert status["platform"] == "darwin"
            assert status["service_available"] is True
            assert status["service_type"] == "launchd"
            assert status["installed"] is True
