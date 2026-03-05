from pathlib import Path

import pytest

from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.tools.knowledge import KnowledgeLearnTool
from kabot.agent.tools.memory import GetMemoryTool, ListRemindersTool, SaveMemoryTool


class _MemorySaveOk:
    async def remember_fact(self, **kwargs):
        return True


class _MemorySaveFail:
    async def remember_fact(self, **kwargs):
        return False


class _MetadataEmpty:
    def get_facts(self, limit=10):
        return []

    def get_message_chain(self, limit=5):
        return []


class _MemorySearchEmpty:
    metadata = _MetadataEmpty()

    async def search_memory(self, query: str, limit: int = 5):
        return []


@pytest.mark.asyncio
async def test_knowledge_tool_localizes_file_not_found(tmp_path: Path):
    tool = KnowledgeLearnTool(workspace=tmp_path)
    missing = tmp_path / "missing.pdf"

    result = await tool.execute(file_path=str(missing))
    assert result == i18n_t("knowledge.file_not_found", str(missing), path=str(missing))


@pytest.mark.asyncio
async def test_knowledge_tool_localizes_extract_failure(monkeypatch, tmp_path: Path):
    tool = KnowledgeLearnTool(workspace=tmp_path)
    source = tmp_path / "doc.txt"
    source.write_text("hello", encoding="utf-8")

    def _boom(path: Path) -> str:
        raise RuntimeError("parse fail")

    monkeypatch.setattr("kabot.utils.document_parser.DocumentParser.extract_text", _boom)

    result = await tool.execute(file_path=str(source))
    assert result == i18n_t("knowledge.extract_failed", str(source), error="parse fail")


@pytest.mark.asyncio
async def test_knowledge_tool_localizes_empty_readable_text(monkeypatch, tmp_path: Path):
    tool = KnowledgeLearnTool(workspace=tmp_path)
    source = tmp_path / "doc.txt"
    source.write_text("hello", encoding="utf-8")

    monkeypatch.setattr("kabot.utils.document_parser.DocumentParser.extract_text", lambda path: "hello")
    monkeypatch.setattr("kabot.utils.document_parser.DocumentParser.chunk_text", lambda text, chunk_size=1500, overlap=300: [])

    result = await tool.execute(file_path=str(source))
    assert result == i18n_t("knowledge.no_readable_text", str(source))


@pytest.mark.asyncio
async def test_save_memory_tool_localizes_missing_manager():
    tool = SaveMemoryTool(memory_manager=None)
    prompt = "simpan ini sebagai catatan"
    result = await tool.execute(content=prompt, category="fact")
    assert result == i18n_t("memory.manager_unavailable", prompt)


@pytest.mark.asyncio
async def test_get_memory_tool_localizes_missing_manager():
    tool = GetMemoryTool(memory_manager=None)
    prompt = "ambil memori saya"
    result = await tool.execute(query=prompt)
    assert result == i18n_t("memory.manager_unavailable", prompt)


@pytest.mark.asyncio
async def test_save_memory_tool_localizes_success_message():
    prompt = "tolong simpan preferensi kopi saya"
    tool = SaveMemoryTool(memory_manager=_MemorySaveOk())

    result = await tool.execute(content=prompt, category="preference")
    assert result == i18n_t(
        "memory.save_success",
        prompt,
        category="preference",
        preview=f"{prompt[:100]}...",
    )


@pytest.mark.asyncio
async def test_save_memory_tool_localizes_failed_save():
    prompt = "catat ini sebagai fakta"
    tool = SaveMemoryTool(memory_manager=_MemorySaveFail())

    result = await tool.execute(content=prompt, category="fact")
    assert result == i18n_t("memory.save_category_failed", prompt, category="fact")


@pytest.mark.asyncio
async def test_get_memory_tool_localizes_empty_search():
    prompt = "ingat ga ya"
    tool = GetMemoryTool(memory_manager=_MemorySearchEmpty())

    result = await tool.execute(query=prompt)
    assert result == i18n_t("memory.search.no_results", prompt, query=prompt)


@pytest.mark.asyncio
async def test_list_reminders_tool_localizes_empty_state():
    tool = ListRemindersTool(cron_service=None)
    result = await tool.execute()
    assert result == i18n_t("memory.reminders.none")
