"""Authentication error classification."""

from enum import Enum


class AuthErrorKind(str, Enum):
    AUTH = "auth"              # Invalid/expired credentials
    BILLING = "billing"        # Account billing issues
    RATE_LIMIT = "rate_limit"  # Rate limiting
    FORMAT = "format"          # Request format issues
    TIMEOUT = "timeout"        # Request timeout
    UNKNOWN = "unknown"


def classify_auth_error(status_code: int, message: str = "") -> AuthErrorKind:
    """Classify an API error into a specific kind."""
    msg_lower = message.lower()

    if status_code == 401 or "unauthorized" in msg_lower or "invalid_api_key" in msg_lower:
        return AuthErrorKind.AUTH

    if status_code == 402 or "insufficient_quota" in msg_lower or "billing" in msg_lower:
        return AuthErrorKind.BILLING

    if status_code == 429 or "rate_limit" in msg_lower:
        return AuthErrorKind.RATE_LIMIT

    if status_code == 400 or "invalid_request" in msg_lower:
        return AuthErrorKind.FORMAT

    if status_code == 408 or "timeout" in msg_lower:
        return AuthErrorKind.TIMEOUT

    return AuthErrorKind.UNKNOWN
