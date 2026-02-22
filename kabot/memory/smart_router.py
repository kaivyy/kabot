# kabot/memory/smart_router.py
"""Smart Router: classify query intent for memory routing."""

from __future__ import annotations

import re
from typing import Literal

MemoryRoute = Literal["episodic", "knowledge", "hybrid"]

# Multilingual keywords — episodic (personal/temporal)
EPISODIC_KEYWORDS = [
    # Indonesian
    "kamu", "aku", "tadi", "sebelumnya", "ingat", "kemarin", "biasanya",
    "preferensi", "suka", "kebiasaan", "waktu itu", "dulu",
    # English
    "remember", "you said", "i told", "earlier", "before", "yesterday",
    "last time", "my preference", "i like", "i prefer", "i usually",
    # Spanish
    "recuerda", "dijiste", "antes", "ayer", "prefiero",
    # French
    "souviens", "tu as dit", "avant", "hier", "je préfère",
    # Japanese
    "覚えて", "さっき", "前に", "昨日", "好き", "言い",
    # Chinese
    "记得", "你说", "之前", "昨天", "喜欢",
    # Korean
    "기억", "아까", "어제", "좋아",
    # Thai
    "จำได้", "เมื่อกี้", "เมื่อวาน", "ชอบ",
]

# Multilingual keywords — knowledge (factual/instructional)
KNOWLEDGE_KEYWORDS = [
    # Indonesian
    "apa itu", "jelaskan", "cara", "bagaimana", "definisi", "dokumen",
    "panduan", "info", "penjelasan", "tutorial", "langkah",
    # English
    "what is", "explain", "how to", "how does", "define", "definition",
    "guide", "tutorial", "documentation", "steps", "instructions",
    # Spanish
    "qué es", "explica", "cómo", "definición", "guía",
    # French
    "qu'est-ce", "expliquer", "comment", "définition", "guide",
    # Japanese
    "とは", "説明", "方法", "定義", "ガイド",
    # Chinese
    "什么是", "解释", "怎么", "定义", "指南",
    # Korean
    "무엇", "설명", "방법", "정의",
    # Thai
    "คืออะไร", "อธิบาย", "วิธี", "คำจำกัดความ",
]


class SmartRouter:
    """Classify queries into episodic/knowledge/hybrid routing.

    Rule-based first (zero cost). Falls back to 'hybrid' if ambiguous.
    """

    def __init__(self):
        self._episodic_patterns = [
            re.compile(re.escape(k), re.IGNORECASE) for k in EPISODIC_KEYWORDS
        ]
        self._knowledge_patterns = [
            re.compile(re.escape(k), re.IGNORECASE) for k in KNOWLEDGE_KEYWORDS
        ]

    def route(self, query: str) -> MemoryRoute:
        """Classify a query into episodic, knowledge, or hybrid.

        Args:
            query: User query text.

        Returns:
            "episodic", "knowledge", or "hybrid".
        """
        if not query or not query.strip():
            return "hybrid"

        has_episodic = any(p.search(query) for p in self._episodic_patterns)
        has_knowledge = any(p.search(query) for p in self._knowledge_patterns)

        if has_episodic and not has_knowledge:
            return "episodic"
        elif has_knowledge and not has_episodic:
            return "knowledge"
        else:
            return "hybrid"
