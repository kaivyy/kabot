"""
PID-based file locking with stale lock recovery.

Pattern from OpenClaw: agents/session-write-lock.ts
Prevents race conditions in multi-process scenarios.
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

import psutil


class PIDLockError(Exception):
    """Raised when lock acquisition fails."""
    pass


class PIDLock:
    """
    File-based process locking with stale lock recovery.

    Ensures only one process can access a resource at a time.
    Automatically recovers from stale locks left by crashed processes.

    Usage:
        lock = PIDLock(Path("config.json"))
        if lock.acquire():
            try:
                # Critical section
                pass
            finally:
                lock.release()

    Or use as context manager:
        with PIDLock(Path("config.json")):
            # Critical section
            pass
    """

    def __init__(self, lock_path: Path, timeout: int = 30):
        """
        Initialize PID lock.

        Args:
            lock_path: Path to the resource being locked
            timeout: Maximum seconds to wait for lock acquisition
        """
        self.lock_path = Path(lock_path)
        self.lock_file = self.lock_path.with_suffix(self.lock_path.suffix + '.lock')
        self.timeout = timeout
        self.pid = os.getpid()
        self._acquired = False

    def acquire(self) -> bool:
        """
        Acquire lock, stealing from dead processes if needed.

        Returns:
            True if lock acquired successfully

        Raises:
            PIDLockError: If lock cannot be acquired within timeout
        """
        start_time = time.time()

        while time.time() - start_time < self.timeout:
            # Try to acquire lock
            if self._try_acquire():
                self._acquired = True
                return True

            # Lock exists, check if it's valid and process is alive
            lock_data = self._read_lock_file()

            # If lock file is corrupted/empty (None), treat as stale
            if lock_data is None:
                self._steal_lock(None)
                if self._try_acquire():
                    self._acquired = True
                    return True
            elif lock_data:
                lock_pid = lock_data.get('pid')
                if lock_pid and not self._is_process_alive(lock_pid):
                    # Stale lock detected, steal it
                    self._steal_lock(lock_pid)
                    if self._try_acquire():
                        self._acquired = True
                        return True

            # Wait before retry
            time.sleep(0.1)

        raise PIDLockError(
            f"Failed to acquire lock for {self.lock_path} within {self.timeout}s"
        )

    def release(self) -> None:
        """Release lock and clean up lock file."""
        if not self._acquired:
            return

        try:
            # Verify we still own the lock before releasing
            lock_data = self._read_lock_file()
            if lock_data and lock_data.get('pid') == self.pid:
                self.lock_file.unlink(missing_ok=True)
            self._acquired = False
        except Exception:
            # Best effort cleanup
            pass

    def _try_acquire(self) -> bool:
        """
        Attempt to create lock file atomically.

        Returns:
            True if lock file created successfully
        """
        try:
            # Use exclusive creation flag (fails if file exists)
            fd = os.open(
                self.lock_file,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600
            )

            lock_data = {
                'pid': self.pid,
                'created_at': time.time(),
                'hostname': os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', 'unknown'))
            }

            os.write(fd, json.dumps(lock_data).encode('utf-8'))
            os.close(fd)
            return True

        except FileExistsError:
            return False
        except Exception:
            return False

    def _read_lock_file(self) -> Optional[dict]:
        """
        Read lock file contents.

        Returns:
            Lock data dict or None if file doesn't exist/invalid
        """
        try:
            if not self.lock_file.exists():
                return None

            with open(self.lock_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None

    def _is_process_alive(self, pid: int) -> bool:
        """
        Check if process is still running (cross-platform).

        Args:
            pid: Process ID to check

        Returns:
            True if process is alive
        """
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def _steal_lock(self, old_pid: int) -> None:
        """
        Remove stale lock file from dead process.

        Args:
            old_pid: PID of the dead process
        """
        try:
            self.lock_file.unlink(missing_ok=True)
        except Exception:
            pass

    def __enter__(self):
        """Context manager entry."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
        return False

    def __del__(self):
        """Cleanup on garbage collection."""
        if self._acquired:
            self.release()
