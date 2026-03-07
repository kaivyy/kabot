from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kabot.agent.tools.image_gen import ImageGenTool


def _make_config(*, default_model: str = "openai-codex/gpt-5.3-codex", api_key: str = "sk-test"):
    return SimpleNamespace(
        providers=SimpleNamespace(
            openai=SimpleNamespace(api_key=""),
            openai_codex=SimpleNamespace(api_key=""),
            gemini=SimpleNamespace(api_key=""),
        ),
        agents=SimpleNamespace(defaults=SimpleNamespace(model=default_model)),
        get_api_key=lambda model=None: api_key if model else api_key,
        get_api_base=lambda model=None: None,
    )


@pytest.mark.asyncio
async def test_image_gen_uses_runtime_openai_codex_credentials(tmp_path):
    config = _make_config()
    tool = ImageGenTool(workspace=Path(tmp_path), config=config)
    tool._generate_openai = AsyncMock(return_value="Image generated via OpenAI: test.png")

    result = await tool.execute(prompt="car in forest")

    assert "Image generated via OpenAI" in result
    tool._generate_openai.assert_awaited_once()


@pytest.mark.asyncio
async def test_image_gen_missing_provider_returns_clear_setup_error(tmp_path):
    config = _make_config(api_key="")
    tool = ImageGenTool(workspace=Path(tmp_path), config=config)

    result = await tool.execute(prompt="buatkan gambar mobil di hutan")

    assert "api key" in result.lower()
    assert "openai" in result.lower() or "gemini" in result.lower()
    assert "kabot auth login" in result.lower()
