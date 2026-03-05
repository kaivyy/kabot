import base64
import json

import pytest
from litellm.exceptions import InvalidRequestError

import kabot.providers.litellm_provider as litellm_provider_mod
from kabot.providers.base import LLMResponse
from kabot.providers.litellm_provider import LiteLLMProvider


def test_qwen_portal_model_resolves_to_dashscope_model_name():
    provider = LiteLLMProvider(
        api_key="test-key",
        default_model="qwen-portal/coder-model",
    )

    resolved = provider._resolve_model("qwen-portal/coder-model")
    assert resolved == "dashscope/coder-model"


def test_litellm_runtime_setup_is_deferred_until_first_model_call():
    provider = LiteLLMProvider(
        api_key="test-key",
        default_model="openai-codex/gpt-5.3-codex",
    )

    assert provider._litellm_runtime_ready is False


@pytest.mark.asyncio
async def test_chat_falls_back_on_auth_invalid_request_error(monkeypatch):
    provider = LiteLLMProvider(
        api_key="test-key",
        default_model="openai-codex/gpt-5.3-codex",
        fallbacks=["groq/llama3-70b-8192"],
    )

    calls: list[str] = []

    async def _fake_execute(model, messages, tools, max_tokens, temperature):
        calls.append(model)
        if model == "openai-codex/gpt-5.3-codex":
            raise InvalidRequestError(
                message="Authentication failed: 401 Client Error: Unauthorized",
                llm_provider="openai-codex",
                model=model,
            )
        return LLMResponse(content="fallback-ok")

    monkeypatch.setattr(provider, "_execute_model_call", _fake_execute)

    response = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="openai-codex/gpt-5.3-codex",
    )

    assert response.content == "fallback-ok"
    assert calls == ["openai-codex/gpt-5.3-codex", "groq/llama3-70b-8192"]


@pytest.mark.asyncio
async def test_chat_keeps_fail_fast_for_format_invalid_request(monkeypatch):
    provider = LiteLLMProvider(
        api_key="test-key",
        default_model="openai-codex/gpt-5.3-codex",
        fallbacks=["groq/llama3-70b-8192"],
    )

    calls: list[str] = []

    async def _fake_execute(model, messages, tools, max_tokens, temperature):
        calls.append(model)
        raise InvalidRequestError(
            message="Invalid request: malformed tool schema payload",
            llm_provider="openai-codex",
            model=model,
        )

    monkeypatch.setattr(provider, "_execute_model_call", _fake_execute)

    with pytest.raises(InvalidRequestError):
        await provider.chat(
            messages=[{"role": "user", "content": "hello"}],
            model="openai-codex/gpt-5.3-codex",
        )

    assert calls == ["openai-codex/gpt-5.3-codex"]


@pytest.mark.asyncio
async def test_chat_uses_provider_specific_key_for_cross_provider_fallback(monkeypatch):
    provider = LiteLLMProvider(
        api_key="openai-jwt-token",
        default_model="openai-codex/gpt-5.3-codex",
        fallbacks=["groq/llama3-70b-8192"],
        provider_api_keys={
            "openai-codex": "openai-jwt-token",
            "groq": "groq-test-key",
        },
    )

    async def _fake_codex(*_args, **_kwargs):
        raise InvalidRequestError(
            message="Authentication failed: 401 Client Error: Unauthorized",
            llm_provider="openai-codex",
            model="openai-codex/gpt-5.3-codex",
        )

    monkeypatch.setattr(provider, "_chat_openai_codex", _fake_codex)

    captured: dict[str, str] = {}

    async def _fake_acompletion(**kwargs):
        captured["api_key"] = kwargs.get("api_key")
        captured["model"] = kwargs.get("model")
        return type(
            "Resp",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type("Msg", (), {"content": "fallback-ok", "tool_calls": []})(),
                            "finish_reason": "stop",
                        },
                    )()
                ],
                "usage": type(
                    "Usage",
                    (),
                    {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                )(),
            },
        )()

    monkeypatch.setattr("kabot.providers.litellm_provider.acompletion", _fake_acompletion)

    response = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="openai-codex/gpt-5.3-codex",
    )

    assert response.content == "fallback-ok"
    assert captured["api_key"] == "groq-test-key"
    assert captured["model"] == "groq/llama3-70b-8192"


