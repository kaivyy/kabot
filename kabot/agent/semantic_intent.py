from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_META_FEEDBACK_RE = re.compile(
    r"(?i)\b("
    r"why|wrong|slow|bug|error|"
    r"not (?:that|stock|weather|web\s*search|websearch|brows(?:e|ing))|"
    r"no web\s*search|not web\s*search|"
    r"correct(?:ing|ion)? (?:the )?(?:chat|conversation)|"
    r"not about|that's not what i asked"
    r")\b"
)


@dataclass(slots=True)
class SemanticIntentHint:
    kind: str = "none"
    required_tool: str | None = None
    required_tool_query: str | None = None
    clear_pending: bool = False
    reason: str = ""


def _normalize_text(text: str) -> str:
    raw = str(text or "").strip().lower()
    if not raw:
        return ""
    compact = _NON_WORD_RE.sub(" ", raw)
    return _SPACE_RE.sub(" ", compact).strip()


def _is_cjk_or_unspaced_substantive(raw: str) -> bool:
    if any(ch.isspace() for ch in raw):
        return False
    return bool(
        re.search(r"[\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF\u0E00-\u0E7F]", raw)
        and len(raw) >= 5
    )


def _is_low_information_turn(text: str, *, max_tokens: int, max_chars: int) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if raw.startswith("/"):
        return False
    if _is_cjk_or_unspaced_substantive(raw):
        return False
    if len(normalized) > max_chars:
        return False
    tokens = [token for token in normalized.split(" ") if token]
    return 0 < len(tokens) <= max_tokens


def _looks_like_meta_feedback(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if not _is_low_information_turn(raw, max_tokens=12, max_chars=96):
        return False
    return bool(_META_FEEDBACK_RE.search(normalized))


def arbitrate_semantic_intent(
    text: str,
    *,
    parser_tool: str | None,
    pending_followup_tool: str | None = None,
    pending_followup_source: str = "",
    last_tool_context: dict[str, object] | None = None,
    payload_checker: Callable[[str, str], bool] | None = None,
) -> SemanticIntentHint:
    del parser_tool, pending_followup_tool, pending_followup_source, last_tool_context, payload_checker

    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return SemanticIntentHint()

    if _looks_like_meta_feedback(raw):
        return SemanticIntentHint(
            kind="meta_feedback",
            clear_pending=True,
            reason="meta_feedback_turn",
        )

    return SemanticIntentHint()


__all__ = ["SemanticIntentHint", "arbitrate_semantic_intent"]
