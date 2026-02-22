"""Planning, self-eval, and critic helpers extracted from AgentLoop."""

from __future__ import annotations

import re
from typing import Any

from loguru import logger

from kabot.agent.language.lexicon import REMINDER_TERMS, WEATHER_TERMS

IMMEDIATE_ACTION_PATTERNS = [
    # Reminders / scheduling (multilingual)
    "remind",
    "reminder",
    "schedule",
    "alarm",
    "ingatkan",
    "bangunkan",
    "jadwalkan",
    "pengingat",
    "timer",
    "wake me",
    "peringatan",
    "jadual",
    "เตือน",
    "提醒",
    # Weather
    "weather",
    "cuaca",
    "suhu",
    "temperature",
    "ramalan",
    "อากาศ",
    "天气",
    "气温",
    # Quick lookups
    "stock",
    "crypto",
    "saham",
    "harga",
    # Time queries
    "what time",
    "jam berapa",
]


IMMEDIATE_ACTION_PATTERNS = [
    *REMINDER_TERMS,
    *WEATHER_TERMS,
    # Quick lookups
    "stock",
    "crypto",
    "saham",
    "harga",
    # Time queries
    "what time",
    "jam berapa",
]


def self_evaluate(loop: Any, question: str, answer: str) -> tuple[bool, str | None]:
    """Quick heuristic: detect common refusal patterns."""
    if not answer or len(answer) < 30:
        return True, None

    answer_lower = answer.lower()

    refusal_patterns = [
        # English
        "i cannot",
        "i can't",
        "i don't have access",
        "i'm unable to",
        "i am unable to",
        "cannot access",
        "i'm not able to",
        # Indonesian
        "saya tidak bisa",
        "saya tidak dapat",
        "saya tidak memiliki akses",
        "tidak dapat mengakses",
        # Spanish
        "no puedo",
        "no tengo acceso",
        # French
        "je ne peux pas",
        "je n'ai pas accÃ¨s",
        # German
        "ich kann nicht",
        "ich habe keinen zugriff",
        # Portuguese
        "nÃ£o consigo",
        "nÃ£o tenho acesso",
        # Russian
        "Ñ Ð½Ðµ Ð¼Ð¾Ð³Ñƒ",
        "Ñƒ Ð¼ÐµÐ½Ñ Ð½ÐµÑ‚ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð°",
        # Japanese
        "ã§ãã¾ã›ã‚“",
        "ã‚¢ã‚¯ã‚»ã‚¹ã§ãã¾ã›ã‚“",
        # Chinese
        "æˆ‘æ— æ³•",
        "æˆ‘ä¸èƒ½",
        "æ— æ³•è®¿é—®",
        # Korean
        "í•  ìˆ˜ ì—†",
        "ì ‘ê·¼í•  ìˆ˜ ì—†",
    ]

    has_refusal = any(p in answer_lower for p in refusal_patterns)
    if has_refusal and len(loop.tools.tool_names) > 0:
        tool_list = ", ".join(loop.tools.tool_names)
        return False, (
            f"SYSTEM: You said you cannot do something, but you have these tools: {tool_list}. "
            f"Use the appropriate tool instead of refusing. For example, use 'read_file' to read files, "
            f"'exec' to run commands, 'web_search' to search the web. Try again and actually use a tool."
        )

    return True, None


async def plan_task(loop: Any, question: str) -> str | None:
    """Ask LLM to create a brief execution plan."""
    if len(question) < 30:
        return None

    q_lower = question.lower()
    for pattern in IMMEDIATE_ACTION_PATTERNS:
        if pattern in q_lower:
            logger.info(f"Skipping plan for immediate-action task: matched '{pattern}'")
            return None

    try:
        plan_prompt = f"""Create a brief plan (max 5 steps) to answer this request.
For each step, specify:
1. What to do
2. Which tool to use (if any)
3. Success criteria

CRITICAL: If the request is for creating code, skills, or complex actions, Step 1 MUST be "Ask user for approval/details".
Do not plan to write/execute immediately.

Request: {question[:500]}

Reply with a numbered plan. Be concise."""

        response = await loop.provider.chat(
            messages=[{"role": "user", "content": plan_prompt}],
            model=loop.model,
            max_tokens=300,
            temperature=0.3,
        )
        logger.info(f"Plan generated: {response.content[:100]}...")
        return response.content
    except Exception as e:
        logger.warning(f"Planning failed: {e}")
        return None


def is_weak_model(loop: Any, model: str) -> bool:
    """Check if model is considered weak and needs adaptive critic thresholds."""
    weak_models = [
        "llama-4-scout",
        "llama-3.1-8b",
        "llama-3-8b",
        "gemma-7b",
        "mistral-7b",
        "phi-3",
        "qwen-7b",
        "codellama-7b",
    ]
    model_lower = model.lower()
    return any(weak in model_lower for weak in weak_models)


async def critic_evaluate(loop: Any, question: str, answer: str, model: str | None = None) -> tuple[int, str]:
    """Score response quality 0-10 with rubric."""
    try:
        eval_model = model or loop.model
        if is_weak_model(loop, eval_model):
            stronger_models = [
                "openai/gpt-4o",
                "anthropic/claude-3-5-sonnet-20241022",
                "openai/gpt-4o-mini",
            ]
            for strong_model in stronger_models:
                try:
                    await loop.provider.chat(
                        messages=[{"role": "user", "content": "test"}],
                        model=strong_model,
                        max_tokens=5,
                        temperature=0.0,
                    )
                    eval_model = strong_model
                    logger.info(f"Using stronger model {strong_model} for critic evaluation")
                    break
                except Exception:
                    continue
        eval_prompt = f"""Score this AI response 0-10 based on:
- Correctness: Does it accurately answer the question?
- Completeness: Is anything important missing?
- Evidence: Did it use tools/data or fabricate information?
- Clarity: Is it well-structured and clear?

Question: {question[:300]}
Response: {answer[:800]}

Reply in this EXACT format:
SCORE: X
FEEDBACK: <one sentence explaining the score>"""

        response = await loop.provider.chat(
            messages=[{"role": "user", "content": eval_prompt}],
            model=eval_model,
            max_tokens=100,
            temperature=0.0,
        )

        score_match = re.search(r"SCORE:\s*(\d+)", response.content)
        score = int(score_match.group(1)) if score_match else 7
        score = max(0, min(10, score))

        feedback_match = re.search(r"FEEDBACK:\s*(.+)", response.content)
        feedback = feedback_match.group(1).strip() if feedback_match else response.content

        logger.info(f"Critic score: {score}/10 â€” {feedback[:80]}")
        return score, feedback

    except Exception as e:
        logger.warning(f"Critic evaluation failed: {e}")
        return 7, "Evaluation skipped"


async def log_lesson(loop: Any, question: str, feedback: str, score_before: int, score_after: int) -> None:
    """Log a metacognition lesson from critic-driven retries."""
    try:
        import uuid

        lesson_id = str(uuid.uuid4())[:12]
        loop.memory.metadata.add_lesson(
            lesson_id=lesson_id,
            trigger=question[:200],
            mistake=f"Initial response scored {score_before}/10",
            fix=feedback[:200],
            guardrail=f"Improved to {score_after}/10 after retry",
            score_before=score_before,
            score_after=score_after,
            task_type="complex",
        )
        logger.info(f"Lesson logged: {lesson_id} ({score_before}â†’{score_after})")
    except Exception as e:
        logger.warning(f"Failed to log lesson: {e}")
