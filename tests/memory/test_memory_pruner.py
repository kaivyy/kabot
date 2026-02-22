# tests/memory/test_memory_pruner.py
"""Tests for MemoryPruner."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from kabot.memory.memory_pruner import MemoryPruner
from kabot.memory.sqlite_store import SQLiteMetadataStore


@pytest.fixture
def store(tmp_path):
    return SQLiteMetadataStore(tmp_path / "test.db")


@pytest.fixture
def pruner():
    return MemoryPruner(max_age_days=30)


class TestMemoryPruner:
    def test_prune_old_facts(self, store, pruner):
        # Add a fact then manually backdate it
        store.add_fact("old1", "factual", "old", "old fact value")
        with store._get_connection() as conn:
            old_date = (datetime.now() - timedelta(days=60)).isoformat()
            conn.execute(
                "UPDATE facts SET created_at = ? WHERE fact_id = ?",
                (old_date, "old1"),
            )
            conn.commit()

        # Add a recent fact
        store.add_fact("new1", "factual", "new", "new fact value")

        deleted = pruner.prune_old_facts(store)
        assert deleted == 1

        # New fact should still exist
        remaining = store.get_facts()
        assert len(remaining) == 1
        assert remaining[0]["fact_id"] == "new1"

    def test_prune_nothing_if_all_recent(self, store, pruner):
        store.add_fact("f1", "factual", "k", "value1")
        store.add_fact("f2", "factual", "k", "value2")
        deleted = pruner.prune_old_facts(store)
        assert deleted == 0

    def test_prune_old_messages(self, store, pruner):
        store.create_session("s1", "telegram", "123")
        store.add_message("m1", "s1", "user", "old message")
        with store._get_connection() as conn:
            old_date = (datetime.now() - timedelta(days=60)).isoformat()
            conn.execute(
                "UPDATE messages SET created_at = ? WHERE message_id = ?",
                (old_date, "m1"),
            )
            conn.commit()
        store.add_message("m2", "s1", "user", "new message")

        deleted = pruner.prune_old_messages(store)
        assert deleted == 1

    def test_custom_age(self, store):
        pruner = MemoryPruner(max_age_days=7)
        store.add_fact("f1", "factual", "k", "value")
        with store._get_connection() as conn:
            old = (datetime.now() - timedelta(days=10)).isoformat()
            conn.execute("UPDATE facts SET created_at = ? WHERE fact_id = ?", (old, "f1"))
            conn.commit()
        deleted = pruner.prune_old_facts(store)
        assert deleted == 1
