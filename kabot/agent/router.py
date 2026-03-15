"""
Intent router for adaptive context and task complexity triaging.

Two responsibilities:
1. Profile selection: CODING / CHAT / RESEARCH / GENERAL
2. Complexity triaging: SIMPLE (direct answer) vs COMPLEX (needs agent loop)
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Literal

from kabot.providers.base import LLMProvider

logger = logging.getLogger(__name__)

IntentType = Literal["CODING", "CHAT", "RESEARCH", "GENERAL"]
TurnCategory = Literal["chat", "action", "contextual_action", "command"]
GroundingMode = Literal["none", "filesystem_inspection"]

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

_ROUTE_CATEGORY_RE = re.compile(r"\b(CODING|CHAT|RESEARCH|GENERAL)\b", re.IGNORECASE)
_ROUTE_TURN_CATEGORY_RE = re.compile(r"\b(chat|action|contextual_action|command)\b", re.IGNORECASE)
_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


@dataclass
class RouteDecision:
    """Result of routing a user message."""

    profile: IntentType
    is_complex: bool
    turn_category: TurnCategory = "chat"
    grounding_mode: GroundingMode = "none"


class IntentRouter:
    """
    Routes user messages: selects personality profile AND triages complexity.

    Simple requests -> direct response, skip agent loop.
    Complex requests -> full reasoning loop.
    """

    def __init__(self, provider: LLMProvider, model: str | None = None):
        self.provider = provider
        self.model = model or provider.get_default_model()

    @staticmethod
    def _normalize_profile(value: str | None) -> IntentType | None:
        normalized = str(value or "").strip().upper()
        if normalized in {"CODING", "CHAT", "RESEARCH", "GENERAL"}:
            return normalized  # type: ignore[return-value]
        return None

    @staticmethod
    def _normalize_turn_category(value: str | None) -> TurnCategory | None:
        normalized = str(value or "").strip().lower()
        if normalized in {"chat", "action", "contextual_action", "command"}:
            return normalized  # type: ignore[return-value]
        return None

    @staticmethod
    def _normalize_grounding_mode(value: str | None) -> GroundingMode | None:
        normalized = str(value or "").strip().lower()
        if normalized in {"none", "filesystem_inspection"}:
            return normalized  # type: ignore[return-value]
        return None

    @staticmethod
    def _parse_bool(value: object) -> bool | None:
        if isinstance(value, bool):
            return value
        normalized = str(value or "").strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
        return None

    def _infer_complexity(
        self,
        *,
        profile: IntentType,
        turn_category: TurnCategory,
        content: str,
    ) -> bool:
        content_stripped = content.strip()
        if turn_category in {"action", "contextual_action", "command"}:
            return True
        if profile in {"CODING", "RESEARCH"}:
            return True
        if profile == "CHAT" and len(content_stripped) < 150:
            return False
        if len(content_stripped) > 100:
            return True
        return False

    def _parse_route_response(self, raw_response: str, content: str) -> RouteDecision | None:
        raw = _JSON_FENCE_RE.sub("", str(raw_response or "").strip()).strip()
        if not raw:
            return None

        parsed_payload = None
        try:
            parsed_payload = json.loads(raw)
        except Exception:
            parsed_payload = None

        if isinstance(parsed_payload, dict):
            profile = self._normalize_profile(str(parsed_payload.get("profile") or ""))
            turn_category = self._normalize_turn_category(
                str(parsed_payload.get("turn_category") or "")
            )
            grounding_mode = self._normalize_grounding_mode(
                str(parsed_payload.get("grounding_mode") or "")
            )
            is_complex = self._parse_bool(parsed_payload.get("is_complex"))
            if profile:
                resolved_turn_category = turn_category or (
                    "action" if is_complex else "chat"
                ) or "chat"
                resolved_grounding_mode = grounding_mode or "none"
                if resolved_grounding_mode == "filesystem_inspection" and resolved_turn_category == "chat":
                    resolved_turn_category = "action"
                resolved_is_complex = (
                    True
                    if resolved_grounding_mode == "filesystem_inspection"
                    else (
                        is_complex
                        if is_complex is not None
                        else self._infer_complexity(
                            profile=profile,
                            turn_category=resolved_turn_category,
                            content=content,
                        )
                    )
                )
                return RouteDecision(
                    profile=profile,
                    is_complex=resolved_is_complex,
                    turn_category=resolved_turn_category,
                    grounding_mode=resolved_grounding_mode,
                )

        profile_match = _ROUTE_CATEGORY_RE.search(raw)
        if not profile_match:
            return None

        profile = self._normalize_profile(profile_match.group(1))
        if not profile:
            return None

        turn_match = _ROUTE_TURN_CATEGORY_RE.search(raw)
        turn_category = self._normalize_turn_category(turn_match.group(1) if turn_match else "")
        if not turn_category:
            turn_category = "action" if profile in {"CODING", "RESEARCH"} else "chat"
        grounding_mode_match = re.search(r"\b(none|filesystem_inspection)\b", raw, re.IGNORECASE)
        grounding_mode = self._normalize_grounding_mode(
            grounding_mode_match.group(1) if grounding_mode_match else ""
        )
        resolved_grounding_mode = grounding_mode or "none"
        if resolved_grounding_mode == "filesystem_inspection" and turn_category == "chat":
            turn_category = "action"

        is_complex = self._parse_bool(raw)
        if resolved_grounding_mode == "filesystem_inspection":
            is_complex = True
        elif is_complex is None:
            is_complex = self._infer_complexity(
                profile=profile,
                turn_category=turn_category,
                content=content,
            )
        return RouteDecision(
            profile=profile,
            is_complex=is_complex,
            turn_category=turn_category,
            grounding_mode=resolved_grounding_mode,
        )

    async def route(self, content: str) -> RouteDecision:
        """
        Full routing: determine profile + complexity.

        Uses minimal deterministic fast paths for obviously safe cases, then
        falls back to the model so multilingual action turns do not depend on
        fixed keyword banks.
        """
        if not content or len(content.strip()) < 3:
            return RouteDecision(profile="GENERAL", is_complex=False, turn_category="chat")

        content_stripped = content.strip()
        if content_stripped.startswith("/"):
            return RouteDecision(profile="GENERAL", is_complex=True, turn_category="command")

        for pattern in _SIMPLE_RE:
            if pattern.match(content_stripped):
                return RouteDecision(profile="CHAT", is_complex=False, turn_category="chat")

        structured_decision = await self.classify_route(content)
        if structured_decision:
            return structured_decision

        profile = await self.classify(content)
        turn_category: TurnCategory = "action" if profile in {"CODING", "RESEARCH"} else "chat"
        return RouteDecision(
            profile=profile,
            is_complex=self._infer_complexity(
                profile=profile,
                turn_category=turn_category,
                content=content,
            ),
            turn_category=turn_category,
            grounding_mode="none",
        )

    async def classify_route(self, content: str) -> RouteDecision | None:
        """Ask the model for a full route decision when fast paths do not apply."""
        if not content or len(content.strip()) < 5:
            return None

        preview = content[:1000]
        prompt = f"""Classify this user turn for runtime routing.

