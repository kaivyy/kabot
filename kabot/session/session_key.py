def build_agent_session_key(agent_id: str, channel: str, chat_id: str) -> str:
    return f"agent:{agent_id}:{channel}:{chat_id}"

def parse_agent_session_key(session_key: str) -> dict[str, str]:
    parts = session_key.split(":")
    if len(parts) >= 4 and parts[0] == "agent":
        return {
            "agent_id": parts[1],
            "channel": parts[2],
            "chat_id": ":".join(parts[3:])
        }
    return {}
