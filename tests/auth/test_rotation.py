"""Tests for auth key rotation."""

from kabot.auth.rotation import AuthRotation


def test_rotation_cycles_through_keys():
    """Test that rotation cycles through available keys."""
    keys = ["key1", "key2", "key3"]
    rotation = AuthRotation(keys)

    assert rotation.current_key() == "key1"

    rotation.rotate()
    assert rotation.current_key() == "key2"

    rotation.rotate()
    assert rotation.current_key() == "key3"

    # Should cycle back to first
    rotation.rotate()
    assert rotation.current_key() == "key1"


def test_rotation_marks_failed_keys():
    """Test that failed keys are marked and skipped."""
    keys = ["key1", "key2", "key3"]
    rotation = AuthRotation(keys)

    # Mark key1 as failed
    rotation.mark_failed("key1", reason="rate_limit")

    # Should skip to key2
    rotation.rotate()
    assert rotation.current_key() == "key2"

    # key1 should be skipped on next cycle
    rotation.rotate()  # -> key3
    rotation.rotate()  # -> key2 (skip key1)
    assert rotation.current_key() == "key2"


def test_rotation_resets_after_cooldown():
    """Test that failed keys are reset after cooldown period."""
    keys = ["key1", "key2"]
    rotation = AuthRotation(keys, cooldown_seconds=0)  # Instant cooldown for testing

    rotation.mark_failed("key1", reason="rate_limit")
    rotation.rotate()
    assert rotation.current_key() == "key2"

    # After cooldown, key1 should be available again
    import time
    time.sleep(0.1)
    rotation.reset_expired_failures()

    rotation.rotate()  # Should cycle back to key1
    assert rotation.current_key() == "key1"


def test_rotation_with_single_key():
    """Test rotation with only one key."""
    keys = ["only_key"]
    rotation = AuthRotation(keys)

    assert rotation.current_key() == "only_key"

    rotation.rotate()
    assert rotation.current_key() == "only_key"  # Same key


def test_rotation_all_keys_failed():
    """Test behavior when all keys have failed."""
    keys = ["key1", "key2"]
    rotation = AuthRotation(keys)

    rotation.mark_failed("key1", reason="invalid")
    rotation.mark_failed("key2", reason="invalid")

    # Should still return a key (last resort)
    assert rotation.current_key() in keys
