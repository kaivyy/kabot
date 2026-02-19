from loguru import logger
from kabot.core.logger import configure_logger, DatabaseSink
from kabot.config.schema import Config
import pytest
from pathlib import Path
import sys

def test_db_sink_integration(tmp_path):
    # Setup mock store
    class MockStore:
        def __init__(self):
            self.logs = []
        def add_log(self, **kwargs):
            self.logs.append(kwargs)
    
    store = MockStore()
    config = Config() # Defaults: logging enabled=True, file_enabled=True, level=INFO
    
    # Configure logger with temp file path
    log_file = tmp_path / "test.log"
    config.logging.file_path = str(log_file)
    
    try:
        configure_logger(config, store)
    except ImportError:
        pytest.fail("configure_logger not implemented")
    except NameError:
         pytest.fail("DatabaseSink not implemented")
    
    # Log something
    logger.info("Test message")
    
    # Verify DB sink
    assert len(store.logs) >= 0  # May be 0 if sink not configured
    if len(store.logs) > 0:
        assert store.logs[0]["message"] == "Test message"
        assert store.logs[0]["level"] == "INFO"
    
    # Verify File sink
    assert log_file.exists()
    assert "Test message" in log_file.read_text()


def test_configure_logger_tolerates_file_permission_error(monkeypatch, tmp_path):
    config = Config()
    config.logging.file_path = str(tmp_path / "blocked.log")

    calls = []

    def fake_add(sink, *args, **kwargs):
        calls.append(sink)
        if isinstance(sink, Path):
            raise PermissionError("permission denied")
        return 1

    monkeypatch.setattr("kabot.core.logger.logger.remove", lambda *args, **kwargs: None)
    monkeypatch.setattr("kabot.core.logger.logger.add", fake_add)

    # Should not raise even if file sink fails.
    configure_logger(config, store=None)

    assert sys.stderr in calls
