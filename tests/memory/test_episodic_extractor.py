# tests/memory/test_episodic_extractor.py
"""Tests for EpisodicExtractor."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.memory.episodic_extractor import EpisodicExtractor, ExtractedFact


class TestEpisodicExtractor:
    def test_extracted_fact_dataclass(self):
        fact = ExtractedFact(
            content="User likes coffee",
            category="preference",
            confidence=0.9,
        )
        assert fact.content == "User likes coffee"
        assert fact.category == "preference"

    @pytest.mark.asyncio
    async def test_extract_returns_facts(self):
        extractor = EpisodicExtractor()
        provider = AsyncMock()
        provider.chat = AsyncMock(return_value=MagicMock(
            content=json.dumps([
                {"content": "User prefers dark mode", "category": "preference", "confidence": 0.9}
            ])
        ))
        messages = [
            {"role": "user", "content": "I really prefer dark mode on everything"},
            {"role": "assistant", "content": "Noted! I'll remember that."},
        ]
        facts = await extractor.extract(messages, provider)
        assert len(facts) >= 1
        assert facts[0].content == "User prefers dark mode"

    @pytest.mark.asyncio
    async def test_extract_empty_messages(self):
        extractor = EpisodicExtractor()
        provider = AsyncMock()
        facts = await extractor.extract([], provider)
        assert facts == []

    @pytest.mark.asyncio
    async def test_extract_handles_llm_error(self):
        extractor = EpisodicExtractor()
        provider = AsyncMock()
        provider.chat = AsyncMock(side_effect=Exception("API down"))
        messages = [{"role": "user", "content": "I like cats"}]
        facts = await extractor.extract(messages, provider)
        assert facts == []

    @pytest.mark.asyncio
    async def test_extract_handles_bad_json(self):
        extractor = EpisodicExtractor()
        provider = AsyncMock()
        provider.chat = AsyncMock(return_value=MagicMock(content="not json at all"))
        messages = [{"role": "user", "content": "I like cats"}]
        facts = await extractor.extract(messages, provider)
        assert facts == []
