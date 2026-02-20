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

from kabot.agent.language.lexicon import REMINDER_TERMS, WEATHER_TERMS
from kabot.providers.base import LLMProvider

logger = logging.getLogger(__name__)

IntentType = Literal["CODING", "CHAT", "RESEARCH", "GENERAL"]

# Patterns that indicate SIMPLE requests (no tools needed)
# Multilingual: covers EN, ID, ES, FR, DE, PT, RU, JA, KO, ZH, AR, TH, etc.
_SIMPLE_PATTERNS = [
    # Greetings (multilingual)
    r'^(h[ae]llo|hi|hey|yo|hei|hola|bonjour|hallo|oi|ciao|ohayo|annyeong|marhaba)\b',
    r'^(halo|hai|assalamualaikum)\b',  # ID/Malay
    r'^(selamat\s+(pagi|siang|sore|malam))',  # ID time-greetings
    r'^(good\s+(morning|afternoon|evening|night))',  # EN time-greetings
    r'^(buen[oa]s?\s+(dias?|tardes?|noches?))',  # ES time-greetings
    r'^(おはよう|こんにちは|こんばんは)',  # JA greetings
    r'^(안녕)',  # KO greeting
    r'^(你好|早上好|晚上好)',  # ZH greetings
    r'^(привет|здравствуйте)',  # RU greetings
    r'^(สวัสดี)',  # TH greeting
    # Thanks / acknowledgment (multilingual)
    r'^(thanks?|thx|ty|ok[e]?|okay|yep|yup|nope|sure|cool|nice|great)\b',
    r'^(terima\s*kasih|makasih|mantap|siap|baik|oke\s+deh)\b',  # ID
    r'^(gracias|merci|danke|obrigad[oa]|спасибо|ありがとう|감사|谢谢|شكرا)\b',
    # Identity questions (multilingual)
    r'^(who\s+are\s+you|what.s\s+your\s+name)',
    r'^(siapa\s+(kamu|nama\s*mu))',  # ID
    r'^(あなたは誰|너는\s*누구|你是谁)',
    # How are you (multilingual)
    r'^(how\s+are\s+you|apa\s+kabar|como\s+estas|comment\s+vas)',
    # Short affirmations/negations (multilingual)
    r'^(yes|no|ya|iya|tidak|gak|si|non|oui|ja|nein|da|net|はい|いいえ|네|아니|是|不)$',
]
_SIMPLE_RE = [re.compile(p, re.IGNORECASE) for p in _SIMPLE_PATTERNS]

# Keywords that indicate COMPLEX requests (tools/multi-step needed)
# Organized by action category, multilingual
_COMPLEX_KEYWORDS = [
    # Create/build
    "create", "build", "make", "generate", "write",
    "buatkan", "buat", "bikin",  # ID
    "crear", "créer", "erstellen",  # ES/FR/DE
    # Find/search
    "search", "find", "look up", "research",
    "cari", "carikan",  # ID
    "buscar", "chercher", "suchen",  # ES/FR/DE
    # File operations
    "read file", "write file", "edit file", "delete file",
    "baca file", "tulis file",  # ID
    # Execute/run
    "run", "execute", "deploy", "install", "setup", "configure",
    "jalankan",  # ID
    # Analyze/debug
    "analyze", "debug", "fix", "repair", "refactor", "optimize",
    "analisis", "perbaiki", "optimasi",  # ID
    # Download/send
    "download", "upload", "send", "fetch",
    "unduh", "kirim",  # ID
    # Verify/check
    "check", "verify", "test", "validate", "inspect",
    "cek", "periksa",  # ID
    # Schedule/remind
    "automate", "set reminder",
    *REMINDER_TERMS,
    # Weather / live lookups
    *WEATHER_TERMS,
    # Assist
    "help me", "tolong", "please",  # EN/ID
]


@dataclass
class RouteDecision:
    """Result of routing a user message."""
    profile: IntentType     # Personality profile for system prompt
    is_complex: bool        # True = needs Planner→Executor→Critic loop


class IntentRouter:
    """
    Routes user messages: selects personality profile AND triages complexity.

    Simple requests (greetings, thanks) → direct response, skip agent loop.
    Complex requests (coding, research, tool use) → full reasoning loop.
    """

    def __init__(self, provider: LLMProvider, model: str | None = None):
        self.provider = provider
        self.model = model or provider.get_default_model()

    async def route(self, content: str) -> RouteDecision:
        """
        Full routing: determine profile + complexity.

        Uses fast heuristic for obvious cases, LLM for ambiguous ones.

        Args:
            content: User message text.

        Returns:
            RouteDecision with profile and complexity.
        """
        if not content or len(content.strip()) < 3:
            return RouteDecision(profile="GENERAL", is_complex=False)

        content_stripped = content.strip()

        # --- Fast heuristic: obvious SIMPLE cases ---
        for pattern in _SIMPLE_RE:
            if pattern.match(content_stripped):
                return RouteDecision(profile="CHAT", is_complex=False)

        # --- Fast heuristic: obvious COMPLEX cases ---
        # Action keywords ALWAYS need tools → force COMPLEX, skip LLM classification
        # that could downgrade to SIMPLE via "CHAT + short message" heuristic
        content_lower = content_stripped.lower()
        for keyword in _COMPLEX_KEYWORDS:
            if keyword in content_lower:
                return RouteDecision(profile="GENERAL", is_complex=True)

        # --- Ambiguous: use LLM classification ---
        profile = await self.classify(content)

        # Short CHAT messages are usually simple
        if profile == "CHAT" and len(content_stripped) < 150:
            return RouteDecision(profile=profile, is_complex=False)

        # CODING and RESEARCH are always complex
        if profile in ("CODING", "RESEARCH"):
            return RouteDecision(profile=profile, is_complex=True)

        # GENERAL with moderate length → complex
        if len(content_stripped) > 100:
            return RouteDecision(profile=profile, is_complex=True)

        return RouteDecision(profile=profile, is_complex=False)

    async def classify(self, content: str) -> IntentType:
        """
        Classify the user message into a profile category.

        Args:
            content: User message text.

        Returns:
            Detected intent (CODING, CHAT, RESEARCH, GENERAL).
        """
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
                temperature=0.0
            )

            intent = response.content.strip().upper()
            match = re.search(r'\b(CODING|CHAT|RESEARCH|GENERAL)\b', intent)
            if match:
                return match.group(1)  # type: ignore

            return "GENERAL"

        except Exception as e:
            logger.warning(f"Intent classification failed: {e}. Defaulting to GENERAL.")
            return "GENERAL"
