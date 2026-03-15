"""Planning, self-eval, and critic helpers extracted from AgentLoop."""

from __future__ import annotations

import re
from typing import Any

from loguru import logger

from kabot.agent.language.lexicon import REMINDER_TERMS, WEATHER_TERMS

IMMEDIATE_ACTION_PATTERNS = [
    *REMINDER_TERMS,
    *WEATHER_TERMS,
    # Quick lookups
    "stock",
    "crypto",
    # Time queries
    "what time",
]

_HINT_TOKEN_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def _normalize_hint_text(text: str) -> str:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return ""
    compact = _HINT_TOKEN_RE.sub(" ", lowered)
    return re.sub(r"\s+", " ", compact).strip()


def get_learned_execution_hints(
    loop: Any,
    question: str,
    *,
    required_tool: str | None = None,
    limit: int = 3,
) -> list[str]:
    """Return bounded lesson-derived execution hints relevant to the current ask."""
    memory_obj = getattr(loop, "memory", None)
    lessons = None
    for getter in (
        getattr(memory_obj, "get_recent_lessons", None),
        getattr(getattr(memory_obj, "metadata", None), "get_recent_lessons", None),
    ):
        if not callable(getter):
            continue
        try:
            lessons = getter(limit=max(limit * 4, 8), task_type="complex")
        except TypeError:
            lessons = getter(limit=max(limit * 4, 8))
        except Exception:
            lessons = None
        if isinstance(lessons, list):
            break

    normalized_query = _normalize_hint_text(question)
    query_tokens = {token for token in normalized_query.split() if len(token) >= 4}
    normalized_tool = _normalize_hint_text(required_tool or "")

    hints: list[str] = []
    if isinstance(lessons, list):
        for lesson in lessons:
            if not isinstance(lesson, dict):
                continue
            guardrail = str(lesson.get("guardrail") or "").strip()
            fix = str(lesson.get("fix") or "").strip()
            trigger = str(lesson.get("trigger") or "").strip()
            hint_text = guardrail or fix or trigger
            if not hint_text or hint_text in hints:
                continue
            haystack = _normalize_hint_text(" ".join(part for part in (guardrail, fix, trigger) if part))
            matches_tool = bool(normalized_tool and normalized_tool in haystack)
            matches_query = bool(query_tokens and any(token in haystack for token in query_tokens))
            if normalized_query and not (matches_tool or matches_query):
                continue
            hints.append(hint_text)
            if len(hints) >= max(1, int(limit or 3)):
                return hints

    guardrails = None
    for getter in (
        getattr(memory_obj, "get_guardrails", None),
        getattr(getattr(memory_obj, "metadata", None), "get_guardrails", None),
    ):
        if not callable(getter):
            continue
        try:
            guardrails = getter(limit=max(limit * 2, 5))
        except Exception:
            guardrails = None
        if isinstance(guardrails, list):
            break

    if isinstance(guardrails, list):
        for item in guardrails:
            hint_text = str(item or "").strip()
            if not hint_text or hint_text in hints:
                continue
            if normalized_query:
                haystack = _normalize_hint_text(hint_text)
                matches_tool = bool(normalized_tool and normalized_tool in haystack)
                matches_query = bool(query_tokens and any(token in haystack for token in query_tokens))
                if not (matches_tool or matches_query):
                    continue
            hints.append(hint_text)
            if len(hints) >= max(1, int(limit or 3)):
                break
    return hints


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
        # Spanish
        "no puedo",
        "no tengo acceso",
        # French
        "je ne peux pas",
        "je n'ai pas acces",
        "je n'ai pas accès",
        # German
        "ich kann nicht",
        "ich habe keinen zugriff",
        # Portuguese
        "nao consigo",
        "não consigo",
        "nao tenho acesso",
        "não tenho acesso",
        # Russian
        "я не могу",
        "у меня нет доступа",
        # Japanese
        "できません",
        "アクセスできません",
        # Chinese
        "我无法",
        "我不能",
        "无法访问",
        # Korean
        "할 수 없",
        "접근할 수 없",
    ]

    has_refusal = any(p in answer_lower for p in refusal_patterns)
    if has_refusal and len(loop.tools.tool_names) > 0:
        tool_list = ", ".join(loop.tools.tool_names)
        return False, (
            f"SYSTEM: You said you cannot do something, but you have these tools: {tool_list}. "
            "Use the appropriate tool instead of refusing. For example, use 'read_file' to read files, "
            "'exec' to run commands, 'web_search' to search the web. Try again and actually use a tool."
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
    except Exception as exc:
        logger.warning(f"Planning failed: {exc}")
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

        logger.info(f"Critic score: {score}/10 - {feedback[:80]}")
        return score, feedback

    except Exception as exc:
        logger.warning(f"Critic evaluation failed: {exc}")
        return 7, "Evaluation skipped"


async def log_lesson(loop: Any, question: str, feedback: str, score_before: int, score_after: int) -> None:
    """Log a metacognition lesson from critic-driven retries."""
    try:
        save_lesson = getattr(getattr(loop, "memory", None), "save_lesson", None)
        if callable(save_lesson):
            result = save_lesson(
                trigger=question[:200],
                mistake=f"Initial response scored {score_before}/10",
                fix=feedback[:200],
                guardrail=f"Improved to {score_after}/10 after retry",
                score_before=score_before,
                score_after=score_after,
                task_type="complex",
            )
            if hasattr(result, "__await__"):
                await result
            logger.info(f"Lesson logged via memory backend ({score_before}->{score_after})")
            return

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
        logger.info(f"Lesson logged: {lesson_id} ({score_before}->{score_after})")
    except Exception as exc:
        logger.warning(f"Failed to log lesson: {exc}")
