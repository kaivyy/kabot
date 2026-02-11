from letta_client import Letta
import sys

try:
    client = Letta(api_key="sk-let-OGZlZTY2M2ItYmYyZC00Y2ViLTllMTMtZDFmMTllYTBlZTkwOjJlZDUyN2U4LWY0NzYtNGY4NS1hNTE2LWY1MmE0ZWJiNjMyMA==")

    print("Listing existing agents...")
    agents_page = client.agents.list()

    # Iterate directly
    count = 0
    for agent in agents_page:
        print(f"- Name: {agent.name}, ID: {agent.id}, Model: {agent.model}")
        count += 1

    print(f"Total agents found: {count}")

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
