import pytest
import sqlite3
from kabot.memory.sqlite_store import SQLiteMetadataStore

@pytest.fixture
def store(tmp_path):
    return SQLiteMetadataStore(tmp_path / "test.db")

def test_add_log(store):
    # This should fail if add_log method or system_logs table doesn't exist
    try:
        store.add_log(
            level="INFO",
            module="test",
            message="hello",
            metadata={"foo": "bar"}
        )
    except AttributeError:
        pytest.fail("add_log method not implemented")
    except sqlite3.OperationalError:
        pytest.fail("system_logs table not created")

    # Verify directly in DB
    with store._get_connection() as conn:
        try:
            row = conn.execute("SELECT * FROM system_logs").fetchone()
            assert row["message"] == "hello"
            assert row["level"] == "INFO"
        except sqlite3.OperationalError:
            pytest.fail("system_logs table missing")

def test_cleanup_logs(store):
    # This should fail if cleanup_logs not implemented
    
    # Prerequisite: Table must exist (if test_add_log passed or we skip to implementation)
    # If add_log failed, we might not get here properly in TDD, but let's write the test.
    with store._get_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO system_logs (level, module, message, created_at) VALUES (?, ?, ?, datetime('now', '-31 days'))",
                ("INFO", "test", "old",)
            )
            conn.execute(
                "INSERT INTO system_logs (level, module, message, created_at) VALUES (?, ?, ?, datetime('now', '-1 day'))",
                ("INFO", "test", "new",)
            )
            conn.commit()
        except sqlite3.OperationalError:
             pytest.fail("Cannot insert test data (table missing)")
    
    try:
        deleted = store.cleanup_logs(retention_days=30)
        assert deleted == 1
    except AttributeError:
        pytest.fail("cleanup_logs method not implemented")
    
    with store._get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM system_logs").fetchone()[0]
        assert count == 1
