"""
ChatGPT Backend API Client

Custom client for OpenAI Codex OAuth that uses the ChatGPT backend API
(chatgpt.com/backend-api) instead of the standard OpenAI API.
"""

import json
import base64
from typing import Dict, Any, List, Iterator, Optional


def extract_account_id(jwt_token: str) -> str:
    """Extract ChatGPT account ID from JWT token."""
    try:
        parts = jwt_token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT token format")

        # Decode payload (add padding if needed)
        payload_b64 = parts[1]
        padding = 4 - (len(payload_b64) % 4)
        if padding != 4:
            payload_b64 += "=" * padding

        payload_json = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
        payload = json.loads(payload_json)

        # Extract account ID from JWT claim path
        auth_claim = payload.get("https://api.openai.com/auth", {})
        account_id = auth_claim.get("chatgpt_account_id")

        if not account_id:
            raise ValueError("No chatgpt_account_id in token")

        return account_id
    except Exception as e:
        raise ValueError(f"Failed to extract account ID from token: {e}")


def build_chatgpt_request(
    model: str,
    messages: List[Dict[str, Any]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stream: bool = True,
) -> Dict[str, Any]:
    """Build request body for ChatGPT backend API."""
    # Separate system prompt from messages
    system_prompt = None
    user_messages = []

    for msg in messages:
        if msg.get("role") == "system":
            system_prompt = msg.get("content", "")
        else:
            user_messages.append({
                "role": msg.get("role"),
                "content": msg.get("content"),
            })

    body = {
        "model": model,
        "store": False,
        "stream": stream,
        "input": user_messages,
        "text": {"verbosity": "medium"},
        "include": ["reasoning.encrypted_content"],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
    }

    if system_prompt:
        body["instructions"] = system_prompt

    # ChatGPT backend codex endpoint rejects "temperature".
    # Keep function signature stable but intentionally do not send it.

    return body


def build_chatgpt_headers(jwt_token: str, account_id: str) -> Dict[str, str]:
    """Build headers for ChatGPT backend API."""
    return {
        "Authorization": f"Bearer {jwt_token}",
        "chatgpt-account-id": account_id,
        "OpenAI-Beta": "responses=experimental",
        "originator": "kabot",
        "User-Agent": "kabot",
        "accept": "text/event-stream",
        "content-type": "application/json",
    }


def parse_sse_stream(response_text: str) -> Iterator[Dict[str, Any]]:
    """Parse Server-Sent Events stream."""
    for chunk in response_text.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue

        data_lines: list[str] = []
        for line in chunk.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())

        if not data_lines:
            continue

        data = "\n".join(data_lines).strip()
        if data and data != "[DONE]":
            try:
                yield json.loads(data)
            except json.JSONDecodeError:
                continue


def extract_content_from_event(event: Dict[str, Any]) -> Optional[str]:
    """Extract text content from SSE event."""
    event_type = event.get("type")

    if event_type == "response.output_item.added":
        item = event.get("item", {})
        if item.get("type") == "message":
            content = item.get("content", [])
            if content and isinstance(content, list):
                for part in content:
                    part_type = part.get("type")
                    if part_type in {"text", "output_text"}:
                        return part.get("text", "")
                    if part_type == "refusal":
                        return part.get("refusal", "")

    elif event_type == "response.content_part.added":
        part = event.get("part", {})
        part_type = part.get("type")
        if part_type in {"text", "output_text"}:
            return part.get("text", "")
        if part_type == "refusal":
            return part.get("refusal", "")

    elif event_type in {"response.output_text.delta", "response.text.delta", "response.refusal.delta"}:
        return event.get("delta", "")

    return None
