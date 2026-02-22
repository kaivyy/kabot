"""
Crash recovery sentinel for seamless restart UX.

Pattern from OpenClaw: server-restart-sentinel.ts
Black box recorder that detects unclean shutdowns and provides recovery context.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from loguru import logger


class CrashSentinel:
    """
    Black box recorder for crash recovery.

    Writes a sentinel file before processing each message. If the process
    crashes, the sentinel file remains. On next startup, we detect the crash
    and can send a recovery message to the user.

    This provides seamless UX after unexpected shutdowns.
    """

    def __init__(self, sentinel_path: Path):
        """
        Initialize crash sentinel.

        Args:
            sentinel_path: Path to sentinel file (e.g., ~/.kabot/crash.sentinel)
        """
        self.sentinel_path = Path(sentinel_path)
        self.sentinel_path.parent.mkdir(parents=True, exist_ok=True)

    def mark_session_active(self, session_id: str, message_id: str,
                           user_message: Optional[str] = None) -> None:
        """
        Write sentinel file before processing message.

        This marks the session as "in progress". If the process crashes,
        this file will remain and we can detect it on next startup.

        Args:
            session_id: Current session ID
            message_id: Current message ID being processed
            user_message: Optional user message content for context
        """
        try:
            sentinel_data = {
                'session_id': session_id,
                'message_id': message_id,
                'timestamp': time.time(),
                'datetime': datetime.now().isoformat(),
                'pid': os.getpid(),
                'user_message': user_message[:200] if user_message is not None else None  # Truncate for safety
            }

            # Write atomically
            temp_path = self.sentinel_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(sentinel_data, f, indent=2)

            # Atomic rename
            if os.name == 'nt':  # Windows
                if self.sentinel_path.exists():
                    os.remove(self.sentinel_path)
            os.rename(temp_path, self.sentinel_path)

        except Exception as e:
            logger.warning(f"Failed to write crash sentinel: {e}")

    def clear_sentinel(self) -> None:
        """
        Remove sentinel on clean shutdown.

        This indicates the process exited cleanly and no crash occurred.
        """
        try:
            self.sentinel_path.unlink(missing_ok=True)
            logger.debug("Crash sentinel cleared (clean shutdown)")
        except Exception as e:
            logger.warning(f"Failed to clear crash sentinel: {e}")

    def check_for_crash(self) -> Optional[Dict[str, str]]:
        """
        On startup, check if previous session crashed.

        Returns:
            Dict with crash info if crash detected, None otherwise.
            Dict contains: session_id, message_id, timestamp, user_message
        """
        try:
            if not self.sentinel_path.exists():
                return None

            # Sentinel exists - previous session crashed
            with open(self.sentinel_path) as f:
                crash_data = json.load(f)

            logger.warning(
                f"Detected crash from previous session: "
                f"session={crash_data.get('session_id')}, "
                f"message={crash_data.get('message_id')}"
            )

            # Clear sentinel after reading
            self.clear_sentinel()

            return crash_data

        except Exception as e:
            logger.error(f"Error checking for crash: {e}")
            # Clear corrupted sentinel
            self.clear_sentinel()
            return None

    def __enter__(self):
        """Context manager entry - does nothing (sentinel written explicitly)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - clear sentinel on clean exit."""
        if exc_type is None:
            # Clean exit
            self.clear_sentinel()
        # If exception occurred, leave sentinel in place
        return False


# Recovery message template
RECOVERY_MESSAGE = """🔄 I just restarted after an unexpected shutdown.

**Last session**: {session_id}
**Last message**: {message_id}
**Time**: {datetime}

I'm back online and ready to continue. What were we working on?"""


def format_recovery_message(crash_data: Dict[str, str]) -> str:
    """
    Format recovery message from crash data.

    Args:
        crash_data: Crash information from sentinel

    Returns:
        Formatted recovery message
    """
    return RECOVERY_MESSAGE.format(
        session_id=crash_data.get('session_id', 'unknown'),
        message_id=crash_data.get('message_id', 'unknown'),
        datetime=crash_data.get('datetime', 'unknown')
    )
