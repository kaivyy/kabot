"""
Intent router for adaptive context and task complexity triaging.

Two responsibilities:
1. Profile selection: CODING / CHAT / RESEARCH / GENERAL
2. Complexity triaging: SIMPLE (direct answer) vs COMPLEX (needs agent loop)
"""

import logging
import re
from dataclasses import dataclass
from typing import Literal

from kabot.providers.base import LLMProvider

logger = logging.getLogger(__name__)

IntentType = Literal["CODING", "CHAT", "RESEARCH", "GENERAL"]
TurnCategory = Literal["chat", "action", "contextual_action", "command"]

# English-first fast paths. Non-English turns should fall through to the model
# instead of being pre-routed by lexical parser shortcuts.
_SIMPLE_PATTERNS = [
    r"^(h[ae]llo|hi|hey|yo)\b",
    r"^(good\s+(morning|afternoon|evening|night))",
    r"^(thanks?|thx|ty|ok[e]?|okay|yep|yup|nope|sure|cool|nice|great)\b",
    r"^(who\s+are\s+you|what(?:'s| is)\s+your\s+name)",
    r"^(how\s+are\s+you)",
    r"^(yes|no)$",
]
_SIMPLE_RE = [re.compile(p, re.IGNORECASE) for p in _SIMPLE_PATTERNS]

_ENGLISH_REMINDER_KEYWORDS = (
    "remind me",
    "set reminder",
    "reminder",
    "schedule",
)
_ENGLISH_WEATHER_KEYWORDS = (
    "weather",
    "forecast",
    "temperature",
    "wind",
)

_COMPLEX_KEYWORDS = [
    "create", "build", "make", "generate", "write",
    "search", "find", "look up", "research",
    "read file", "write file", "edit file", "delete file",
    "run", "execute", "deploy", "install", "setup", "configure",
    "analyze", "debug", "fix", "repair", "refactor", "optimize",
    "download", "upload", "send", "fetch",
    "check", "verify", "test", "validate", "inspect",
    "automate", "help me", "please",
    *_ENGLISH_REMINDER_KEYWORDS,
    *_ENGLISH_WEATHER_KEYWORDS,
    "spec", "specs", "sysinfo", "system info", "hardware",
    "cpu", "gpu", "ram", "memory",
    "disk", "ssd", "hdd", "storage",
    "space", "free space", "disk space", "disk usage",
    "check disk", "check pc", "capacity",
    "cleanup", "clean up", "clear cache", "clear temp", "delete temp",
]

_TEMPORAL_FAST_RE = re.compile(
    r"(?i)\b("
    r"what day|day is it|what date|what time|"
    r"timezone|time zone|"
    r"utc\s*[+-]?\s*\d{1,2}(?::?\d{2})?|"
    r"tomorrow day|yesterday day|next week day"
    r")\b"
)
_MEMORY_RECALL_FAST_RE = re.compile(
    r"(?i)\b("
    r"what is my preference code|what was my preference code|my preference code|"
    r"what was the code you just remembered|what did you save about me|"
    r"remembered code|saved code|memory code"
    r")\b"
)


@dataclass
class RouteDecision:
    """Result of routing a user message."""

    profile: IntentType
    is_complex: bool
    turn_category: TurnCategory = "chat"


class IntentRouter:
    """
    Routes user messages: selects personality profile AND triages complexity.

    Simple requests -> direct response, skip agent loop.
    Complex requests -> full reasoning loop.
    """

    def __init__(self, provider: LLMProvider, model: str | None = None):
        self.provider = provider
        self.model = model or provider.get_default_model()

    async def route(self, content: str) -> RouteDecision:
        """
        Full routing: determine profile + complexity.

        Uses English-first heuristics for obvious cases, then falls back to the
        model for everything else.
        """
        if not content or len(content.strip()) < 3:
            return RouteDecision(profile="GENERAL", is_complex=False, turn_category="chat")

        content_stripped = content.strip()

        for pattern in _SIMPLE_RE:
            if pattern.match(content_stripped):
                return RouteDecision(profile="CHAT", is_complex=False, turn_category="chat")

        content_lower = content_stripped.lower()
        for keyword in _COMPLEX_KEYWORDS:
            if keyword in content_lower:
                return RouteDecision(profile="GENERAL", is_complex=True, turn_category="action")

        if _TEMPORAL_FAST_RE.search(content_stripped):
            return RouteDecision(profile="GENERAL", is_complex=False, turn_category="chat")
        if _MEMORY_RECALL_FAST_RE.search(content_stripped):
            return RouteDecision(profile="GENERAL", is_complex=False, turn_category="chat")

        profile = await self.classify(content)

        if profile == "CHAT" and len(content_stripped) < 150:
            return RouteDecision(profile=profile, is_complex=False, turn_category="chat")

        if profile in ("CODING", "RESEARCH"):
            return RouteDecision(profile=profile, is_complex=True, turn_category="action")

        if len(content_stripped) > 100:
            return RouteDecision(profile=profile, is_complex=True, turn_category="action")

        return RouteDecision(profile=profile, is_complex=False, turn_category="chat")

    async def classify(self, content: str) -> IntentType:
        """Classify the user message into a profile category."""
        if not content or len(content.strip()) < 5:
            return "GENERAL"

        preview = content[:1000]

        prompt = f"""Classify the following user message into exactly one of these categories:
- CODING: Requests to write, debug, explain, or modify code.
- CHAT: Casual conversation, greetings, personality-based interaction.
- RESEARCH: Requests to search the web, summarize news, or find facts.
- GENERAL: Tasks that don't fit the above (e.g. "remind me", "what time is it").

User message:
"{preview}"

Reply with ONLY the category name (e.g. CODING). Do not add punctuation or explanation."""

        try:
            response = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=10,
                temperature=0.0,
            )

            intent = response.content.strip().upper()
            match = re.search(r"\b(CODING|CHAT|RESEARCH|GENERAL)\b", intent)
            if match:
                return match.group(1)  # type: ignore[return-value]

            return "GENERAL"

        except Exception as e:
            logger.warning(f"Intent classification failed: {e}. Defaulting to GENERAL.")
            return "GENERAL"
