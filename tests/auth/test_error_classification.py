# tests/auth/test_error_classification.py
from kabot.auth.errors import classify_auth_error, AuthErrorKind

def test_expired_token():
    result = classify_auth_error(401, "invalid_api_key")
    assert result == AuthErrorKind.AUTH

def test_billing_error():
    result = classify_auth_error(402, "insufficient_quota")
    assert result == AuthErrorKind.BILLING

def test_rate_limit():
    result = classify_auth_error(429, "rate_limit_exceeded")
    assert result == AuthErrorKind.RATE_LIMIT

def test_server_error():
    result = classify_auth_error(500, "internal_server_error")
    assert result == AuthErrorKind.UNKNOWN
