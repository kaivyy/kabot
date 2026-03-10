from pathlib import Path

import pytest

from kabot.config.loader import load_config


def test_load_config_raises_clean_value_error_on_malformed_json(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{ invalid_json: ]", encoding="utf-8")

    with pytest.raises(ValueError, match="CRITICAL: Configuration file is malformed"):
        load_config(config_path)


def test_load_config_keeps_default_behavior_for_missing_file(tmp_path: Path):
    cfg = load_config(tmp_path / "missing.json")

    assert cfg is not None
