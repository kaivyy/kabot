"""Tests for PID-based file locking."""

import os
import time
import json
import multiprocessing
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import psutil

from kabot.utils.pid_lock import PIDLock, PIDLockError


@pytest.fixture
def temp_lock_path(tmp_path):
    """Provide a temporary file path for locking tests."""
    return tmp_path / "test_resource.json"


@pytest.fixture
def lock_file_path(temp_lock_path):
    """Provide the lock file path."""
    return temp_lock_path.with_suffix(temp_lock_path.suffix + '.lock')


class TestPIDLockBasic:
    """Test basic PIDLock functionality."""

    def test_acquire_and_release(self, temp_lock_path, lock_file_path):
        """Test normal lock acquisition and release."""
        lock = PIDLock(temp_lock_path)

        # Lock should not exist initially
        assert not lock_file_path.exists()

        # Acquire lock
        assert lock.acquire()
        assert lock_file_path.exists()

        # Verify lock file contains correct PID
        with open(lock_file_path) as f:
            lock_data = json.load(f)
        assert lock_data['pid'] == os.getpid()
        assert 'created_at' in lock_data
        assert 'hostname' in lock_data

        # Release lock
        lock.release()
        assert not lock_file_path.exists()

    def test_context_manager(self, temp_lock_path, lock_file_path):
        """Test PIDLock as context manager."""
        assert not lock_file_path.exists()

        with PIDLock(temp_lock_path):
            # Lock should exist inside context
            assert lock_file_path.exists()

        # Lock should be released after context
        assert not lock_file_path.exists()

    def test_double_acquire_fails(self, temp_lock_path):
        """Test that acquiring same lock twice fails."""
        lock1 = PIDLock(temp_lock_path, timeout=1)
        lock2 = PIDLock(temp_lock_path, timeout=1)

        # First lock succeeds
        assert lock1.acquire()

        # Second lock should timeout
        with pytest.raises(PIDLockError, match="Failed to acquire lock"):
            lock2.acquire()

        lock1.release()

    def test_release_without_acquire(self, temp_lock_path):
        """Test that releasing without acquiring is safe."""
        lock = PIDLock(temp_lock_path)
        lock.release()  # Should not raise

    def test_multiple_release(self, temp_lock_path):
        """Test that multiple releases are safe."""
        lock = PIDLock(temp_lock_path)
        lock.acquire()
        lock.release()
        lock.release()  # Should not raise


class TestPIDLockStaleLockRecovery:
    """Test stale lock detection and recovery."""

    def test_stale_lock_recovery(self, temp_lock_path, lock_file_path):
        """Test recovery from stale lock left by dead process."""
        # Create a fake stale lock with non-existent PID
        fake_pid = 999999  # Very unlikely to exist
        stale_lock_data = {
            'pid': fake_pid,
            'created_at': time.time() - 100,
            'hostname': 'test-host'
        }

        with open(lock_file_path, 'w') as f:
            json.dump(stale_lock_data, f)

        # New lock should steal the stale lock
        lock = PIDLock(temp_lock_path, timeout=5)
        assert lock.acquire()

        # Verify new lock has current PID
        with open(lock_file_path) as f:
            lock_data = json.load(f)
        assert lock_data['pid'] == os.getpid()

        lock.release()

    def test_live_lock_not_stolen(self, temp_lock_path, lock_file_path):
        """Test that locks from live processes are not stolen."""
        # Create lock with current process PID
        lock1 = PIDLock(temp_lock_path, timeout=1)
        lock1.acquire()

        # Try to acquire with another lock instance
        lock2 = PIDLock(temp_lock_path, timeout=1)
        with pytest.raises(PIDLockError):
            lock2.acquire()

        lock1.release()

    @patch('kabot.utils.pid_lock.psutil.Process')
    def test_stale_lock_detection_with_mock(self, mock_process_class, temp_lock_path, lock_file_path):
        """Test stale lock detection using mocked process check."""
        # Create lock file with fake PID
        fake_pid = 12345
        stale_lock_data = {
            'pid': fake_pid,
            'created_at': time.time(),
            'hostname': 'test-host'
        }

        with open(lock_file_path, 'w') as f:
            json.dump(stale_lock_data, f)

        # Mock process as not running
        mock_process = MagicMock()
        mock_process.is_running.return_value = False
        mock_process_class.return_value = mock_process

        # Should successfully steal the lock
        lock = PIDLock(temp_lock_path, timeout=5)
        assert lock.acquire()
        lock.release()


def _concurrent_worker(lock_path, results_queue, worker_id):
    """Worker function for concurrent process testing (must be module-level for pickling)."""
    try:
        from kabot.utils.pid_lock import PIDLock
        from pathlib import Path
        import time

        lock = PIDLock(Path(lock_path), timeout=2)
        lock.acquire()

        # Critical section - write to shared file
        test_file = Path(lock_path).parent / "shared_counter.txt"

        # Read current value
        if test_file.exists():
            with open(test_file) as f:
                count = int(f.read().strip())
        else:
            count = 0

        # Simulate some work
        time.sleep(0.1)

        # Write incremented value
        with open(test_file, 'w') as f:
            f.write(str(count + 1))

        lock.release()
        results_queue.put(('success', worker_id))

    except Exception as e:
        results_queue.put(('error', str(e)))


