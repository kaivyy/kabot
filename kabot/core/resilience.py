"""
Resilience Layer for Kabot (Phase 9).

Implements automatic API key rotation and model fallback logic
to achieve zero-downtime during API errors, quota limits, or outages.
"""

import asyncio
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class KeyRotator:
    """
    Manages multiple API keys per provider and rotates on failure.

    When an API call returns 429 (rate limit) or 401 (auth error),
    automatically switches to the next available key.
    """

    def __init__(self, keys: list[str] | None = None):
        """
        Args:
            keys: List of API keys. Can be a single key (no rotation)
                  or multiple keys for round-robin rotation.
        """
        self._keys = keys or []
        self._current_index = 0
        self._failed_keys: dict[int, float] = {}  # index → cooldown_until timestamp
        self._cooldown_seconds = 60  # How long to wait before retrying a failed key

    @property
    def current_key(self) -> str | None:
        """Get the currently active API key."""
        if not self._keys:
            return None
        
        # Try current key
        key = self._keys[self._current_index]
        
        # If current key is on cooldown, find the next available one
        if self._current_index in self._failed_keys:
            cooldown_until = self._failed_keys[self._current_index]
            if time.time() < cooldown_until:
                next_key = self._find_available_key()
                if next_key is not None:
                    return self._keys[next_key]
            else:
                # Cooldown expired, remove from failed
                del self._failed_keys[self._current_index]
        
        return key

    def add_key(self, key: str) -> None:
        """Add a new API key to the rotation pool."""
        if key and key not in self._keys:
            self._keys.append(key)
            logger.info(f"Added API key to rotation pool (total: {len(self._keys)})")

    def rotate(self, error_code: int | None = None) -> str | None:
        """
        Rotate to the next available key.
        
        Args:
            error_code: HTTP error code that triggered rotation (429, 401, etc.)
        
        Returns:
            The new active key, or None if no keys available.
        """
        if len(self._keys) <= 1:
            logger.warning("Cannot rotate: only 1 key available")
            return self.current_key

        # Mark current key as failed with cooldown
        self._failed_keys[self._current_index] = time.time() + self._cooldown_seconds
        
        # Find next available key
        next_idx = self._find_available_key()
        if next_idx is not None:
            old_idx = self._current_index
            self._current_index = next_idx
            logger.warning(
                f"Rotated API key: {old_idx} → {next_idx} "
                f"(error={error_code}, pool={len(self._keys)})"
            )
            return self._keys[self._current_index]
        
        logger.error("All API keys exhausted (on cooldown)")
        return None

    def _find_available_key(self) -> int | None:
        """Find the next key not on cooldown."""
        now = time.time()
        for i in range(len(self._keys)):
            idx = (self._current_index + 1 + i) % len(self._keys)
            if idx not in self._failed_keys or now >= self._failed_keys[idx]:
                # Clean up expired cooldowns
                if idx in self._failed_keys:
                    del self._failed_keys[idx]
                return idx
        return None

    @property
    def pool_size(self) -> int:
        return len(self._keys)

    @property
    def available_count(self) -> int:
        now = time.time()
        return sum(
            1 for i in range(len(self._keys))
            if i not in self._failed_keys or now >= self._failed_keys[i]
        )

    def get_status(self) -> str:
        """Get human-readable key rotation status."""
        return (
            f"🔑 Key Pool: {self.available_count}/{self.pool_size} available "
            f"(active: #{self._current_index})"
        )


class ModelFallback:
    """
    Automatic model fallback cascade.

    When the primary model fails (500, timeout, auth error),
    automatically tries the next model in the fallback chain.
    """

    def __init__(self, primary: str, fallbacks: list[str] | None = None):
        """
        Args:
            primary: Primary model name (e.g., "gpt-4o").
            fallbacks: Ordered list of fallback models.
        """
        self._primary = primary
        self._fallbacks = fallbacks or []
        self._chain = [primary] + self._fallbacks
        self._current_index = 0
        self._attempt_count = 0
        self._last_error: str | None = None

    @property
    def current_model(self) -> str:
        """Get the currently active model."""
        return self._chain[self._current_index]

    def fallback(self, error: str = "") -> str | None:
        """
        Move to the next model in the fallback chain.
        
        Returns:
            The fallback model name, or None if chain exhausted.
        """
        self._last_error = error
        self._attempt_count += 1

        if self._current_index + 1 < len(self._chain):
            old = self._chain[self._current_index]
            self._current_index += 1
            new = self._chain[self._current_index]
            logger.warning(f"Model fallback: {old} → {new} (error: {error[:50]})")
            return new
        
        logger.error(f"Model fallback chain exhausted after {self._attempt_count} attempts")
        return None

    def reset(self) -> None:
        """Reset to primary model (typically after a successful response)."""
        if self._current_index != 0:
            logger.info(f"Resetting to primary model: {self._primary}")
        self._current_index = 0
        self._attempt_count = 0
        self._last_error = None

    @property
    def is_using_fallback(self) -> bool:
        return self._current_index > 0

    def get_status(self) -> str:
        """Get human-readable fallback status."""
        chain_display = " → ".join(
            f"**{m}**" if i == self._current_index else m
            for i, m in enumerate(self._chain)
        )
        status = "⚠️ Fallback" if self.is_using_fallback else "✅ Primary"
        return f"{status}: {chain_display}"


class ResilienceLayer:
    """
    Combined resilience layer: key rotation + model fallback.

    Coordinates both mechanisms for maximum uptime.
    """

    def __init__(
        self,
        keys: list[str] | None = None,
        primary_model: str = "gpt-4o",
        fallback_models: list[str] | None = None,
    ):
        self.key_rotator = KeyRotator(keys)
        self.model_fallback = ModelFallback(primary_model, fallback_models)
        self._total_retries = 0
        self._total_fallbacks = 0

    async def handle_error(self, error: Exception, status_code: int | None = None) -> dict[str, Any]:
        """
        Handle an API error by attempting recovery.
        
        Args:
            error: The exception that occurred.
            status_code: HTTP status code if available.
        
        Returns:
            Dict with recovery action taken:
            {
                "action": "rotated_key" | "model_fallback" | "exhausted",
                "new_key": Optional[str],
                "new_model": Optional[str],
            }
        """
        error_str = str(error)

        # Rate limit or auth error → try key rotation first
        if status_code in (429, 401, 403):
            new_key = self.key_rotator.rotate(error_code=status_code)
            if new_key:
                self._total_retries += 1
                return {"action": "rotated_key", "new_key": new_key, "new_model": None}

        # Server error or timeout → try model fallback
        if status_code in (500, 502, 503, 504) or status_code is None:
            new_model = self.model_fallback.fallback(error_str)
            if new_model:
                self._total_fallbacks += 1
                return {"action": "model_fallback", "new_key": None, "new_model": new_model}

        return {"action": "exhausted", "new_key": None, "new_model": None}

    def on_success(self) -> None:
        """Call after a successful API response to reset fallback state."""
        self.model_fallback.reset()

    def get_status(self) -> str:
        """Get combined resilience status."""
        return (
            f"🛡 *Resilience Status*\n"
            f"  {self.key_rotator.get_status()}\n"
            f"  {self.model_fallback.get_status()}\n"
            f"  Retries: {self._total_retries} | Fallbacks: {self._total_fallbacks}"
        )
