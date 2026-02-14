
import asyncio
import sys
from kabot.agent.router import IntentRouter, RouteDecision

# Simplified MockProvider
class MockProvider:
    def get_default_model(self):
        return "mock-model"
    async def chat(self, *args, **kwargs):
        # Return a dummy object with content attribute
        return type("Response", (), {"content": "GENERAL"})()

async def main():
    print("Testing routing logic...")
    router = IntentRouter(MockProvider())
    
    test_cases = [
        "ingatkan 1 menit lagi waktunya pulang",
        "remind me in 1 minute",
        "halo apa kabar",
        "buatkan saya puisi",
        "check the logs",
        "jadwalkan meeting besok"
    ]
    
    for text in test_cases:
        decision = await router.route(text)
        status = "COMPLEX (Tools enabled)" if decision.is_complex else "SIMPLE (No tools)"
        print(f"Input: '{text}' -> {status}")
        
        # Validation
        is_action = any(k in text for k in ["ingatkan", "remind", "check", "jadwalkan"])
        if is_action and not decision.is_complex:
            print(f"FAIL: '{text}' should be COMPLEX!")
            # Don't exit, just log failure
        elif not is_action and "halo" in text and decision.is_complex:
            print(f"FAIL: '{text}' should be SIMPLE!")

if __name__ == "__main__":
    asyncio.run(main())
