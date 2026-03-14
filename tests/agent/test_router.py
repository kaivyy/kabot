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


class _StructuredRouteProvider:
    def __init__(self, content: str) -> None:
        self.content = content
        self.chat_calls = 0

    def get_default_model(self) -> str:
        return "openai-codex/gpt-5.3-codex"

    async def chat(self, *args, **kwargs):
        self.chat_calls += 1

        class _Resp:
            def __init__(self, content: str) -> None:
                self.content = content

        return _Resp(self.content)


@pytest.mark.asyncio
async def test_route_weather_query_is_complex():
    router = IntentRouter(_ChatOnlyProvider())
    decision = await router.route("check the weather in Cilacap today")
    assert decision.is_complex is True


@pytest.mark.asyncio
async def test_route_set_relative_reminder_is_complex():
    router = IntentRouter(_ChatOnlyProvider())
    decision = await router.route("set a reminder in 2 minutes to eat")
    assert decision.is_complex is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected_profile"),
    [
        ("what day is it now?", "GENERAL"),
        ("what date is it today?", "GENERAL"),
        ("what time is it right now?", "GENERAL"),
        ("what timezone am I in?", "GENERAL"),
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
        "what was the code you just remembered? answer with the code only.",
        "what did you save about me? answer briefly.",
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

    decision = await router.route("what is the average human IQ")

    assert decision.is_complex is False
    assert getattr(decision, "turn_category", None) == "chat"
    assert provider.chat_calls == 1


@pytest.mark.asyncio
async def test_route_indonesian_weather_query_no_longer_uses_fast_parser_shortcuts():
    provider = _ChatOnlyProvider()
    router = IntentRouter(provider)

    await router.route("tolong cek suhu cilacap hari ini")

    assert provider.chat_calls == 1


@pytest.mark.asyncio
async def test_route_multilingual_action_turn_uses_structured_model_decision():
    provider = _StructuredRouteProvider(
        '{"profile":"GENERAL","turn_category":"action","is_complex":true}'
    )
    router = IntentRouter(provider)

    decision = await router.route("このチャットに tes.md を送って")

    assert decision.profile == "GENERAL"
    assert decision.turn_category == "action"
    assert decision.is_complex is True
    assert provider.chat_calls == 1


@pytest.mark.asyncio
async def test_route_multilingual_project_inspection_turn_sets_filesystem_grounding_mode():
    provider = _StructuredRouteProvider(
        '{"profile":"GENERAL","turn_category":"action","is_complex":true,"grounding_mode":"filesystem_inspection"}'
    )
    router = IntentRouter(provider)

    decision = await router.route("この openclaw フォルダの中身を見て、どんなアプリか説明して")

    assert decision.profile == "GENERAL"
    assert decision.turn_category == "action"
    assert decision.grounding_mode == "filesystem_inspection"
    assert decision.is_complex is True
    assert provider.chat_calls == 1
