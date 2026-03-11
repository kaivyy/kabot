import zipfile
from pathlib import Path

import pytest

from kabot.agent.tools.filesystem import ArchivePathTool, FindFilesTool, ListDirTool


@pytest.mark.asyncio
async def test_list_dir_tool_respects_limit(tmp_path: Path):
    for idx in range(1, 8):
        (tmp_path / f"item{idx}.txt").write_text(str(idx), encoding="utf-8")

    tool = ListDirTool()

    result = await tool.execute(str(tmp_path), limit=5)
    lines = [line for line in result.splitlines() if line.strip()]

    assert len(lines) == 5
    assert lines[0].endswith("item1.txt")
    assert lines[-1].endswith("item5.txt")


@pytest.mark.asyncio
async def test_find_files_tool_returns_matching_files_and_folders(tmp_path: Path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "report-q1.pdf").write_text("q1", encoding="utf-8")
    (tmp_path / "report-assets").mkdir()
    (tmp_path / "notes.txt").write_text("notes", encoding="utf-8")

    tool = FindFilesTool(allowed_dir=tmp_path)

    result = await tool.execute(query="report", path=str(tmp_path), kind="any", limit=10)

    assert "report-q1.pdf" in result
    assert "report-assets" in result
    assert "notes.txt" not in result


@pytest.mark.asyncio
async def test_find_files_tool_respects_kind_and_limit(tmp_path: Path):
    for idx in range(1, 5):
        (tmp_path / f"report-{idx}.txt").write_text(str(idx), encoding="utf-8")
    (tmp_path / "report-folder").mkdir()

    tool = FindFilesTool(allowed_dir=tmp_path)

    result = await tool.execute(query="report", kind="file", limit=2)
    lines = [line for line in result.splitlines() if line.strip()]

    assert len(lines) == 2
    assert all("report-" in line for line in lines)
    assert all("report-folder" not in line for line in lines)


@pytest.mark.asyncio
async def test_archive_path_tool_creates_zip_from_directory(tmp_path: Path):
    source_dir = tmp_path / "project-assets"
    nested_dir = source_dir / "nested"
    nested_dir.mkdir(parents=True)
    (source_dir / "README.txt").write_text("hello", encoding="utf-8")
    (nested_dir / "poster.txt").write_text("promo", encoding="utf-8")

    tool = ArchivePathTool(allowed_dir=tmp_path)

    result = await tool.execute(path=str(source_dir))

    archive_path = tmp_path / "project-assets.zip"
    assert str(archive_path) in result
    assert archive_path.exists()
    with zipfile.ZipFile(archive_path, "r") as archive:
        names = sorted(archive.namelist())
    assert "project-assets/README.txt" in names
    assert "project-assets/nested/poster.txt" in names
