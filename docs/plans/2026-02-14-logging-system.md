# Logging System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a dual logging system (File + SQLite) with configurable rotation and retention policies.

**Architecture:** 
- `LoggingConfig` in `schema.py` defines policies.
- `DatabaseSink` adapter pipes `loguru` records to `metadata.db`.
- `SQLiteMetadataStore` manages the `system_logs` table and retention cleanup.
- Global logger configuration applied on startup.

**Tech Stack:** `loguru`, `sqlite3`, `pydantic`.

---

### Task 1: Configuration Schema

**Files:**
- Modify: `kabot/config/schema.py`

**Step 1: Write the failing test**
Create `tests/config/test_logging_config.py`:
```python
from kabot.config.schema import LoggingConfig, Config

def test_logging_config_defaults():
    cfg = LoggingConfig()
    assert cfg.enabled is True
    assert cfg.level == "INFO"
    assert cfg.rotation == "10 MB"
    assert cfg.retention == "7 days"
    assert cfg.db_retention_days == 30

def test_config_integration():
    cfg = Config()
    assert cfg.logging.enabled is True
```

**Step 2: Run test to verify it fails**
Run: `pytest tests/config/test_logging_config.py`
Expected: `ImportError` or `AttributeError`

**Step 3: Write implementation**
In `kabot/config/schema.py`:
```python
class LoggingConfig(BaseModel):
    """Logging configuration."""
    enabled: bool = True
    level: str = "INFO"
    file_enabled: bool = True
    file_path: str = "~/.kabot/logs/kabot.log"
    rotation: str = "10 MB"
    retention: str = "7 days"
    db_enabled: bool = True
    db_retention_days: int = 30

class Config(BaseSettings):
    # ... existing fields ...
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    # ...
```

**Step 4: Run test to verify it passes**
Run: `pytest tests/config/test_logging_config.py`
Expected: PASS

**Step 5: Commit**
`git add kabot/config/schema.py tests/config/test_logging_config.py`
`git commit -m "feat(config): add logging configuration schema"`

---

### Task 2: Database Storage (Schema & Cleanup)

**Files:**
- Modify: `kabot/memory/sqlite_store.py`

**Step 1: Write the failing test**
Create `tests/memory/test_logging_store.py`:
```python
import pytest
from kabot.memory.sqlite_store import SQLiteMetadataStore

@pytest.fixture
def store(tmp_path):
    return SQLiteMetadataStore(tmp_path / "test.db")

def test_add_log(store):
    store.add_log(
        level="INFO",
        module="test",
        message="hello",
        metadata={"foo": "bar"}
    )
    # Verify directly in DB
    with store._get_connection() as conn:
        row = conn.execute("SELECT * FROM system_logs").fetchone()
        assert row["message"] == "hello"
        assert row["level"] == "INFO"

def test_cleanup_logs(store):
    # Add old log
    with store._get_connection() as conn:
        conn.execute(
            "INSERT INTO system_logs (level, message, created_at) VALUES (?, ?, datetime('now', '-31 days'))",
            ("INFO", "old",)
        )
        conn.execute(
            "INSERT INTO system_logs (level, message, created_at) VALUES (?, ?, datetime('now', '-1 day'))",
            ("INFO", "new",)
        )
        conn.commit()
    
    deleted = store.cleanup_logs(retention_days=30)
    assert deleted == 1
    
    with store._get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM system_logs").fetchone()[0]
        assert count == 1
```

**Step 2: Run test to verify it fails**
Run: `pytest tests/memory/test_logging_store.py`
Expected: `OperationalError: no such table: system_logs`

**Step 3: Write implementation**
In `kabot/memory/sqlite_store.py`:
1. Update `_init_db` to create `system_logs` table.
2. Add `add_log` method.
3. Add `cleanup_logs` method.

**Step 4: Run test to verify it passes**
Run: `pytest tests/memory/test_logging_store.py`
Expected: PASS

**Step 5: Commit**
`git add kabot/memory/sqlite_store.py tests/memory/test_logging_store.py`
`git commit -m "feat(db): add system_logs table and cleanup logic"`

---

### Task 3: Logger Integration (The Sink)

**Files:**
- Create: `kabot/core/logger.py`
- Modify: `kabot/cli/commands.py` (to init logging)

**Step 1: Write the failing test**
Create `tests/core/test_logger.py`:
```python
from loguru import logger
from kabot.core.logger import configure_logger, DatabaseSink
from kabot.config.schema import Config

def test_db_sink_integration(tmp_path):
    # Setup mock
    class MockStore:
        def __init__(self):
            self.logs = []
        def add_log(self, **kwargs):
            self.logs.append(kwargs)
    
    store = MockStore()
    config = Config()
    
    # Configure
    configure_logger(config, store)
    
    # Log
    logger.info("Test message")
    
    # Assert
    assert len(store.logs) > 0
    assert store.logs[0]["message"] == "Test message"
```

**Step 2: Run test to verify it fails**
Run: `pytest tests/core/test_logger.py`
Expected: `ImportError`

**Step 3: Write implementation**
In `kabot/core/logger.py`:
```python
from loguru import logger
import sys

class DatabaseSink:
    def __init__(self, store):
        self.store = store
    
    def write(self, message):
        record = message.record
        self.store.add_log(
            level=record["level"].name,
            module=record["name"],
            message=record["message"],
            metadata=record["extra"],
            exception=str(record["exception"]) if record["exception"] else None
        )

def configure_logger(config, store=None):
    logger.remove() # Remove default handler
    
    # Console (stderr)
    logger.add(sys.stderr, level=config.logging.level)
    
    # File
    if config.logging.file_enabled:
        path = Path(config.logging.file_path).expanduser()
        logger.add(
            path,
            rotation=config.logging.rotation,
            retention=config.logging.retention,
            level=config.logging.level
        )
    
    # DB
    if config.logging.db_enabled and store:
        logger.add(DatabaseSink(store), level=config.logging.level)
```

**Step 4: Run test to verify it passes**
Run: `pytest tests/core/test_logger.py`
Expected: PASS

**Step 5: Commit**
`git add kabot/core/logger.py tests/core/test_logger.py`
`git commit -m "feat(core): add logger configuration and simple DataBaseSink"`

---

### Task 4: Wiring It All Up

**Files:**
- Modify: `kabot/cli/commands.py` (initialize logger in `gateway` and `agent` commands)

**Step 1: Manual Verification**
- We can't easily unit test the CLI entry point without spawning processes.
- We will rely on running the `agent` command.

**Step 2: Implementation**
In `kabot/cli/commands.py`:
- Import `configure_logger`
- Call it in `gateway()` and `agent()` before other logic.
- Pass the `cron.service.store` (or create a dedicated store instance if needed, but `SQLiteMetadataStore` is typically available via `SessionManager` or initialized directly).
- *Correction*: `CronService` doesn't hold the metadata store. We need `session_manager.db` (which is `SQLiteMetadataStore`) or init it.

**Step 3: Commit**
`git add kabot/cli/commands.py`
`git commit -m "feat(cli): enable logging in agent and gateway"`
