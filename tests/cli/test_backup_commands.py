import zipfile

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


def test_backup_create_command_exists(runner):
    from kabot.cli.commands import app

    result = runner.invoke(app, ["backup", "create", "--help"])

    assert result.exit_code == 0
    assert "--source-dir" in result.output
    assert "--dest-dir" in result.output


def test_backup_create_command_writes_archive(tmp_path, runner):
    from kabot.cli.commands import app

    source_dir = tmp_path / ".kabot"
    dest_dir = tmp_path / "backups"
    source_dir.mkdir()
    dest_dir.mkdir()
    (source_dir / "config.json").write_text('{"model":"openai/gpt-5.4"}', encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "backup",
            "create",
            "--source-dir",
            str(source_dir),
            "--dest-dir",
            str(dest_dir),
            "--only-config",
        ],
    )

    assert result.exit_code == 0
    archives = list(dest_dir.glob("kabot_backup_*.zip"))
    assert len(archives) == 1
    assert str(archives[0]) in result.output

    with zipfile.ZipFile(archives[0]) as zf:
        assert "config.json" in set(zf.namelist())
