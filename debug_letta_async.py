import asyncio
import os
from letta_client import AsyncLetta

async def main():
    client = AsyncLetta(
        api_key="sk-let-OGZlZTY2M2ItYmYyZC00Y2ViLTllMTMtZDFmMTllYTBlZTkwOjJlZDUyN2U4LWY0NzYtNGY4NS1hNTE2LWY1MmE0ZWJiNjMyMA=="
    )

    print("Listing agents...")
    try:
        agents_page = await client.agents.list()
        print(f"Type of agents_page: {type(agents_page)}")

        agents = []
        # Try iterating directly (if it's a sync iterator or list)
        try:
            for a in agents_page:
                agents.append(a)
                print(f"Item type: {type(a)}")
                print(f"Item content: {a}")
            print("Iterated synchronously")
        except TypeError:
            print("Sync iteration failed, trying async iteration")
            async for a in agents_page:
                agents.append(a)
            print("Iterated asynchronously")

        print(f"Found {len(agents)} agents")
        if agents:
            print(f"Last agent: {agents[-1].id}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
