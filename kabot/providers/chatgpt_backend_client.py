"""ChatGPT backend helpers for OpenAI Codex OAuth."""

import base64
import json
import re
from typing import Any, Dict, Iterator, List, Optional

from loguru import logger


def extract_account_id(jwt_token: str) -> str:
    """Extract ChatGPT account ID from JWT token."""
    try:
        parts = jwt_token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT token format")

        payload_b64 = parts[1]
        padding = 4 - (len(payload_b64) % 4)
        if padding != 4:
            payload_b64 += "=" * padding

        payload_json = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
        payload = json.loads(payload_json)
        auth_claim = payload.get("https://api.openai.com/auth", {})
        account_id = auth_claim.get("chatgpt_account_id")

        if not account_id:
            raise ValueError("No chatgpt_account_id in token")
        return account_id
    except Exception as e:
        raise ValueError(f"Failed to extract account ID from token: {e}")


def _normalize_tool_for_responses(tool: Dict[str, Any]) -> Dict[str, Any]:
    """Convert chat-completions style tools into responses-style tools."""
    if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
        fn = tool["function"]
        normalized = {
            "type": "function",
            "name": fn.get("name"),
            "description": fn.get("description", ""),
            "parameters": fn.get("parameters", {"type": "object", "properties": {}}),
        }
        return normalized
    return tool


_CALL_ID_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_-]")
_DEFAULT_INSTRUCTIONS = "You are Kabot, a helpful AI assistant. Follow the user request safely and accurately."


def _normalize_call_id(value: Any, fallback: str) -> str:
    """Normalize a tool call id to a backend-safe value."""
    candidate = ""
    if value is not None:
        candidate = str(value).strip()
    if "|" in candidate:
        candidate = candidate.split("|", 1)[0]
    candidate = _CALL_ID_SANITIZE_RE.sub("_", candidate).strip("_")
    if not candidate:
        candidate = fallback
    normalized = candidate[:64].rstrip("_")
    return normalized or fallback


def _serialize_arguments(arguments: Any) -> str:
    """Serialize function-call arguments into JSON string."""
    if isinstance(arguments, str):
        text = arguments.strip()
        return text if text else "{}"
    if arguments is None:
        return "{}"
    try:
        return json.dumps(arguments, ensure_ascii=False)
    except Exception:
        return "{}"


def _normalize_message_content(content: Any) -> Any:
    """Normalize message content for responses input payload."""
    if isinstance(content, (str, list, dict)):
        return content
    if content is None:
        return ""
    return str(content)


def _stringify_content(content: Any) -> str:
    """Convert content into text for function_call_output payload."""
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    try:
        return json.dumps(content, ensure_ascii=False)
    except Exception:
        return str(content)


def _append_assistant_tool_calls(
    input_messages: list[dict[str, Any]],
    msg: Dict[str, Any],
    tool_result_ids: set[str]
) -> bool:
    """Append assistant tool calls as responses-style function_call items.

    Only appends tool calls that have corresponding tool results to avoid
    ChatGPT backend API validation errors.
    """
    appended = False
    tool_calls = msg.get("tool_calls")

    if isinstance(tool_calls, list):
        for idx, tc in enumerate(tool_calls, start=1):
            if not isinstance(tc, dict):
                continue
            function = tc.get("function") if isinstance(tc.get("function"), dict) else {}
            name = function.get("name") or tc.get("name")
            if not isinstance(name, str) or not name.strip():
                continue

            raw_id = tc.get("call_id") or tc.get("id") or msg.get("tool_call_id")
            fallback = f"call_{len(input_messages) + idx}"
            call_id = _normalize_call_id(raw_id, fallback)

            # Only add tool call if there's a corresponding tool result
            if call_id not in tool_result_ids:
                logger.debug(f"Skipping tool call {call_id} (no matching result)")
                continue

            arguments = function.get("arguments") if function else tc.get("arguments")

            input_messages.append(
                {
                    "type": "function_call",
                    "call_id": call_id,
                    "name": name,
                    "arguments": _serialize_arguments(arguments),
                }
            )
            appended = True

    function_call = msg.get("function_call")
    if isinstance(function_call, dict):
        name = function_call.get("name")
        if isinstance(name, str) and name.strip():
            raw_id = function_call.get("call_id") or function_call.get("id") or msg.get("tool_call_id")
            call_id = _normalize_call_id(raw_id, f"call_{len(input_messages) + 1}")

            # Only add tool call if there's a corresponding tool result
            if call_id not in tool_result_ids:
                logger.debug(f"Skipping function_call {call_id} (no matching result)")
                return appended

            input_messages.append(
                {
                    "type": "function_call",
                    "call_id": call_id,
                    "name": name,
                    "arguments": _serialize_arguments(function_call.get("arguments")),
                }
            )
            appended = True

    return appended


