"""Infer delivery target from session key."""

def infer_delivery(session_key: str) -> dict | None:
    """Auto-detect channel and recipient from a session key.

    Session keys follow the format: channel:chat_id
    Background sessions (background:*) return None.
    """
    if not session_key or session_key.startswith("background:"):
        return None

    parts = session_key.split(":", 1)
    if len(parts) < 2:
        return None

    channel, to = parts[0].strip(), parts[1].strip()
    if not channel or not to:
        return None

    return {"channel": channel, "to": to}
