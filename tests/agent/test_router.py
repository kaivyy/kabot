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


class _FallbackRouteProvider:
    def __init__(self) -> None:
        self.chat_calls: list[str] = []
        self.fallbacks = ["fallback-model"]

    def get_default_model(self) -> str:
        return "primary-model"

    async def chat(self, *args, **kwargs):
        model = str(kwargs.get("model") or "")
        self.chat_calls.append(model)
        if model == "primary-model":
            raise Exception("429 rate limit")

        class _Resp:
            content = '{"profile":"CODING","turn_category":"action","is_complex":true,"workflow_intent":"skill_creator"}'

        return _Resp()


@pytest.mark.asyncio
async def test_route_weather_query_uses_structured_model_decision_instead_of_fast_parser():
    provider = _StructuredRouteProvider(
        '{"profile":"GENERAL","turn_category":"action","is_complex":true}'
    )
    router = IntentRouter(provider)
    decision = await router.route("check the weather in Cilacap today")
    assert decision.is_complex is True
    assert decision.turn_category == "action"
    assert provider.chat_calls == 1


@pytest.mark.asyncio
async def test_route_set_relative_reminder_uses_structured_model_decision_instead_of_fast_parser():
    provider = _StructuredRouteProvider(
        '{"profile":"GENERAL","turn_category":"action","is_complex":true}'
    )
    router = IntentRouter(provider)
    decision = await router.route("set a reminder in 2 minutes to eat")
    assert decision.is_complex is True
    assert decision.turn_category == "action"
    assert provider.chat_calls == 1


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
async def test_route_temporal_queries_use_structured_model_decision(query, expected_profile):
    provider = _StructuredRouteProvider(
        '{"profile":"GENERAL","turn_category":"chat","is_complex":false}'
    )
    router = IntentRouter(provider)

    decision = await router.route(query)

    assert decision.profile == expected_profile
    assert decision.is_complex is False
    assert getattr(decision, "turn_category", None) == "chat"
    assert provider.chat_calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "what is my preference code? answer with the code only.",
        "what was the code you just remembered? answer with the code only.",
        "what did you save about me? answer briefly.",
    ],
)
async def test_route_memory_recall_queries_use_structured_model_decision(query):
    provider = _StructuredRouteProvider(
        '{"profile":"GENERAL","turn_category":"chat","is_complex":false}'
    )
    router = IntentRouter(provider)

    decision = await router.route(query)

    assert decision.profile == "GENERAL"
    assert getattr(decision, "turn_category", None) == "chat"
    assert provider.chat_calls == 1


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
    provider = _StructuredRouteProvider(
        '{"profile":"GENERAL","turn_category":"action","is_complex":true}'
    )
    router = IntentRouter(provider)

    decision = await router.route("tolong cek suhu cilacap hari ini")

    assert decision.turn_category == "action"
    assert provider.chat_calls == 1


@pytest.mark.asyncio
async def test_route_english_weather_query_no_longer_uses_fast_parser_shortcuts():
    provider = _StructuredRouteProvider(
        '{"profile":"GENERAL","turn_category":"action","is_complex":true}'
    )
    router = IntentRouter(provider)

    decision = await router.route("check the weather in Cilacap today")

    assert decision.turn_category == "action"
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


@pytest.mark.asyncio
async def test_route_skill_creation_spec_turn_surfaces_semantic_workflow_intent():
    provider = _StructuredRouteProvider(
        '{"profile":"CODING","turn_category":"action","is_complex":true,"workflow_intent":"skill_creator"}'
    )
    router = IntentRouter(provider)

    decision = await router.route(
        "bikin skills scrape\n"
        "url: https://arqstorecekid.vercel.app/api/game\n"
        'json: {"endpoint":"/api/game/mlbb-ard","query":"?id=xxxx&zone=xxx"}'
    )

    assert decision.profile == "CODING"
    assert decision.turn_category == "action"
    assert decision.is_complex is True
    assert getattr(decision, "workflow_intent", None) == "skill_creator"
    assert provider.chat_calls == 1


@pytest.mark.asyncio
async def test_route_skill_creation_spec_turn_uses_fallback_model_chain_when_primary_fails():
    provider = _FallbackRouteProvider()
    router = IntentRouter(provider, model="primary-model")

    decision = await router.route(
        "bikin skills scrape\n"
        "url: https://arqstorecekid.vercel.app/api/game\n"
        'json: {"endpoint":"/api/game/mlbb-ard","query":"?id=xxxx&zone=xxx"}'
    )

    assert decision.profile == "CODING"
    assert decision.turn_category == "action"
    assert decision.is_complex is True
    assert getattr(decision, "workflow_intent", None) == "skill_creator"
    assert provider.chat_calls[:2] == ["primary-model", "fallback-model"]