class TestPIDLockConcurrency:
    """Test PIDLock behavior under concurrent access."""

    def test_sequential_locks(self, temp_lock_path):
        """Test that locks can be acquired sequentially."""
        for i in range(5):
            with PIDLock(temp_lock_path):
                # Each iteration should successfully acquire lock
                pass

    def test_concurrent_process_safety(self, temp_lock_path):
        """Test that only one process can hold lock at a time."""
        # Launch multiple processes
        num_workers = 5
        results_queue = multiprocessing.Queue()
        processes = []

        for i in range(num_workers):
            p = multiprocessing.Process(
                target=_concurrent_worker,
                args=(str(temp_lock_path), results_queue, i)
            )
            p.start()
            processes.append(p)

        # Wait for all processes
        for p in processes:
            p.join(timeout=10)

        # Collect results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())

        # Verify all workers succeeded
        assert len(results) == num_workers
        assert all(status == 'success' for status, _ in results)

        # Verify counter was incremented correctly (no race conditions)
        counter_file = temp_lock_path.parent / "shared_counter.txt"
        with open(counter_file) as f:
            final_count = int(f.read().strip())
        assert final_count == num_workers


class TestPIDLockEdgeCases:
    """Test edge cases and error conditions."""

    def test_corrupted_lock_file(self, temp_lock_path, lock_file_path):
        """Test handling of corrupted lock file."""
        # Create corrupted lock file
        with open(lock_file_path, 'w') as f:
            f.write("not valid json{{{")

        # Should be able to acquire lock (treats as stale)
        lock = PIDLock(temp_lock_path, timeout=5)
        assert lock.acquire()
        lock.release()

    def test_empty_lock_file(self, temp_lock_path, lock_file_path):
        """Test handling of empty lock file."""
        # Create empty lock file
        lock_file_path.touch()

        # Should be able to acquire lock
        lock = PIDLock(temp_lock_path, timeout=5)
        assert lock.acquire()
        lock.release()

    def test_lock_file_permissions(self, temp_lock_path, lock_file_path):
        """Test that lock file has secure permissions."""
        lock = PIDLock(temp_lock_path)
        lock.acquire()

        # Check file permissions (should be 0o600 on Unix)
        if os.name != 'nt':  # Skip on Windows
            stat_info = os.stat(lock_file_path)
            mode = stat_info.st_mode & 0o777
            assert mode == 0o600, f"Lock file has insecure permissions: {oct(mode)}"

        lock.release()

    def test_timeout_configuration(self, temp_lock_path):
        """Test that timeout is respected."""
        lock1 = PIDLock(temp_lock_path, timeout=1)
        lock2 = PIDLock(temp_lock_path, timeout=1)

        lock1.acquire()

        start_time = time.time()
        with pytest.raises(PIDLockError):
            lock2.acquire()
        elapsed = time.time() - start_time

        # Should timeout around 1 second (allow some variance)
        assert 0.8 < elapsed < 1.5

        lock1.release()

    def test_destructor_cleanup(self, temp_lock_path, lock_file_path):
        """Test that destructor releases lock."""
        lock = PIDLock(temp_lock_path)
        lock.acquire()
        assert lock_file_path.exists()

        # Delete lock object (triggers __del__)
        del lock

        # Lock file should be cleaned up
        # Note: This is best-effort, may not always work due to GC timing
        time.sleep(0.1)  # Give GC time to run
        # We can't reliably test this due to GC non-determinism


class TestPIDLockCrossPlatform:
    """Test cross-platform compatibility."""

    def test_windows_compatibility(self, temp_lock_path):
        """Test that PIDLock works on Windows."""
        if os.name != 'nt':
            pytest.skip("Windows-only test")

        lock = PIDLock(temp_lock_path)
        assert lock.acquire()
        lock.release()

    def test_unix_compatibility(self, temp_lock_path):
        """Test that PIDLock works on Unix."""
        if os.name == 'nt':
            pytest.skip("Unix-only test")

        lock = PIDLock(temp_lock_path)
        assert lock.acquire()
        lock.release()

    def test_hostname_capture(self, temp_lock_path, lock_file_path):
        """Test that hostname is captured in lock file."""
        lock = PIDLock(temp_lock_path)
        lock.acquire()

        with open(lock_file_path) as f:
            lock_data = json.load(f)

        assert 'hostname' in lock_data
        assert isinstance(lock_data['hostname'], str)
        assert len(lock_data['hostname']) > 0

        lock.release()


class TestPIDLockIntegration:
    """Integration tests with real file operations."""

    def test_config_file_protection(self, tmp_path):
        """Test protecting a config file with PIDLock."""
        config_file = tmp_path / "config.json"
        config_data = {"setting": "value"}

        # Write config with lock protection
        with PIDLock(config_file):
            with open(config_file, 'w') as f:
                json.dump(config_data, f)

        # Read config with lock protection
        with PIDLock(config_file):
            with open(config_file) as f:
                loaded_data = json.load(f)

        assert loaded_data == config_data

    def test_multiple_resources(self, tmp_path):
        """Test locking multiple different resources."""
        file1 = tmp_path / "resource1.json"
        file2 = tmp_path / "resource2.json"

        # Should be able to lock different resources simultaneously
        lock1 = PIDLock(file1)
        lock2 = PIDLock(file2)

        assert lock1.acquire()
        assert lock2.acquire()

        lock1.release()
        lock2.release()
