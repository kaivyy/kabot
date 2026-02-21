import asyncio
import json
from kabot.integrations.meta_graph import MetaGraphClient

async def main():
    token = "THAAQIcDVkFeJBUVFTMnE1SjRkeXFhSXlRaGlrOUVIa0x6dzQ3U2tPYmVheXdlbUZArdWZAIZAUplRnh6TWdCemhjWlJmeTltNndYWUZAlRFVld0dkZA3RwM0VQWVMwUU9NOU1BV0RmVWN1TzlwTmdpa2RvUHl5RlNwTWRUTU94aU1YTU5vWDA2ZAEpDMW9CRDhoRGl3bnhoVDZA4X1hZAMzd0ZA2JMMFZAVZAWMZD"
    uid = "26179670184998096"
    client = MetaGraphClient(access_token=token)

    try:
        print("1. Creating container...")
        res = await client.request(
            "POST",
            f"/{uid}/threads",
            {"media_type": "TEXT", "text": "Hai testing dari kabot \ud83d\udd25"}
        )
        print(f"Container created: {res}")
        
        creation_id = res.get("id")
        if creation_id:
            print(f"2. Publishing container {creation_id}...")
            pub = await client.request(
                "POST",
                f"/{uid}/threads_publish",
                {"creation_id": creation_id}
            )
            print(f"Published: {pub}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
