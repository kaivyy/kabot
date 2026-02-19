from kabot.plugins.scaffold import scaffold_plugin


def test_scaffold_creates_dynamic_plugin(tmp_path):
    out = scaffold_plugin(tmp_path, name="meta_bridge", kind="dynamic")
    assert (out / "plugin.json").exists()
    assert (out / "main.py").exists()
