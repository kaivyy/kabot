"""Enhanced failover error classification for API errors."""

from __future__ import annotations

from typing import Literal

FailoverReason = Literal[
    "billing",
    "rate_limit",
    "auth",
    "timeout",
    "format",
    "model_not_found",
    "unknown",
]


class FailoverError(Exception):
    """Exception with failover reason classification."""

    def __init__(self, message: str, reason: FailoverReason):
        super().__init__(message)
        self.reason = reason


def resolve_failover_reason(
    *,
    status: int | None = None,
    message: str | None = None,
    error_code: str | None = None,
) -> FailoverReason:
    """
    Classify API error into failover reason category.

    Args:
        status: HTTP status code
        message: Error message text
        error_code: Provider-specific error code

    Returns:
        Failover reason category
    """
    msg_lower = (message or "").lower()

    # Status code classification
    if status == 402:
        return "billing"
    if status == 429:
        return "rate_limit"
    if status in (401, 403):
        return "auth"
    if status == 400:
        return "format"
    if status == 404:
        # Could be model not found or endpoint not found
        if "model" in msg_lower:
            return "model_not_found"
        return "unknown"

    # Message-based classification
    if any(keyword in msg_lower for keyword in ["timeout", "timed out", "deadline"]):
        return "timeout"
    if any(keyword in msg_lower for keyword in ["rate limit", "too many requests", "quota"]):
        return "rate_limit"
    if any(keyword in msg_lower for keyword in ["billing", "payment", "insufficient funds"]):
        return "billing"
    if any(keyword in msg_lower for keyword in ["unauthorized", "forbidden", "invalid api key"]):
        return "auth"
    if any(keyword in msg_lower for keyword in ["model not found", "model does not exist"]):
        return "model_not_found"
    if any(keyword in msg_lower for keyword in ["invalid request", "bad request", "malformed"]):
        return "format"

    # Error code classification (provider-specific)
    if error_code:
        code_lower = error_code.lower()
        if "rate" in code_lower or "quota" in code_lower:
            return "rate_limit"
        if "auth" in code_lower or "key" in code_lower:
            return "auth"
        if "billing" in code_lower or "payment" in code_lower:
            return "billing"

    return "unknown"


def should_retry(reason: FailoverReason) -> bool:
    """Determine if error should trigger retry."""
    return reason in ("rate_limit", "timeout", "unknown")


def should_fallback(reason: FailoverReason) -> bool:
    """Determine if error should trigger model fallback."""
    return reason in ("billing", "auth", "model_not_found")
