from kabot.providers.litellm_provider import LiteLLMProvider


def test_qwen_portal_model_resolves_to_dashscope_model_name():
    provider = LiteLLMProvider(
        api_key="test-key",
        default_model="qwen-portal/coder-model",
    )

    resolved = provider._resolve_model("qwen-portal/coder-model")
    assert resolved == "dashscope/coder-model"
