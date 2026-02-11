"""Letta provider implementation for stateful agents."""

import json
import os
from pathlib import Path
from typing import Any, Dict

try:
    from letta_client import AsyncLetta
except ImportError:
    AsyncLetta = None

from kabot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from loguru import logger

class LettaProvider(LLMProvider):
    """
    Provider for Letta (formerly MemGPT) stateful agents.

    This provider manages persistent agents that maintain their own memory and context.
    It ignores the conversation history passed by Kabot's AgentLoop (since Letta
    tracks history internally) and forwards only the latest message.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        workspace_path: str = "~/.kabot/workspace",
        default_model: str = "openai/gpt-4o-mini",
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.workspace = Path(workspace_path).expanduser()
        self.mapping_file = self.workspace / "letta_agents.json"

        if not AsyncLetta:
            raise ImportError("letta-client not installed. Run `pip install letta-client`.")

        # Initialize client
        # If api_base is provided, use it (e.g. http://localhost:8283 for local server)
        # Otherwise defaults to Letta Cloud
        self.client = AsyncLetta(
            api_key=api_key or "letta-insecure",  # Default for local
            base_url=api_base
        )

        self._agent_mapping: Dict[str, str] = {}
        self._load_mapping()

    def _load_mapping(self):
        """Load session_id -> letta_agent_id mapping."""
        if self.mapping_file.exists():
            try:
                self._agent_mapping = json.loads(self.mapping_file.read_text())
            except Exception as e:
                logger.error(f"Failed to load Letta mapping: {e}")

    def _save_mapping(self):
        """Save session_id -> letta_agent_id mapping."""
        try:
            self.mapping_file.write_text(json.dumps(self._agent_mapping, indent=2))
        except Exception as e:
            logger.error(f"Failed to save Letta mapping: {e}")

    async def _get_or_create_agent(self, session_id: str, model: str) -> str:
        """Get existing Letta agent ID or create a new one for this session."""
        if session_id in self._agent_mapping:
            return self._agent_mapping[session_id]

        # Create new agent
        try:
            agent = await self.client.agents.create(
                model=model,
                name=f"kabot-{session_id.replace(':', '-')}",
                memory_blocks=[
                    {
                        "label": "human",
                        "value": f"User ID: {session_id}\nThis user is chatting via Kabot."
                    },
                    {
                        "label": "persona",
                        "value": "You are Kabot, a helpful AI assistant with advanced long-term memory."
                    }
                ]
            )
            agent_id = agent.id
            self._agent_mapping[session_id] = agent_id
            self._save_mapping()
            logger.info(f"Created new Letta agent {agent_id} for session {session_id}")
            return agent_id
        except Exception as e:
            # Handle account limits (402 Payment Required / Limit reached)
            error_str = str(e).lower()
            if "limit" in error_str or "402" in error_str or "429" in error_str:
                logger.warning(f"Letta agent limit reached. Attempting fallback to existing agent. Error: {e}")
                try:
                    # List existing agents
                    agents_page = await self.client.agents.list()

                    all_agents = []
                    # Try synchronous iteration first (works for SyncArrayPage/some Async pages)
                    try:
                        for item in agents_page:
                            # Check if item is the agent itself or a tuple ('items', [agents])
                            if isinstance(item, tuple) and len(item) == 2 and item[0] == 'items':
                                if isinstance(item[1], list):
                                    all_agents.extend(item[1])
                            else:
                                # Assume item is an agent object
                                all_agents.append(item)
                    except TypeError:
                        # Fallback to async iteration
                        async for item in agents_page:
                            if isinstance(item, tuple) and len(item) == 2 and item[0] == 'items':
                                if isinstance(item[1], list):
                                    all_agents.extend(item[1])
                            else:
                                all_agents.append(item)

                    if all_agents:
                        # 1. Try to find match by name
                        target_name = f"kabot-{session_id.replace(':', '-')}"
                        matching_agent = next((a for a in all_agents if hasattr(a, 'name') and a.name == target_name), None)

                        if matching_agent:
                            agent_id = matching_agent.id
                            logger.info(f"Fallback: Found existing agent {agent_id} with name {target_name}")
                        else:
                            # 2. Reuse the last agent in the list
                            # Filter mostly to ensure it has an ID
                            valid_agents = [a for a in all_agents if hasattr(a, 'id')]
                            if valid_agents:
                                fallback_agent = valid_agents[-1]
                                agent_id = fallback_agent.id
                                logger.info(f"Fallback: Reusing existing agent {agent_id} ({getattr(fallback_agent, 'name', 'unknown')}) for session {session_id}")
                            else:
                                logger.error("No valid agent objects found in list.")
                                raise e

                        self._agent_mapping[session_id] = agent_id
                        self._save_mapping()
                        return agent_id
                    else:
                        logger.error("No existing agents found to reuse.")
                        raise e
                except Exception as fallback_e:
                    logger.error(f"Failed to execute fallback logic: {fallback_e}")
                    raise e

            logger.error(f"Failed to create Letta agent: {e}")
            raise

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        Send a message to the Letta agent.

        We ignore 'messages' history because Letta is stateful.
        We only take the last user message.
        """
        model = model or self.default_model

        # 1. Identify session from the messages or context
        # Kabot's AgentLoop doesn't pass session_id explicitly to chat(),
        # but we can try to infer it or use a default.
        # Ideally, we should pass session_id in 'extra_body' or similar if possible,
        # but for now let's use a hashed user_id from the last message if available.

        # Heuristic to find the real user message
        last_user_msg = None
        for m in reversed(messages):
            if m["role"] == "user":
                last_user_msg = m
                break

        if not last_user_msg:
            return LLMResponse(content="No user message found.")

        # Extract content
        content = last_user_msg["content"]
        if isinstance(content, list):
            # Handle multimodal - extract text parts
            text_parts = [p["text"] for p in content if p.get("type") == "text"]
            content = "\n".join(text_parts)

        # Generate a stable session key based on the prompt hash or specific metadata if available
        # Since we don't have the explicit session_id here, we'll use a single 'default' agent
        # or rely on the user to configure a specific agent ID in the future.
        # IMPROVEMENT: Use a global/contextvar for session_id if we modify Kabot core.
        # For now, let's use a single shared agent for simplicity or try to parse from system prompt.
        session_id = "default"

        # Try to find "Current Session" block in system prompt
        for m in messages:
            if m["role"] == "system" and "Current Session" in m["content"]:
                # Parse "Chat ID: xxx"
                import re
                match = re.search(r"Chat ID: (\S+)", m["content"])
                if match:
                    session_id = match.group(1)
                    break

        # 2. Get Agent
        agent_id = await self._get_or_create_agent(session_id, model)

        # 3. Send Message
        try:
            response = await self.client.agents.messages.create(
                agent_id=agent_id,
                messages=[{
                    "role": "user",
                    "content": content
                }]
            )

            # 4. Parse Response
            # Letta returns a list of messages (internal thought, tool calls, assistant response)
            final_content = []
            tool_calls = []

            for msg in response.messages:
                if msg.message_type == "assistant_message":
                    final_content.append(msg.content)
                elif msg.message_type == "tool_call_message":
                    # Map Letta tool call to Kabot tool call
                    # Note: Letta might execute some internal tools (memory) automatically.
                    # We only forward tools that Kabot needs to execute.
                    # HOWEVER, Letta usually executes tools server-side if configured.
                    # If Letta asks CLIENT to execute, we handle it here.
                    tool_calls.append(ToolCallRequest(
                        id=msg.id, # or generate one
                        name=msg.tool_call.name,
                        arguments=json.loads(msg.tool_call.arguments) if isinstance(msg.tool_call.arguments, str) else msg.tool_call.arguments
                    ))

            return LLMResponse(
                content="\n\n".join(final_content) if final_content else None,
                tool_calls=tool_calls,
                finish_reason="stop"
            )

        except Exception as e:
            return LLMResponse(
                content=f"Letta Error: {str(e)}",
                finish_reason="error"
            )

    def get_default_model(self) -> str:
        return self.default_model