def build_chatgpt_request(
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stream: bool = True,
) -> Dict[str, Any]:
    """Build request body for ChatGPT backend API."""
    system_prompts: list[str] = []
    input_messages: list[dict[str, Any]] = []

    # Track tool call IDs and tool result IDs to ensure they match
    tool_call_ids: set[str] = set()
    tool_result_ids: set[str] = set()

    # First pass: collect all tool result IDs
    for msg in messages:
        if msg.get("role") == "tool":
            raw_call_id = msg.get("tool_call_id") or msg.get("id")
            if raw_call_id:
                normalized_id = _normalize_call_id(raw_call_id, "")
                if normalized_id:
                    tool_result_ids.add(normalized_id)

    for msg in messages:
        role = msg.get("role")
        if role == "system":
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                system_prompts.append(content)
            continue

        if role == "tool":
            raw_call_id = msg.get("tool_call_id") or msg.get("id")
            call_id = _normalize_call_id(raw_call_id, f"call_{len(input_messages) + 1}")
            input_messages.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": _stringify_content(msg.get("content")),
                }
            )
            continue

        if role == "assistant":
            content = msg.get("content")
            has_content = content is not None and str(content).strip() != ""
            if has_content:
                input_messages.append(
                    {
                        "role": "assistant",
                        "content": _normalize_message_content(content),
                    }
                )
            if _append_assistant_tool_calls(input_messages, msg, tool_result_ids):
                continue
            if has_content:
                continue

        normalized: dict[str, Any] = {
            "role": role,
            "content": _normalize_message_content(msg.get("content", "")),
        }
        for field in ("name",):
            if msg.get(field) is not None:
                normalized[field] = msg.get(field)
        input_messages.append(normalized)

    body: Dict[str, Any] = {
        "model": model,
        "store": False,
        "stream": stream,
        "input": input_messages,
        "text": {"verbosity": "medium"},
        "include": ["reasoning.encrypted_content"],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
    }

    if system_prompts:
        body["instructions"] = "\n\n".join(system_prompts)
    else:
        # Codex backend requires non-empty instructions even for simple user-only turns.
        body["instructions"] = _DEFAULT_INSTRUCTIONS
    if tools:
        body["tools"] = [_normalize_tool_for_responses(t) for t in tools]

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
    """Parse server-sent-events payload into JSON events."""
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

    elif event_type in {
        "response.output_text.delta",
        "response.text.delta",
        "response.refusal.delta",
    }:
        return event.get("delta", "")

    return None


def _parse_tool_arguments(raw_args: Any) -> dict[str, Any]:
    """Normalize tool arguments into a dict."""
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str):
        text = raw_args.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"raw": text}
    if raw_args is None:
        return {}
    return {"value": raw_args}


def parse_chatgpt_stream_events(events: Iterator[Dict[str, Any]]) -> Dict[str, Any]:
    """Parse SSE events into final text + tool calls."""
    text_parts: list[str] = []
    tool_calls: dict[str, dict[str, Any]] = {}
    output_item_to_call: dict[str, str] = {}

    for event in events:
        text = extract_content_from_event(event)
        if text:
            text_parts.append(text)

        event_type = event.get("type")
        if event_type in {"response.output_item.added", "response.output_item.done"}:
            item = event.get("item", {})
            if not isinstance(item, dict):
                continue
            if item.get("type") != "function_call":
                continue

            item_id = str(item.get("id") or "")
            call_id = str(item.get("call_id") or item_id or f"call_{len(tool_calls)+1}")
            if item_id:
                output_item_to_call[item_id] = call_id

            call_state = tool_calls.get(
                call_id,
                {"id": call_id, "name": "", "arguments_chunks": [], "arguments_obj": None},
            )
            name = item.get("name")
            if isinstance(name, str) and name:
                call_state["name"] = name

            args = item.get("arguments")
            if isinstance(args, str):
                call_state["arguments_chunks"] = [args]
            elif isinstance(args, dict):
                call_state["arguments_obj"] = args
            tool_calls[call_id] = call_state
            continue

        if event_type in {"response.function_call_arguments.delta", "response.function_call_arguments.done"}:
            raw_item_id = event.get("item_id") or event.get("id") or event.get("call_id")
            if raw_item_id is None:
                continue
            raw_item_id_str = str(raw_item_id)
            call_id = output_item_to_call.get(raw_item_id_str, raw_item_id_str)

            call_state = tool_calls.get(
                call_id,
                {"id": call_id, "name": "", "arguments_chunks": [], "arguments_obj": None},
            )
            if isinstance(event.get("name"), str) and not call_state.get("name"):
                call_state["name"] = event["name"]

            delta = event.get("delta")
            if isinstance(delta, str):
                call_state["arguments_chunks"].append(delta)

            arguments = event.get("arguments")
            if isinstance(arguments, str):
                call_state["arguments_chunks"] = [arguments]
            elif isinstance(arguments, dict):
                call_state["arguments_obj"] = arguments
            tool_calls[call_id] = call_state

    parsed_calls: list[dict[str, Any]] = []
    for call in tool_calls.values():
        name = str(call.get("name") or "").strip()
        if not name:
            continue
        arguments_obj = call.get("arguments_obj")
        if isinstance(arguments_obj, dict):
            args = arguments_obj
        else:
            args_text = "".join(call.get("arguments_chunks", [])).strip()
            args = _parse_tool_arguments(args_text)

        parsed_calls.append(
            {
                "id": str(call.get("id") or f"call_{len(parsed_calls)+1}"),
                "name": name,
                "arguments": args,
            }
        )

    return {
        "content": "".join(text_parts),
        "tool_calls": parsed_calls,
    }


def parse_chatgpt_response_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Parse non-streaming JSON payload into final text + tool calls."""
    output = payload.get("output", [])
    if not isinstance(output, list):
        return {"content": "", "tool_calls": []}

    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []

    for item in output:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "message":
            content = item.get("content", [])
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                part_type = part.get("type")
                if part_type in {"text", "output_text"} and part.get("text"):
                    text_parts.append(str(part.get("text")))
                elif part_type == "refusal" and part.get("refusal"):
                    text_parts.append(str(part.get("refusal")))
        elif item_type == "function_call":
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            call_id = str(item.get("call_id") or item.get("id") or f"call_{len(tool_calls)+1}")
            tool_calls.append(
                {
                    "id": call_id,
                    "name": name,
                    "arguments": _parse_tool_arguments(item.get("arguments")),
                }
            )

    return {
        "content": "".join(text_parts),
        "tool_calls": tool_calls,
    }
