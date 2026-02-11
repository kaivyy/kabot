from letta_client import Letta
import sys

try:
    client = Letta(api_key="sk-let-OGZlZTY2M2ItYmYyZC00Y2ViLTllMTMtZDFmMTllYTBlZTkwOjJlZDUyN2U4LWY0NzYtNGY4NS1hNTE2LWY1MmE0ZWJiNjMyMA==")

    print("Creating agent...")
    agent = client.agents.create(
        model="gpt-5.1-codex-mini",  # Using the model from config
        memory_blocks=[
            {
                "label": "persona",
                "value": "You are Kabot, a helpful AI assistant with advanced long-term memory.",
            },
            {
                "label": "human",
                "value": "User ID: Owner\nThis user is chatting via Kabot.",
            },
        ],
    )

    print(f"SUCCESS: Agent created with ID: {agent.id}")

    # Save to a file so we can read it
    with open("created_agent_id.txt", "w") as f:
        f.write(agent.id)

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
