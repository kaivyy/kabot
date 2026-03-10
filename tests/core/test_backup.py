import json
import zipfile
from pathlib import Path

from kabot.core.backup import create_backup


def test_create_backup_writes_zip_with_manifest(tmp_path):
    config_dir = tmp_path / ".kabot"
    credentials_dir = config_dir / "credentials"
    sessions_dir = config_dir / "sessions"
    config_dir.mkdir()
    credentials_dir.mkdir()
    sessions_dir.mkdir()

    (config_dir / "config.json").write_text('{"model":"openai/gpt-5.4"}', encoding="utf-8")
    (credentials_dir / "token.json").write_text('{"token":"secret"}', encoding="utf-8")
    (sessions_dir / "chat.jsonl").write_text("ignored", encoding="utf-8")

    archive_path = Path(create_backup(config_dir, dest_dir=tmp_path, only_config=True))

    assert archive_path.exists()
    assert archive_path.suffix == ".zip"

    with zipfile.ZipFile(archive_path) as zf:
        names = set(zf.namelist())
        assert "config.json" in names
        assert "credentials/token.json" in names
        assert "manifest.json" in names
        assert "sessions/chat.jsonl" not in names

        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest["only_config"] is True
        archived_paths = {entry["path"] for entry in manifest["files"]}
        assert archived_paths == {"config.json", "credentials/token.json"}
