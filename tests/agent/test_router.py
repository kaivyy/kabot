import pytest

from kabot.agent.router import IntentRouter


class _ChatOnlyProvider:
    def __init__(self) -> None:
        self.chat_calls = 0

    def get_default_model(self) -> str:
        return "openai-codex/gpt-5.3-codex"

    async def chat(self, *args, **kwargs):
        self.chat_calls += 1
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected_profile"),
    [
        ("hari apa sekarang?", "GENERAL"),
        ("今天星期几？", "GENERAL"),
        ("ตอนนี้วันอะไร", "GENERAL"),
        ("今日は何曜日？", "GENERAL"),
    ],
)
async def test_route_temporal_queries_skip_llm_classification(query, expected_profile):
    provider = _ChatOnlyProvider()
    router = IntentRouter(provider)

    decision = await router.route(query)

    assert decision.profile == expected_profile
    assert decision.is_complex is False
    assert provider.chat_calls == 0
