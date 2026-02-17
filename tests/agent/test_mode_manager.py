# tests/agent/test_mode_manager.py
def test_set_mode(tmp_path):
    from kabot.agent.mode_manager import ModeManager

    manager = ModeManager(tmp_path / "mode_config.json")
    manager.set_mode("user:telegram:123", "multi")

    mode = manager.get_mode("user:telegram:123")
    assert mode == "multi"

def test_default_mode(tmp_path):
    from kabot.agent.mode_manager import ModeManager

    manager = ModeManager(tmp_path / "mode_config.json")
    mode = manager.get_mode("user:telegram:999")
    assert mode == "single"  # default
