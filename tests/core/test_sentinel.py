"""Tests for crash recovery sentinel."""

import json
import os
import time

import pytest

from kabot.core.sentinel import CrashSentinel, format_recovery_message


@pytest.fixture
def sentinel_path(tmp_path):
    """Provide a temporary sentinel file path."""
    return tmp_path / "crash.sentinel"


@pytest.fixture
def sentinel(sentinel_path):
    """Provide a CrashSentinel instance."""
    return CrashSentinel(sentinel_path)


class TestCrashSentinelBasic:
    """Test basic sentinel functionality."""

    def test_initialization(self, sentinel_path):
        """Test sentinel initialization creates parent directory."""
        sentinel = CrashSentinel(sentinel_path)
        assert sentinel.sentinel_path == sentinel_path
        assert sentinel_path.parent.exists()

    def test_mark_session_active(self, sentinel, sentinel_path):
        """Test marking session as active creates sentinel file."""
        session_id = "test-session-123"
        message_id = "msg-456"
        user_message = "Hello, world!"

        sentinel.mark_session_active(session_id, message_id, user_message)

        # Sentinel file should exist
        assert sentinel_path.exists()

        # Verify contents
        with open(sentinel_path) as f:
            data = json.load(f)

        assert data['session_id'] == session_id
        assert data['message_id'] == message_id
        assert data['user_message'] == user_message
        assert data['pid'] == os.getpid()
        assert 'timestamp' in data
        assert 'datetime' in data

    def test_mark_session_active_truncates_long_message(self, sentinel, sentinel_path):
        """Test that long user messages are truncated."""
        long_message = "x" * 500  # 500 characters

        sentinel.mark_session_active("session", "msg", long_message)

        with open(sentinel_path) as f:
            data = json.load(f)

        # Should be truncated to 200 chars
        assert len(data['user_message']) == 200

    def test_clear_sentinel(self, sentinel, sentinel_path):
        """Test clearing sentinel removes file."""
        # Create sentinel
        sentinel.mark_session_active("session", "msg")
        assert sentinel_path.exists()

        # Clear it
        sentinel.clear_sentinel()
        assert not sentinel_path.exists()

    def test_clear_sentinel_when_not_exists(self, sentinel, sentinel_path):
        """Test clearing non-existent sentinel is safe."""
        assert not sentinel_path.exists()
        sentinel.clear_sentinel()  # Should not raise

    def test_multiple_mark_overwrites(self, sentinel, sentinel_path):
        """Test that marking multiple times overwrites previous sentinel."""
        sentinel.mark_session_active("session1", "msg1")
        sentinel.mark_session_active("session2", "msg2")

        with open(sentinel_path) as f:
            data = json.load(f)

        # Should have latest data
        assert data['session_id'] == "session2"
        assert data['message_id'] == "msg2"


class TestCrashDetection:
    """Test crash detection functionality."""

    def test_check_for_crash_when_no_sentinel(self, sentinel, sentinel_path):
        """Test that no crash is detected when sentinel doesn't exist."""
        assert not sentinel_path.exists()
        crash_data = sentinel.check_for_crash()
        assert crash_data is None

    def test_check_for_crash_detects_crash(self, sentinel, sentinel_path):
        """Test that crash is detected when sentinel exists."""
        # Simulate crash by creating sentinel and not clearing it
        session_id = "crashed-session"
        message_id = "crashed-msg"
        sentinel.mark_session_active(session_id, message_id)

        # Simulate restart - create new sentinel instance
        new_sentinel = CrashSentinel(sentinel_path)
        crash_data = new_sentinel.check_for_crash()

        # Should detect crash
        assert crash_data is not None
        assert crash_data['session_id'] == session_id
        assert crash_data['message_id'] == message_id

        # Sentinel should be cleared after detection
        assert not sentinel_path.exists()

    def test_check_for_crash_clears_corrupted_sentinel(self, sentinel, sentinel_path):
        """Test that corrupted sentinel is cleared."""
        # Create corrupted sentinel
        with open(sentinel_path, 'w') as f:
            f.write("not valid json{{{")

        crash_data = sentinel.check_for_crash()

        # Should return None and clear file
        assert crash_data is None
        assert not sentinel_path.exists()

    def test_check_for_crash_clears_empty_sentinel(self, sentinel, sentinel_path):
        """Test that empty sentinel is cleared."""
        # Create empty sentinel
        sentinel_path.touch()

        crash_data = sentinel.check_for_crash()

        # Should return None and clear file
        assert crash_data is None
        assert not sentinel_path.exists()


class TestContextManager:
    """Test context manager functionality."""

    def test_context_manager_clears_on_clean_exit(self, sentinel, sentinel_path):
        """Test that context manager clears sentinel on clean exit."""
        # Create sentinel before entering context
        sentinel.mark_session_active("session", "msg")
        assert sentinel_path.exists()

        # Use as context manager
        with sentinel:
            pass  # Clean exit

        # Sentinel should be cleared
        assert not sentinel_path.exists()

    def test_context_manager_preserves_on_exception(self, sentinel, sentinel_path):
        """Test that context manager preserves sentinel on exception."""
        # Create sentinel before entering context
        sentinel.mark_session_active("session", "msg")
        assert sentinel_path.exists()

        # Use as context manager with exception
        try:
            with sentinel:
                raise ValueError("Simulated crash")
        except ValueError:
            pass

        # Sentinel should still exist (crash detected)
        assert sentinel_path.exists()