@pytest.mark.asyncio
async def test_chat_temporarily_skips_model_after_auth_failure(monkeypatch):
    provider = LiteLLMProvider(
        api_key="test-key",
        default_model="openai-codex/gpt-5.3-codex",
        fallbacks=["groq/llama3-70b-8192"],
    )
    provider._auth_failure_cooldown_seconds = 60

    calls: list[str] = []

    async def _fake_execute(model, messages, tools, max_tokens, temperature):
        calls.append(model)
        if model == "openai-codex/gpt-5.3-codex":
            raise InvalidRequestError(
                message="Authentication failed: 401 Client Error: Unauthorized",
                llm_provider="openai-codex",
                model=model,
            )
        return LLMResponse(content="fallback-ok")

    monkeypatch.setattr(provider, "_execute_model_call", _fake_execute)

    first = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="openai-codex/gpt-5.3-codex",
    )
    second = await provider.chat(
        messages=[{"role": "user", "content": "hello-again"}],
        model="openai-codex/gpt-5.3-codex",
    )

    assert first.content == "fallback-ok"
    assert second.content == "fallback-ok"
    assert calls == [
        "openai-codex/gpt-5.3-codex",
        "groq/llama3-70b-8192",
        "groq/llama3-70b-8192",
    ]


@pytest.mark.asyncio
async def test_chat_retries_primary_again_after_auth_cooldown_expires(monkeypatch):
    provider = LiteLLMProvider(
        api_key="test-key",
        default_model="openai-codex/gpt-5.3-codex",
        fallbacks=["groq/llama3-70b-8192"],
    )
    provider._auth_failure_cooldown_seconds = 10

    fake_now = {"t": 1000.0}
    monkeypatch.setattr(litellm_provider_mod.time, "time", lambda: fake_now["t"])

    calls: list[str] = []

    async def _fake_execute(model, messages, tools, max_tokens, temperature):
        calls.append(model)
        if model == "openai-codex/gpt-5.3-codex":
            raise InvalidRequestError(
                message="Authentication failed: 401 Client Error: Unauthorized",
                llm_provider="openai-codex",
                model=model,
            )
        return LLMResponse(content="fallback-ok")

    monkeypatch.setattr(provider, "_execute_model_call", _fake_execute)

    first = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="openai-codex/gpt-5.3-codex",
    )
    fake_now["t"] += 11.0
    second = await provider.chat(
        messages=[{"role": "user", "content": "hello-after-cooldown"}],
        model="openai-codex/gpt-5.3-codex",
    )

    assert first.content == "fallback-ok"
    assert second.content == "fallback-ok"
    assert calls == [
        "openai-codex/gpt-5.3-codex",
        "groq/llama3-70b-8192",
        "openai-codex/gpt-5.3-codex",
        "groq/llama3-70b-8192",
    ]


@pytest.mark.asyncio
async def test_chat_skips_openai_codex_when_jwt_already_expired(monkeypatch):
    def _b64(data: dict) -> str:
        raw = json.dumps(data).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    expired_jwt = f"{_b64({'alg': 'RS256', 'typ': 'JWT'})}.{_b64({'exp': 1})}.signature"

    provider = LiteLLMProvider(
        api_key="test-key",
        default_model="openai-codex/gpt-5.3-codex",
        fallbacks=["groq/llama3-70b-8192"],
        provider_api_keys={
            "openai-codex": expired_jwt,
            "groq": "groq-test-key",
        },
    )
    provider._auth_failure_cooldown_seconds = 60

    calls: list[str] = []

    async def _fake_execute(model, messages, tools, max_tokens, temperature):
        calls.append(model)
        if model.startswith("openai-codex/"):
            raise AssertionError("expired openai-codex should be skipped before request")
        return LLMResponse(content="fallback-ok")

    monkeypatch.setattr(provider, "_execute_model_call", _fake_execute)

    result = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="openai-codex/gpt-5.3-codex",
    )

    assert result.content == "fallback-ok"
    assert calls == ["groq/llama3-70b-8192"]

