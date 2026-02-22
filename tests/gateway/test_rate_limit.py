from kabot.gateway.middleware.rate_limit import RateLimiter


def test_rate_limiter_allows_requests():
    """Test that rate limiter allows requests within limit."""
    limiter = RateLimiter(max_tokens=5, refill_rate=1.0)

    # Should allow first 5 requests
    for i in range(5):
        assert limiter.allow("user1"), f"Request {i+1} should be allowed"

def test_rate_limiter_blocks_excess_requests():
    """Test that rate limiter blocks requests exceeding limit."""
    limiter = RateLimiter(max_tokens=3, refill_rate=1.0)

    # Allow first 3 requests
    for i in range(3):
        assert limiter.allow("user1")

    # Block 4th request
    assert not limiter.allow("user1"), "4th request should be blocked"

def test_rate_limiter_refills_tokens():
    """Test that tokens refill over time."""
    limiter = RateLimiter(max_tokens=2, refill_rate=10.0)  # 10 tokens per second

    # Use up tokens
    assert limiter.allow("user1")
    assert limiter.allow("user1")
    assert not limiter.allow("user1")

    # Wait for refill (0.2 seconds = 2 tokens)
    import time
    time.sleep(0.2)

    # Should allow again
    assert limiter.allow("user1"), "Should allow after refill"

def test_rate_limiter_per_key_isolation():
    """Test that rate limits are isolated per key."""
    limiter = RateLimiter(max_tokens=2, refill_rate=1.0)

    # User1 uses up tokens
    assert limiter.allow("user1")
    assert limiter.allow("user1")
    assert not limiter.allow("user1")

    # User2 should still have tokens
    assert limiter.allow("user2"), "User2 should have separate limit"
    assert limiter.allow("user2")
