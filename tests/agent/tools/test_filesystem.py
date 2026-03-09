from pathlib import Path

import pytest

from kabot.agent.tools.filesystem import ListDirTool


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
