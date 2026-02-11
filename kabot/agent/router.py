"""
Intent router for adaptive context.
Classifies user messages to select the best system prompt profile.
"""

import logging
import re
from typing import Literal

from kabot.providers.base import LLMProvider

logger = logging.getLogger(__name__)

IntentType = Literal["CODING", "CHAT", "RESEARCH", "GENERAL"]

class IntentRouter:
    """
    Classifies user messages into specific intents using a fast LLM.
    """

    def __init__(self, provider: LLMProvider, model: str = "groq/llama-3.1-8b-instant"):
        self.provider = provider
        self.model = model

    async def classify(self, content: str) -> IntentType:
        """
        Classify the user message content.

        Args:
            content: User message text.

        Returns:
            Detected intent (CODING, CHAT, RESEARCH, GENERAL).
        """
        if not content or len(content.strip()) < 5:
            return "GENERAL"

        # Truncate content for classification to save tokens/time if very long
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
            # Use a low temperature for deterministic classification
            response = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=10,
                temperature=0.0
            )

            intent = response.content.strip().upper()

            # Clean up any potential extra chars
            match = re.search(r'\b(CODING|CHAT|RESEARCH|GENERAL)\b', intent)
            if match:
                return match.group(1) # type: ignore

            return "GENERAL"

        except Exception as e:
            # Fail gracefully to GENERAL if the router model is unavailable
            logger.warning(f"Intent classification failed: {e}. Defaulting to GENERAL.")
            return "GENERAL"
