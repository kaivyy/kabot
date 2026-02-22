# kabot/memory/episodic_extractor.py
"""Episodic Extractor: auto-extract user facts from conversations."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class ExtractedFact:
    """A fact extracted from a conversation."""
    content: str
    category: str  # "preference", "factual", "habit", "entity"
    confidence: float = 0.8


EXTRACTION_PROMPT = """Analyze this conversation and extract any user preferences, personal facts, habits, or important entities.

Rules:
- Only extract CONCRETE facts about the USER (not about the AI or generic info).
- Categories: "preference" (likes/dislikes), "factual" (name, location, job), "habit" (routines), "entity" (projects, pets, people they mention).
- Confidence: 0.9 for explicitly stated, 0.7 for implied.
- If nothing to extract, return an empty JSON array [].
- Respond with ONLY a valid JSON array, no markdown, no explanation.

Format:
[{{""content"": ""fact text"", ""category"": ""preference|factual|habit|entity"", ""confidence"": 0.9}}]

Conversation:
{conversation}"""


class EpisodicExtractor:
    """Extract user preferences and facts from conversations using LLM.

    Runs asynchronously after each chat session ends.
    Uses the existing LLM provider (no new API key needed).
    """

    async def extract(
        self,
        messages: list[dict[str, Any]],
        provider: Any,
        model: str | None = None,
    ) -> list[ExtractedFact]:
        """Extract facts from a conversation.

        Args:
            messages: Conversation messages (list of {role, content}).
            provider: LLM provider instance.
            model: Optional model override.

        Returns:
            List of extracted facts.
        """
        if not messages or len(messages) < 2:
            return []

        try:
            # Build conversation text (only keep user + assistant, not system)
            conv_lines = []
            for msg in messages[-20:]:  # Last 20 messages max
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role in ("user", "assistant") and isinstance(content, str):
                    conv_lines.append(f"{role}: {content[:300]}")

            if not conv_lines:
                return []

            conversation_text = "\n".join(conv_lines)
            prompt = EXTRACTION_PROMPT.format(conversation=conversation_text)

            response = await provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                max_tokens=500,
                temperature=0.1,
            )

            return self._parse_response(response.content)

        except Exception as e:
            logger.exception(f"Episodic extraction failed: {e}")
            return []

    def _parse_response(self, text: str) -> list[ExtractedFact]:
        """Parse LLM response into ExtractedFact objects."""
        try:
            # Try to find JSON in the response
            text = text.strip()
            # Handle markdown fences
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            if not json_match:
                return []

            data = json.loads(json_match.group())
            if not isinstance(data, list):
                return []

            facts = []
            for item in data:
                if isinstance(item, dict) and "content" in item:
                    facts.append(ExtractedFact(
                        content=item["content"],
                        category=item.get("category", "factual"),
                        confidence=float(item.get("confidence", 0.8)),
                    ))
            return facts

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.debug(f"Failed to parse extraction response: {e}")
            return []
