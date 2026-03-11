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
    assert getattr(decision, "turn_category", None) == "chat"
    assert provider.chat_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "what is my preference code? answer with the code only.",
        "kode preferensiku apa? jawab kode saja.",
        "我刚才让你记住的代码是什么？只回答代码。",
    ],
)
async def test_route_memory_recall_queries_skip_llm_coding_misclassification(query):
    provider = _ChatOnlyProvider()
    router = IntentRouter(provider)

    decision = await router.route(query)

    assert decision.profile == "GENERAL"
    assert getattr(decision, "turn_category", None) == "chat"
    assert provider.chat_calls == 0


@pytest.mark.asyncio
async def test_route_general_knowledge_query_marks_chat_turn_category():
    provider = _ChatOnlyProvider()
    router = IntentRouter(provider)

    decision = await router.route("IQ MANUSIA RATA RATA BERAPA")

    assert decision.is_complex is False
    assert getattr(decision, "turn_category", None) == "chat"
    assert provider.chat_calls == 1
