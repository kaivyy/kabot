"""Unit tests for hybrid memory ranking helpers (temporal decay + MMR)."""

from datetime import UTC, datetime, timedelta

from kabot.memory.chroma_memory import ChromaMemoryManager


def _manager_without_init() -> ChromaMemoryManager:
    """Construct manager instance without heavy provider/chroma initialization."""
    return ChromaMemoryManager.__new__(ChromaMemoryManager)


def test_temporal_decay_multiplier_prefers_recent_items():
    recent = ChromaMemoryManager._temporal_decay_multiplier(age_hours=0)
    one_week = ChromaMemoryManager._temporal_decay_multiplier(age_hours=24 * 7)
    one_month = ChromaMemoryManager._temporal_decay_multiplier(age_hours=24 * 30)

    assert recent >= one_week >= one_month
    assert 0.64 <= one_month <= 1.0


def test_apply_temporal_decay_reorders_old_high_score_items():
    manager = _manager_without_init()
    now = datetime.now(UTC).replace(tzinfo=None)

    candidates = [
        {
            "item": {"message_id": "old", "created_at": (now - timedelta(days=45)).isoformat()},
            "score": 0.98,
        },
        {
            "item": {"message_id": "new", "created_at": (now - timedelta(hours=2)).isoformat()},
            "score": 0.83,
        },
    ]

    ranked = manager._apply_temporal_decay_to_candidates(candidates)
    assert ranked[0]["item"]["message_id"] == "new"


def test_mmr_select_candidates_promotes_diversity():
    manager = _manager_without_init()
    query_embedding = [1.0, 0.0]
    candidates = [
        {"item": {"message_id": "a"}, "score": 1.0, "embedding": [1.0, 0.0]},
        {"item": {"message_id": "b"}, "score": 0.97, "embedding": [0.99, 0.01]},
        {"item": {"message_id": "c"}, "score": 0.86, "embedding": [0.0, 1.0]},
    ]

    selected = manager._mmr_select_candidates(
        candidates=candidates,
        query_embedding=query_embedding,
        limit=2,
        lambda_mult=0.3,
    )
    selected_ids = [item["item"]["message_id"] for item in selected]

    assert selected_ids[0] == "a"
    assert selected_ids[1] == "c"