Return ONLY one JSON object with this schema:
{{"profile":"CODING|CHAT|RESEARCH|GENERAL","turn_category":"chat|action|contextual_action|command","is_complex":true|false,"grounding_mode":"none|filesystem_inspection"}}

Definitions:
- CODING: code, debugging, app/site/script/config implementation, or technical build work.
- CHAT: explanation, conversation, clarification, or non-executing answer.
- RESEARCH: live facts, web/news lookup, or source-driven research.
- GENERAL: everything else.
- action: the user wants real work, tool use, file/system/web/message action, or an artifact now.
- contextual_action: a short follow-up that depends on prior task context and should continue the same work.
- command: slash or command-style control input.
- filesystem_inspection: the user wants grounded local filesystem evidence before you explain what a folder, repo, project, app, codebase, local config, or workspace docs/bootstrap files contain, configure, or imply about behavior.

Important:
- Understand the user's actual language. Do not rely on fixed English, Indonesian, Japanese, or Chinese keywords.
- If the user is asking to continue/open/read/send/create/edit/run/check something in any language, prefer action or contextual_action.
- If the user is asking what a local folder, repo, project, app, or codebase is, how it is structured, what it contains, how it is configured, or what local docs/config/bootstrap files say about behavior, prefer grounding_mode=filesystem_inspection.
- If the user is mainly asking for an explanation or casual answer, prefer chat.

User message:
\"\"\"{preview}\"\"\""""

        try:
            response = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=120,
                temperature=0.0,
            )
            return self._parse_route_response(str(response.content or ""), content)
        except Exception as e:
            logger.warning(f"Structured route classification failed: {e}. Falling back.")
            return None

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
