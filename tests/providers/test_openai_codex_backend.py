import base64
import json

import pytest

import kabot.providers.litellm_provider as litellm_provider_module
from kabot.providers.chatgpt_backend_client import extract_content_from_event
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
