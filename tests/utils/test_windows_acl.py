"""Tests for Windows ACL security checker."""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from kabot.utils.windows_acl import WindowsACL


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for testing."""
    return tmp_path


@pytest.fixture
def temp_file(tmp_path):
    """Provide a temporary file for testing."""
    test_file = tmp_path / "test_file.txt"
    test_file.write_text("test content")
    return test_file


class TestWindowsACLBasic:
    """Test basic Windows ACL functionality."""

    def test_check_directory_permissions_on_non_windows(self, temp_dir):
        """Test that checks return empty on non-Windows."""
        if os.name == 'nt':
            pytest.skip("Windows-only test")

        findings = WindowsACL.check_directory_permissions(temp_dir)
        assert findings == []

    def test_check_directory_permissions_nonexistent(self, tmp_path):
        """Test checking non-existent directory."""
        if os.name != 'nt':
            pytest.skip("Windows-only test")

        nonexistent = tmp_path / "does_not_exist"
        findings = WindowsACL.check_directory_permissions(nonexistent)
        assert findings == []

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")
    def test_check_directory_permissions_exists(self, temp_dir):
        """Test checking existing directory on Windows."""
        findings = WindowsACL.check_directory_permissions(temp_dir)
        # Should return a list (may be empty if permissions are secure)
        assert isinstance(findings, list)

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")
    def test_is_running_as_admin(self):
        """Test admin detection."""
        result = WindowsACL.is_running_as_admin()
        assert isinstance(result, bool)


class TestWindowsACLParsing:
    """Test ACL parsing functionality."""

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")
    def test_get_acl_info_valid_path(self, temp_dir):
        """Test getting ACL info for valid path."""
        acl_info = WindowsACL.get_acl_info(temp_dir)

        if acl_info:  # May be None if icacls fails
            assert 'path' in acl_info
            assert 'entries' in acl_info
            assert isinstance(acl_info['entries'], list)

    def test_get_acl_info_on_non_windows(self, temp_dir):
        """Test that get_acl_info returns None on non-Windows."""
        if os.name == 'nt':
            pytest.skip("Non-Windows test")

        acl_info = WindowsACL.get_acl_info(temp_dir)
        assert acl_info is None

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")
    def test_get_acl_info_nonexistent_path(self, tmp_path):
        """Test getting ACL info for non-existent path."""
        nonexistent = tmp_path / "does_not_exist"
        acl_info = WindowsACL.get_acl_info(nonexistent)
        # Should return None for non-existent paths
        assert acl_info is None

    @patch('subprocess.run')
    def test_get_acl_info_timeout(self, mock_run, temp_dir):
        """Test handling of icacls timeout."""
        if os.name != 'nt':
            pytest.skip("Windows-only test")

        mock_run.side_effect = subprocess.TimeoutExpired('icacls', 5)
        acl_info = WindowsACL.get_acl_info(temp_dir)
        assert acl_info is None

    @patch('subprocess.run')
    def test_get_acl_info_command_failure(self, mock_run, temp_dir):
        """Test handling of icacls command failure."""
        if os.name != 'nt':
            pytest.skip("Windows-only test")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        acl_info = WindowsACL.get_acl_info(temp_dir)
        assert acl_info is None


class TestWorldWritableDetection:
    """Test world-writable detection."""

    def test_is_world_writable_on_non_windows(self, temp_dir):
        """Test that is_world_writable returns False on non-Windows."""
        if os.name == 'nt':
            pytest.skip("Non-Windows test")

        result = WindowsACL.is_world_writable(temp_dir)
        assert result is False

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")
    def test_is_world_writable_secure_path(self, temp_dir):
        """Test world-writable check on secure path."""
        # Most temp directories should be secure
        result = WindowsACL.is_world_writable(temp_dir)
        assert isinstance(result, bool)

    @patch.object(WindowsACL, 'get_acl_info')
    def test_is_world_writable_with_everyone_full_control(self, mock_get_acl, temp_dir):
        """Test detection of Everyone with full control."""
        if os.name != 'nt':
            pytest.skip("Windows-only test")

        # Mock ACL with Everyone having full control
        mock_get_acl.return_value = {
            'path': str(temp_dir),
            'entries': [
                {
                    'principal': 'Everyone',
                    'permissions': ['F'],  # Full control
                    'inheritance': ''
                }
            ]
        }

        result = WindowsACL.is_world_writable(temp_dir)
        assert result is True

    @patch.object(WindowsACL, 'get_acl_info')
    def test_is_world_writable_with_users_modify(self, mock_get_acl, temp_dir):
        """Test detection of Users with modify permissions."""
        if os.name != 'nt':
            pytest.skip("Windows-only test")

        mock_get_acl.return_value = {
            'path': str(temp_dir),
            'entries': [
                {
                    'principal': 'BUILTIN\\Users',
                    'permissions': ['M'],  # Modify
                    'inheritance': ''
                }
            ]
        }

        result = WindowsACL.is_world_writable(temp_dir)
        assert result is True

    @patch.object(WindowsACL, 'get_acl_info')
    def test_is_world_writable_with_users_read_only(self, mock_get_acl, temp_dir):
        """Test that read-only permissions are not flagged as writable."""
        if os.name != 'nt':
            pytest.skip("Windows-only test")

        mock_get_acl.return_value = {
            'path': str(temp_dir),
            'entries': [
                {
                    'principal': 'BUILTIN\\Users',
                    'permissions': ['R'],  # Read only
                    'inheritance': ''
                }
            ]
        }

        result = WindowsACL.is_world_writable(temp_dir)
        assert result is False

    @patch.object(WindowsACL, 'get_acl_info')
    def test_is_world_writable_with_specific_user(self, mock_get_acl, temp_dir):
        """Test that specific user permissions are not flagged."""
        if os.name != 'nt':
            pytest.skip("Windows-only test")

        mock_get_acl.return_value = {
            'path': str(temp_dir),
            'entries': [
                {
                    'principal': 'DOMAIN\\SpecificUser',
                    'permissions': ['F'],
                    'inheritance': ''
                }
            ]
        }

        result = WindowsACL.is_world_writable(temp_dir)
        assert result is False


class TestWorldReadableDetection:
    """Test world-readable detection."""

    def test_is_world_readable_on_non_windows(self, temp_file):
        """Test that is_world_readable returns False on non-Windows."""
        if os.name == 'nt':
            pytest.skip("Non-Windows test")

        result = WindowsACL.is_world_readable(temp_file)
        assert result is False

    @patch.object(WindowsACL, 'get_acl_info')
    def test_is_world_readable_with_everyone_read(self, mock_get_acl, temp_file):
        """Test detection of Everyone with read permissions."""
        if os.name != 'nt':
            pytest.skip("Windows-only test")

        mock_get_acl.return_value = {
            'path': str(temp_file),
            'entries': [
                {
                    'principal': 'Everyone',
                    'permissions': ['R'],
                    'inheritance': ''
                }
            ]
        }

        result = WindowsACL.is_world_readable(temp_file)
        assert result is True

    @patch.object(WindowsACL, 'get_acl_info')
    def test_is_world_readable_with_users_rx(self, mock_get_acl, temp_file):
        """Test detection of Users with read & execute."""
        if os.name != 'nt':
            pytest.skip("Windows-only test")

        mock_get_acl.return_value = {
            'path': str(temp_file),
            'entries': [
                {
                    'principal': 'Users',
                    'permissions': ['RX'],
                    'inheritance': ''
                }
            ]
        }

        result = WindowsACL.is_world_readable(temp_file)
        assert result is True


class TestFilePermissionChecks:
    """Test file permission checking."""

    def test_check_file_permissions_on_non_windows(self, temp_file):
        """Test that file checks return empty on non-Windows."""
        if os.name == 'nt':
            pytest.skip("Non-Windows test")

        findings = WindowsACL.check_file_permissions(temp_file)
        assert findings == []

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")
    def test_check_file_permissions_nonexistent(self, tmp_path):
        """Test checking non-existent file."""
        nonexistent = tmp_path / "does_not_exist.txt"
        findings = WindowsACL.check_file_permissions(nonexistent)
        assert findings == []

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")
    def test_check_file_permissions_regular_file(self, temp_file):
        """Test checking regular file."""
        findings = WindowsACL.check_file_permissions(temp_file)
        assert isinstance(findings, list)

    def test_is_sensitive_file(self):
        """Test sensitive file detection."""
        assert WindowsACL._is_sensitive_file(Path("config.json"))
        assert WindowsACL._is_sensitive_file(Path(".env"))
        assert WindowsACL._is_sensitive_file(Path("credentials.txt"))
        assert WindowsACL._is_sensitive_file(Path("secret_key.txt"))
        assert WindowsACL._is_sensitive_file(Path("database.db"))
        assert WindowsACL._is_sensitive_file(Path("data.sqlite"))

        assert not WindowsACL._is_sensitive_file(Path("readme.md"))
        assert not WindowsACL._is_sensitive_file(Path("main.py"))
        assert not WindowsACL._is_sensitive_file(Path("test.txt"))


class TestIntegration:
    """Integration tests for Windows ACL checks."""

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")
    def test_full_directory_check(self, temp_dir):
        """Test full directory permission check."""
        # Create some test files
        (temp_dir / "config.json").write_text('{"test": true}')
        (temp_dir / "readme.md").write_text("# Test")

        findings = WindowsACL.check_directory_permissions(temp_dir)
        assert isinstance(findings, list)

        # Check finding structure if any findings exist
        for finding in findings:
            assert 'type' in finding
            assert 'severity' in finding
            assert 'item' in finding
            assert 'file' in finding
            assert 'detail' in finding

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")
    def test_sensitive_file_check(self, temp_dir):
        """Test sensitive file permission check."""
        sensitive_file = temp_dir / "config.json"
        sensitive_file.write_text('{"api_key": "secret"}')

        findings = WindowsACL.check_file_permissions(sensitive_file)
        assert isinstance(findings, list)


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch.object(WindowsACL, 'get_acl_info')
    def test_is_world_writable_with_none_acl(self, mock_get_acl, temp_dir):
        """Test handling when get_acl_info returns None."""
        if os.name != 'nt':
            pytest.skip("Windows-only test")

        mock_get_acl.return_value = None
        result = WindowsACL.is_world_writable(temp_dir)
        assert result is False

    @patch.object(WindowsACL, 'get_acl_info')
    def test_is_world_writable_with_empty_entries(self, mock_get_acl, temp_dir):
        """Test handling of empty ACL entries."""
        if os.name != 'nt':
            pytest.skip("Windows-only test")

        mock_get_acl.return_value = {
            'path': str(temp_dir),
            'entries': []
        }

        result = WindowsACL.is_world_writable(temp_dir)
        assert result is False

    @patch.object(WindowsACL, 'get_acl_info')
    def test_is_world_writable_with_malformed_entry(self, mock_get_acl, temp_dir):
        """Test handling of malformed ACL entry."""
        if os.name != 'nt':
            pytest.skip("Windows-only test")

        mock_get_acl.return_value = {
            'path': str(temp_dir),
            'entries': [
                {
                    # Missing 'principal' key
                    'permissions': ['F']
                }
            ]
        }

        result = WindowsACL.is_world_writable(temp_dir)
        assert result is False

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")
    def test_check_directory_permissions_with_exception(self, temp_dir):
        """Test graceful handling of exceptions."""
        with patch.object(WindowsACL, 'is_world_writable', side_effect=Exception("Test error")):
            findings = WindowsACL.check_directory_permissions(temp_dir)
            # Should return empty list on exception
            assert findings == []
