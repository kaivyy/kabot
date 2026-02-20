import base64
import json

import pytest

import kabot.providers.litellm_provider as litellm_provider_module
from kabot.providers.chatgpt_backend_client import (
    build_chatgpt_request,
    extract_content_from_event,
)
from kabot.providers.litellm_provider import LiteLLMProvider


def _fake_jwt(account_id: str = "acc_test") -> str:
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8")
    ).decode("utf-8").rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {"https://api.openai.com/auth": {"chatgpt_account_id": account_id}}
        ).encode("utf-8")
    ).decode("utf-8").rstrip("=")
    return f"{header}.{payload}.sig"


def test_extract_content_from_event_supports_output_text_delta():
    event = {"type": "response.output_text.delta", "delta": "Hello"}
    assert extract_content_from_event(event) == "Hello"


def test_extract_content_from_event_supports_output_text_part():
    event = {
        "type": "response.content_part.added",
        "part": {"type": "output_text", "text": "Hello"},
    }
    assert extract_content_from_event(event) == "Hello"


@pytest.mark.asyncio
async def test_chat_openai_codex_uses_streaming_payload_and_parses_output_text(monkeypatch):
    captured: dict[str, object] = {}
    sse = "\n\n".join(
        [
            'data: {"type":"response.content_part.added","part":{"type":"output_text","text":""}}',
            'data: {"type":"response.output_text.delta","delta":"Hello"}',
        ]
    ) + "\n\n"

    class DummyResponse:
        def __init__(self, text: str):
            self.status_code = 200
            self.text = text

        def raise_for_status(self):
            return None

    def fake_post(**kwargs):
        captured.update(kwargs)
        return DummyResponse(sse)

    monkeypatch.setattr(litellm_provider_module.requests, "post", fake_post)

    provider = LiteLLMProvider(
        api_key=_fake_jwt(),
        default_model="openai-codex/gpt-5.3-codex",
    )
    response = await provider._chat_openai_codex(
        messages=[{"role": "user", "content": "Say hello"}],
        tools=None,
        model="openai-codex/gpt-5.3-codex",
        max_tokens=128,
        temperature=0.2,
    )

    body = captured.get("json")
    if body is None:
        body = json.loads(captured["data"])  # type: ignore[index]

    assert isinstance(body, dict)
    assert body.get("stream") is True
    assert "temperature" not in body
    assert response.content == "Hello"


@pytest.mark.asyncio
async def test_chat_openai_codex_decodes_sse_utf8_from_raw_bytes(monkeypatch):
    target_text = 'Halo! 👋 "2 menit lagi makan".'
    sse_utf8 = 'data: {"type":"response.output_text.delta","delta":"Halo! 👋 \\"2 menit lagi makan\\"."}\n\n'
    sse_bytes = sse_utf8.encode("utf-8")

    class DummyResponse:
        def __init__(self):
            self.status_code = 200
            self.content = sse_bytes
            # Simulate requests wrong charset decode (mojibake source).
            self.text = sse_bytes.decode("latin-1")

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        litellm_provider_module.requests,
        "post",
        lambda **kwargs: DummyResponse(),
    )

    provider = LiteLLMProvider(
        api_key=_fake_jwt(),
        default_model="openai-codex/gpt-5.3-codex",
    )
    response = await provider._chat_openai_codex(
        messages=[{"role": "user", "content": "Say hello"}],
        tools=None,
        model="openai-codex/gpt-5.3-codex",
        max_tokens=128,
        temperature=0.2,
    )

    assert response.content == target_text


@pytest.mark.asyncio
async def test_chat_openai_codex_sends_tools_and_parses_function_call(monkeypatch):
    captured: dict[str, object] = {}
    sse = (
        'data: {"type":"response.output_item.added","item":{"type":"function_call","id":"fc_123",'
        '"call_id":"call_123","name":"weather","arguments":"{\\"location\\":\\"Cilacap\\"}"}}\n\n'
    )

    class DummyResponse:
        def __init__(self, text: str):
            self.status_code = 200
            self.text = text

        def raise_for_status(self):
            return None

    def fake_post(**kwargs):
        captured.update(kwargs)
        return DummyResponse(sse)

    monkeypatch.setattr(litellm_provider_module.requests, "post", fake_post)

    provider = LiteLLMProvider(
        api_key=_fake_jwt(),
        default_model="openai-codex/gpt-5.3-codex",
    )
    response = await provider._chat_openai_codex(
        messages=[{"role": "user", "content": "cek suhu Cilacap"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "weather",
                    "description": "Get weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"},
                        },
                        "required": ["location"],
                    },
                },
            }
        ],
        model="openai-codex/gpt-5.3-codex",
        max_tokens=128,
        temperature=0.2,
    )

    body = captured.get("json")
    if body is None:
        body = json.loads(captured["data"])  # type: ignore[index]

    assert isinstance(body, dict)
    assert "tools" in body
    assert body["tools"][0]["type"] == "function"  # type: ignore[index]
    assert body["tools"][0]["name"] == "weather"  # type: ignore[index]

    assert response.tool_calls
    assert response.tool_calls[0].name == "weather"
    assert response.tool_calls[0].arguments == {"location": "Cilacap"}


def test_build_chatgpt_request_converts_tool_result_to_function_call_output():
    body = build_chatgpt_request(
        model="gpt-5.3-codex",
        messages=[
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_weather_1",
                        "type": "function",
                        "function": {
                            "name": "weather",
                            "arguments": "{\"location\":\"Cilacap\"}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_weather_1",
                "name": "weather",
                "content": "27C sunny",
            },
        ],
    )

    assert body["input"][0]["type"] == "function_call"  # type: ignore[index]
    assert body["input"][0]["call_id"] == "call_weather_1"  # type: ignore[index]
    assert body["input"][0]["name"] == "weather"  # type: ignore[index]
    assert body["input"][1]["type"] == "function_call_output"  # type: ignore[index]
    assert body["input"][1]["call_id"] == "call_weather_1"  # type: ignore[index]
    assert body["input"][1]["output"] == "27C sunny"  # type: ignore[index]


def test_build_chatgpt_request_converts_legacy_function_call_message():
    body = build_chatgpt_request(
        model="gpt-5.3-codex",
        messages=[
            {
                "role": "assistant",
                "function_call": {
                    "name": "cron",
                    "arguments": "{\"action\":\"list\"}",
                },
            }
        ],
    )

    assert body["input"][0]["type"] == "function_call"  # type: ignore[index]
    assert body["input"][0]["call_id"].startswith("call_")  # type: ignore[index]
    assert body["input"][0]["name"] == "cron"  # type: ignore[index]
    assert body["input"][0]["arguments"] == "{\"action\":\"list\"}"  # type: ignore[index]


def test_build_chatgpt_request_adds_default_instructions_when_missing():
    body = build_chatgpt_request(
        model="gpt-5.3-codex",
        messages=[{"role": "user", "content": "hello"}],
    )

    assert isinstance(body.get("instructions"), str)
    assert body["instructions"].strip() != ""
