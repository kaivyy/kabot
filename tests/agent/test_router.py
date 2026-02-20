import pytest

from kabot.agent.router import IntentRouter


class _ChatOnlyProvider:
    def get_default_model(self) -> str:
        return "openai-codex/gpt-5.3-codex"

    async def chat(self, *args, **kwargs):
        class _Resp:
            content = "CHAT"

        return _Resp()


@pytest.mark.asyncio
async def test_route_weather_query_is_complex():
    router = IntentRouter(_ChatOnlyProvider())
    decision = await router.route("tolong cek suhu cilacap hari ini")
    assert decision.is_complex is True


@pytest.mark.asyncio
async def test_route_set_relative_reminder_is_complex():
    router = IntentRouter(_ChatOnlyProvider())
    decision = await router.route("set sekarang 2 menit lagi makan")
    assert decision.is_complex is True
