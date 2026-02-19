import asyncio
from kabot.config.loader import load_config
from kabot.providers.litellm_provider import LiteLLMProvider

async def test_openai():
    config = load_config()
    
    # Force OpenAI provider for this test
    # We look for a model that starts with "openai/" or just use gpt-4o as default test
    print("Testing OpenAI connection...")
    
    # Manually construct provider from config
    p = config.providers.openai
    
    if not p:
        print("❌ OpenAI provider not found in config")
        return

    # Check for API Key or OAuth Token
    api_key = p.api_key
    if not api_key and p.profiles and p.active_profile in p.profiles:
        profile = p.profiles[p.active_profile]
        api_key = profile.api_key or profile.oauth_token
        
    if not api_key:
        print(f"❌ No API key found for OpenAI (Active Profile: {p.active_profile})")
        return

    print(f"✅ Found API credential for profile: {p.active_profile}")

    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=p.api_base,
        default_model="openai/gpt-4o-mini", # Use a cheap model for testing
        extra_headers=p.extra_headers,
        provider_name="openai"
    )

    try:
        response = await provider.chat(
            messages=[{"role": "user", "content": "Hello, are you working?"}],
            model="openai/gpt-4o-mini"
        )
        print("\n🎉 OpenAI Connection Successful!")
        print(f"Response: {response.content}")
    except Exception as e:
        print(f"\n❌ OpenAI Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_openai())
