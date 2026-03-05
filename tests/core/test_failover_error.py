"""Tests for enhanced failover error classification."""

from kabot.core.failover_error import (
    FailoverError,
    resolve_failover_reason,
    should_fallback,
    should_retry,
)


def test_402_is_billing():
    assert resolve_failover_reason(status=402) == "billing"


def test_429_is_rate_limit():
    assert resolve_failover_reason(status=429) == "rate_limit"


def test_401_is_auth():
    assert resolve_failover_reason(status=401) == "auth"


def test_403_is_auth():
    assert resolve_failover_reason(status=403) == "auth"


def test_timeout_from_message():
    assert resolve_failover_reason(message="Request timed out") == "timeout"


def test_503_is_timeout():
    assert resolve_failover_reason(status=503) == "timeout"


def test_400_is_format():
    assert resolve_failover_reason(status=400) == "format"


def test_404_model_not_found():
    assert resolve_failover_reason(status=404, message="model not found") == "model_not_found"


def test_unknown_fallback():
    assert resolve_failover_reason(status=500) == "unknown"


def test_rate_limit_from_message():
    assert resolve_failover_reason(message="rate limit exceeded") == "rate_limit"


def test_billing_from_message():
    assert resolve_failover_reason(message="insufficient funds") == "billing"


def test_auth_from_message():
    assert resolve_failover_reason(message="invalid api key") == "auth"


def test_auth_from_expired_jwt_message():
    assert (
        resolve_failover_reason(
            message='GroqException - {"error":{"message":"invalid or expired jwt","code":"invalid_or_expired_jwt"}}'
        )
        == "auth"
    )


def test_should_retry_rate_limit():
    assert should_retry("rate_limit") is True


def test_should_retry_timeout():
    assert should_retry("timeout") is True


def test_should_not_retry_auth():
    assert should_retry("auth") is False


def test_should_fallback_billing():
    assert should_fallback("billing") is True


def test_should_fallback_auth():
    assert should_fallback("auth") is True


def test_should_not_fallback_timeout():
    assert should_fallback("timeout") is False


def test_failover_error_exception():
    error = FailoverError("Test error", "rate_limit")
    assert error.reason == "rate_limit"
    assert str(error) == "Test error"

