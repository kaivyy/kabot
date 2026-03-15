"""MCP-specific parsing helpers for message runtime."""

from __future__ import annotations

import re

__all__ = [
    "_extract_explicit_mcp_prompt_reference",
    "_extract_explicit_mcp_resource_reference",
]

_EXPLICIT_MCP_PROMPT_ALIAS_RE = re.compile(
    r"\bmcp\.prompt\.([A-Za-z0-9_-]+)\.([A-Za-z0-9_.-]+)\b",
    re.IGNORECASE,
)
_EXPLICIT_MCP_PROMPT_NATURAL_RE = re.compile(
    r"\b(?:use|render|apply|show)\s+"
    r"(?:prompt\s+)?(?P<prompt>[A-Za-z0-9_.-]+)\s+"
    r"(?:from)\s+(?:server\s+)?(?P<server>[A-Za-z0-9_-]+)\b",
    re.IGNORECASE,
)
_EXPLICIT_MCP_RESOURCE_ALIAS_RE = re.compile(
    r"\bmcp\.resource\.([A-Za-z0-9_-]+)\s+([^\s]+)",
    re.IGNORECASE,
)
_EXPLICIT_MCP_RESOURCE_NATURAL_RE = re.compile(
    r"\b(?:read|use|show)\s+"
    r"(?:resource\s+)?(?P<resource>(?:[A-Za-z][A-Za-z0-9+.-]*://[^\s]+|[A-Za-z0-9_.-]+))\s+"
    r"(?:from)\s+(?:server\s+)?(?P<server>[A-Za-z0-9_-]+)\b",
    re.IGNORECASE,
)


def _strip_trailing_reference_punctuation(value: str) -> str:
    return str(value or "").strip().rstrip(".,;:!?)]}\"'”’")


def _extract_explicit_mcp_prompt_reference(text: str) -> tuple[str, str] | None:
    raw_text = str(text or "").strip()
    if not raw_text:
        return None
    alias_match = _EXPLICIT_MCP_PROMPT_ALIAS_RE.search(raw_text)
    if alias_match:
        server_name, prompt_name = alias_match.groups()
        return str(server_name).strip(), str(prompt_name).strip()
    natural_match = _EXPLICIT_MCP_PROMPT_NATURAL_RE.search(raw_text)
    if natural_match:
        return (
            str(natural_match.group("server")).strip(),
            str(natural_match.group("prompt")).strip(),
        )
    return None


def _extract_explicit_mcp_resource_reference(text: str) -> tuple[str, str] | None:
    raw_text = str(text or "").strip()
    if not raw_text:
        return None
    alias_match = _EXPLICIT_MCP_RESOURCE_ALIAS_RE.search(raw_text)
    if alias_match:
        server_name, resource_ref = alias_match.groups()
        return str(server_name).strip(), _strip_trailing_reference_punctuation(resource_ref)
    natural_match = _EXPLICIT_MCP_RESOURCE_NATURAL_RE.search(raw_text)
    if natural_match:
        return (
            str(natural_match.group("server")).strip(),
            _strip_trailing_reference_punctuation(natural_match.group("resource")),
        )
    return None
