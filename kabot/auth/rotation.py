"""Auth key rotation for production reliability."""

import time
from typing import Optional
from loguru import logger


class AuthRotation:
    """
    Manages rotation of API keys for resilience.

    Automatically rotates to next available key on failures
    (rate limits, auth errors) and tracks cooldown periods.
    """

    def __init__(self, keys: list[str], cooldown_seconds: int = 300):
        """
        Initialize auth rotation.

        Args:
            keys: List of API keys to rotate through
            cooldown_seconds: Time before retrying failed keys (default: 5 min)
        """
        if not keys:
            raise ValueError("At least one API key required")

        self.keys = keys
        self.cooldown_seconds = cooldown_seconds
        self.current_index = 0
        self.failed_keys: dict[str, dict] = {}  # key -> {reason, timestamp}

    def current_key(self) -> str:
        """Get the current active API key."""
        return self.keys[self.current_index]

    def rotate(self) -> str:
        """
        Rotate to next available key.

        Returns:
            The new current key
        """
        # Reset expired failures first
        self.reset_expired_failures()

        # Try to find next non-failed key
        attempts = 0
        while attempts < len(self.keys):
            self.current_index = (self.current_index + 1) % len(self.keys)
            key = self.keys[self.current_index]

            if key not in self.failed_keys:
                logger.info(f"Rotated to key #{self.current_index + 1}")
                return key

            attempts += 1

        # All keys failed, return current as last resort
        logger.warning("All keys have failed, using current key as fallback")
        return self.keys[self.current_index]

    def mark_failed(self, key: str, reason: str) -> None:
        """
        Mark a key as failed.

        Args:
            key: The API key that failed
            reason: Failure reason (rate_limit, auth_error, etc.)
        """
        self.failed_keys[key] = {
            "reason": reason,
            "timestamp": time.time()
        }
        logger.warning(f"Marked key as failed: {reason}")

    def reset_expired_failures(self) -> None:
        """Reset keys that have passed their cooldown period."""
        now = time.time()
        expired = []

        for key, info in self.failed_keys.items():
            if now - info["timestamp"] > self.cooldown_seconds:
                expired.append(key)

        for key in expired:
            del self.failed_keys[key]
            logger.info(f"Reset failed key after cooldown")

    def get_status(self) -> dict:
        """Get rotation status for monitoring."""
        return {
            "total_keys": len(self.keys),
            "current_index": self.current_index,
            "failed_count": len(self.failed_keys),
            "available_count": len(self.keys) - len(self.failed_keys)
        }