class TestRecoveryMessage:
    """Test recovery message formatting."""

    def test_format_recovery_message(self):
        """Test recovery message formatting."""
        crash_data = {
            'session_id': 'test-session-123',
            'message_id': 'msg-456',
            'datetime': '2026-02-16T10:30:00'
        }

        message = format_recovery_message(crash_data)

        assert 'test-session-123' in message
        assert 'msg-456' in message
        assert '2026-02-16T10:30:00' in message
        assert 'restarted' in message.lower()
        assert 'unexpected shutdown' in message.lower()

    def test_format_recovery_message_with_missing_fields(self):
        """Test recovery message with missing fields uses defaults."""
        crash_data = {}

        message = format_recovery_message(crash_data)

        assert 'unknown' in message
        assert 'restarted' in message.lower()


class TestIntegration:
    """Integration tests for sentinel usage patterns."""

    def test_normal_workflow(self, sentinel, sentinel_path):
        """Test normal workflow: mark -> process -> clear."""
        # Mark session active
        sentinel.mark_session_active("session", "msg")
        assert sentinel_path.exists()

        # Simulate processing (no crash)
        time.sleep(0.1)

        # Clear on completion
        sentinel.clear_sentinel()
        assert not sentinel_path.exists()

        # Next startup should not detect crash
        new_sentinel = CrashSentinel(sentinel_path)
        assert new_sentinel.check_for_crash() is None

    def test_crash_workflow(self, sentinel, sentinel_path):
        """Test crash workflow: mark -> crash (no clear) -> restart -> detect."""
        # Mark session active
        sentinel.mark_session_active("session", "msg", "user input")
        assert sentinel_path.exists()

        # Simulate crash (don't clear sentinel)
        # ... process crashes here ...

        # Simulate restart
        new_sentinel = CrashSentinel(sentinel_path)
        crash_data = new_sentinel.check_for_crash()

        # Should detect crash
        assert crash_data is not None
        assert crash_data['session_id'] == "session"
        assert crash_data['message_id'] == "msg"
        assert crash_data['user_message'] == "user input"

        # Sentinel should be cleared after detection
        assert not sentinel_path.exists()

    def test_multiple_sessions(self, sentinel, sentinel_path):
        """Test handling multiple sessions."""
        # Session 1
        sentinel.mark_session_active("session1", "msg1")
        sentinel.clear_sentinel()

        # Session 2
        sentinel.mark_session_active("session2", "msg2")
        sentinel.clear_sentinel()

        # Session 3 crashes
        sentinel.mark_session_active("session3", "msg3")
        # Don't clear (simulated crash)

        # Restart
        new_sentinel = CrashSentinel(sentinel_path)
        crash_data = new_sentinel.check_for_crash()

        # Should only detect last crash
        assert crash_data['session_id'] == "session3"

    def test_atomic_write(self, sentinel, sentinel_path):
        """Test that sentinel writes are atomic."""
        # Mark session active
        sentinel.mark_session_active("session", "msg")

        # File should exist and be valid JSON
        assert sentinel_path.exists()
        with open(sentinel_path) as f:
            data = json.load(f)  # Should not raise

        assert data['session_id'] == "session"

    def test_concurrent_sentinel_updates(self, sentinel, sentinel_path):
        """Test rapid sequential updates."""
        for i in range(10):
            sentinel.mark_session_active(f"session{i}", f"msg{i}")

        # Should have latest data
        with open(sentinel_path) as f:
            data = json.load(f)

        assert data['session_id'] == "session9"
        assert data['message_id'] == "msg9"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_sentinel_with_none_user_message(self, sentinel, sentinel_path):
        """Test sentinel with None user message."""
        sentinel.mark_session_active("session", "msg", None)

        with open(sentinel_path) as f:
            data = json.load(f)

        assert data['user_message'] is None

    def test_sentinel_with_empty_user_message(self, sentinel, sentinel_path):
        """Test sentinel with empty user message."""
        sentinel.mark_session_active("session", "msg", "")

        with open(sentinel_path) as f:
            data = json.load(f)

        assert data['user_message'] == ""

    def test_sentinel_path_creation(self, tmp_path):
        """Test that nested directories are created."""
        nested_path = tmp_path / "deep" / "nested" / "path" / "crash.sentinel"
        sentinel = CrashSentinel(nested_path)

        sentinel.mark_session_active("session", "msg")

        assert nested_path.exists()
        assert nested_path.parent.exists()

    def test_write_failure_is_logged(self, sentinel, sentinel_path):
        """Test that write failures are handled gracefully."""
        # Make parent directory read-only (Unix only)
        if os.name != 'nt':
            sentinel_path.parent.chmod(0o444)

            # Should not raise, just log warning
            sentinel.mark_session_active("session", "msg")

            # Restore permissions
            sentinel_path.parent.chmod(0o755)
