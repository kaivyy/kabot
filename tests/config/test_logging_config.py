from kabot.config.schema import LoggingConfig, Config
import pytest

def test_logging_config_defaults():
    # This should fail initially because LoggingConfig is not defined
    try:
        cfg = LoggingConfig()
        assert cfg.enabled is True
        assert cfg.level == "INFO"
        assert cfg.rotation == "10 MB"
        assert cfg.retention == "7 days"
        assert cfg.db_retention_days == 30
    except NameError:
        pytest.fail("LoggingConfig not defined")
    except ImportError:
        pytest.fail("LoggingConfig not importable")

def test_config_integration():
    # This should fail if logging field is missing in Config
    try:
        cfg = Config()
        assert cfg.logging.enabled is True
    except AttributeError:
        pytest.fail("Config has no logging field")
