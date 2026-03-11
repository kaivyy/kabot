
from kabot.config.loader import get_config_path, load_config, save_config
from kabot.config.schema import Config


def test_get_config_path_uses_kabot_config_env(monkeypatch, tmp_path):
    custom_path = tmp_path / "custom-config.json"
    monkeypatch.setenv("KABOT_CONFIG", str(custom_path))

    assert get_config_path() == custom_path


def test_load_config_uses_kabot_config_env(monkeypatch, tmp_path):
    custom_path = tmp_path / "custom-config.json"
    cfg = Config.model_validate(
        {
            "mcp": {
                "enabled": True,
                "servers": {
                    "local": {
                        "transport": "stdio",
                        "command": "python",
                        "args": ["-m", "example"],
                    }
                },
            }
        }
    )
    save_config(cfg, custom_path)
    monkeypatch.setenv("KABOT_CONFIG", str(custom_path))

    loaded = load_config()

    assert loaded.mcp.enabled is True
    assert "local" in loaded.mcp.servers

