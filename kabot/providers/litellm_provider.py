"""LiteLLM provider implementation for multi-provider support."""

import asyncio
import json
import logging
import os
from typing import Any

import litellm
import requests
from litellm import acompletion
from litellm.exceptions import (
    APIConnectionError,
    InvalidRequestError,
    RateLimitError,
    ServiceUnavailableError,
)
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from kabot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from kabot.providers.chatgpt_backend_client import (
    build_chatgpt_headers,
    build_chatgpt_request,
    extract_account_id,
    parse_chatgpt_response_payload,
    parse_chatgpt_stream_events,
    parse_sse_stream,
)
from kabot.providers.registry import find_by_model, find_gateway

logger = logging.getLogger(__name__)

class LiteLLMProvider(LLMProvider):
    """
    LLM provider using LiteLLM for multi-provider support.

    Supports OpenRouter, Anthropic, OpenAI, Gemini, and many other providers through
    a unified interface.  Provider-specific logic is driven by the registry
    (see providers/registry.py) — no if-elif chains needed here.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "anthropic/claude-opus-4-5",
        extra_headers: dict[str, str] | None = None,
        provider_name: str | None = None,
        fallbacks: list[str] | None = None,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.extra_headers = extra_headers or {}
        self.fallbacks = fallbacks or []

        # Detect gateway / local deployment.
        # provider_name (from config key) is the primary signal;
        # api_key / api_base are fallback for auto-detection.
        self._gateway = find_gateway(provider_name, api_key, api_base)

        # Configure environment variables
        if api_key:
            self._setup_env(api_key, api_base, default_model)

        if api_base:
            litellm.api_base = api_base

        # Disable LiteLLM logging noise
        litellm.suppress_debug_info = True
        # Drop unsupported parameters for providers (e.g., gpt-5 rejects some params)
        litellm.drop_params = True

    def _setup_env(self, api_key: str, api_base: str | None, model: str) -> None:
        """Set environment variables based on detected provider."""
        spec = self._gateway or find_by_model(model)
        if not spec:
            return

        # Gateway/local overrides existing env; standard provider doesn't
        if self._gateway:
            os.environ[spec.env_key] = api_key
        else:
            os.environ.setdefault(spec.env_key, api_key)

        # Resolve env_extras placeholders:
        #   {api_key}  → user's API key
        #   {api_base} → user's api_base, falling back to spec.default_api_base
        effective_base = api_base or spec.default_api_base
        for env_name, env_val in spec.env_extras:
            resolved = env_val.replace("{api_key}", api_key)
            resolved = resolved.replace("{api_base}", effective_base)
            os.environ.setdefault(env_name, resolved)

    def _resolve_model(self, model: str) -> str:
        """Resolve model name by applying provider/gateway prefixes."""
        if self._gateway:
            # Gateway mode: apply gateway prefix, skip provider-specific prefixes
            prefix = self._gateway.litellm_prefix
            if self._gateway.strip_model_prefix:
                model = model.split("/")[-1]
            if prefix and not model.startswith(f"{prefix}/"):
                model = f"{prefix}/{model}"
            return model

        # Standard mode: auto-prefix for known providers
        spec = find_by_model(model)
        if spec and spec.litellm_prefix:
            # Qwen Portal catalog models are stored as qwen-portal/<model>,
            # but DashScope expects only the raw model id after provider prefix.
            if spec.name == "dashscope" and model.startswith("qwen-portal/"):
                model = model.split("/", 1)[1]
            if not any(model.startswith(s) for s in spec.skip_prefixes):
                model = f"{spec.litellm_prefix}/{model}"

        return model

    def _apply_model_overrides(self, model: str, kwargs: dict[str, Any]) -> None:
        """Apply model-specific parameter overrides from the registry."""
        model_lower = model.lower()
        spec = find_by_model(model)
        if spec:
            for pattern, overrides in spec.model_overrides:
                if pattern in model_lower:
                    kwargs.update(overrides)
                    return

    async def _execute_model_call(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Execute a single model call with retries for transient errors."""
        # Lazy imports for performance
        from litellm.exceptions import (
            APIConnectionError,
            RateLimitError,
            ServiceUnavailableError,
        )

        resolved_model = self._resolve_model(model)

        # OpenAI Codex specific handling (ChatGPT backend API)
        if self._is_openai_codex(resolved_model):
            return await self._chat_openai_codex(messages, tools, resolved_model, max_tokens, temperature)

        # OpenRouter specific handling
        if self._is_openrouter(resolved_model):
            return await self._chat_openrouter(messages, tools, resolved_model, max_tokens, temperature)

        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Apply model-specific overrides (e.g. kimi-k2.5 temperature)
        self._apply_model_overrides(resolved_model, kwargs)

        if self.api_key:
            kwargs["api_key"] = self.api_key

        # Pass api_base for custom endpoints
        if self.api_base:
            kwargs["api_base"] = self.api_base

        # Pass extra headers
        if self.extra_headers and "extra_headers" not in kwargs:
            kwargs["extra_headers"] = self.extra_headers

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # Dynamically create the retry wrapper for acompletion
        @retry(
            retry=retry_if_exception_type((RateLimitError, APIConnectionError, ServiceUnavailableError)),
            wait=wait_exponential(multiplier=1, min=2, max=60),
            stop=stop_after_attempt(3),
            reraise=True,
            before_sleep=before_sleep_log(logger, logging.WARNING)
        )
        async def _do_call():
            return await acompletion(**kwargs)

        response = await _do_call()
        return self._parse_response(response)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        Send a chat completion request via LiteLLM with automatic retries and fallback.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions in OpenAI format.
            model: Model identifier (e.g., 'anthropic/claude-sonnet-4-5').
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Returns:
            LLMResponse with content and/or tool calls.
        """
        # Sanitize messages to remove internal fields (like 'tool_results') that might cause API errors
        sanitized_messages = []
        for msg in messages:
            # Create a working copy
            temp_msg = msg.copy()

            # Fix for Groq/OpenAI: Extract tool_call_id from internal tool_results if missing
            # Kabot stores tool info in 'tool_results' list, but API expects 'tool_call_id' at root
            if temp_msg.get("role") == "tool" and "tool_call_id" not in temp_msg:
                tool_results = temp_msg.get("tool_results")
                if tool_results and isinstance(tool_results, list) and len(tool_results) > 0:
                    first_result = tool_results[0]
                    if isinstance(first_result, dict):
                        temp_msg["tool_call_id"] = first_result.get("tool_call_id")
                        if "name" not in temp_msg:
                            temp_msg["name"] = first_result.get("name")

            # Fix for Groq: Ensure tool_calls have correct structure (function wrapper)
            if temp_msg.get("tool_calls") and isinstance(temp_msg["tool_calls"], list):
                fixed_tool_calls = []
                for tc in temp_msg["tool_calls"]:
                    if isinstance(tc, dict):
                        # Ensure 'type' exists
                        if "type" not in tc:
                            tc["type"] = "function"

                        # Fix missing 'function' wrapper (Common issue from memory retrieval)
                        if "function" not in tc:
                            # If name/arguments are at root, move them to function
                            if "name" in tc and "arguments" in tc:
                                tc["function"] = {
                                    "name": tc["name"],
                                    "arguments": tc["arguments"]
                                }
                                # Remove from root to be clean (optional but safer)
                                tc.pop("name", None)
                                tc.pop("arguments", None)

                        # Fix for Groq: 'arguments' must be a JSON string strictly
                        if "function" in tc and isinstance(tc["function"], dict):
                            args = tc["function"].get("arguments")
                            if not isinstance(args, str):
                                try:
                                    # Convert to JSON string (handles dict, list, int, bool, None)
                                    tc["function"]["arguments"] = json.dumps(args) if args is not None else "{}"
                                except Exception:
                                    # Fallback to string representation
                                    tc["function"]["arguments"] = str(args)

                        fixed_tool_calls.append(tc)
                temp_msg["tool_calls"] = fixed_tool_calls

            # Filter keys to only allow standard OpenAI chat message fields
            new_msg = {k: v for k, v in temp_msg.items() if k in ["role", "content", "name", "tool_calls", "tool_call_id", "function_call"]}

            # Keep reasoning_content for OpenRouter if needed, handled in _chat_openrouter
            if "reasoning_content" in temp_msg:
                new_msg["reasoning_content"] = temp_msg["reasoning_content"]

            sanitized_messages.append(new_msg)

        # DEBUG: Print keys of the last message to verify sanitization
        if sanitized_messages:
            # We don't want to spam stdout in production, but keeping it for now as per original file
            print(f"DEBUG: Last message keys sent to LLM: {list(sanitized_messages[-1].keys())}")

        # Construct list of models to try: primary -> fallbacks
        primary_model = model or self.default_model
        models_to_try = [primary_model]

        # Only add fallbacks if we are using the default model or if explicit model matches default
        # (This prevents falling back to a different model if the user explicitly requested a specific one,
        # unless we want fallbacks to apply everywhere. Typically fallbacks are for the 'default' usage.)
        # However, the requirement implies generic fallback. Let's apply provided fallbacks.
        if self.fallbacks:
            for fb in self.fallbacks:
                if fb != primary_model:
                    models_to_try.append(fb)

        last_exception = None

        for attempt_model in models_to_try:
            try:
                return await self._execute_model_call(
                    model=attempt_model,
                    messages=sanitized_messages,
                    tools=tools,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
            except (RateLimitError, APIConnectionError, ServiceUnavailableError) as e:
                # Transient error after retries exhausted for this model.
                logger.warning(f"Model {attempt_model} failed after retries: {e}. Trying next...")
                last_exception = e
                continue
            except InvalidRequestError as e:
                # Fail fast on invalid requests (e.g. context too long, bad tools)
                logger.error(f"Invalid request for {attempt_model}: {e}")
                raise e
            except Exception as e:
                # Catch-all for other errors.
                # If it's a litellm wrapper exception that we didn't catch above, check it.
                # But generally we want to try fallbacks for availability.
                # If it's an unexpected error, we might want to try the next model too?
                # "InvalidRequestError... fails fast".
                # We'll treat unknown exceptions as potential availability issues (like some weird HTTP errors)
                # unless they look like bad requests.
                logger.warning(f"Unexpected error for {attempt_model}: {e}. Trying next...")
                last_exception = e
                continue

        # If we get here, all models failed
        error_msg = f"All models failed. Last error: {last_exception}"
        return LLMResponse(
            content=error_msg,
            finish_reason="error",
        )

    def _is_openrouter(self, model: str) -> bool:
        """Check if the request is destined for OpenRouter."""
        if self._gateway and self._gateway.name == "openrouter":
            return True
        if model.startswith("openrouter/"):
            return True
        return False

    def _is_openai_codex(self, model: str) -> bool:
        """Check if the model uses OpenAI Codex (ChatGPT backend API)."""
        return model.startswith("openai-codex/") or "openai-codex" in model

    async def _chat_openai_codex(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Handle OpenAI Codex requests using ChatGPT backend API."""

        def _make_request():
            if not self.api_key:
                raise ValueError("No API key for OpenAI Codex")

            # Verify it's a JWT token
            if not self.api_key.startswith("eyJ"):
                raise ValueError("OpenAI Codex requires OAuth JWT token, not API key")

            try:
                # Extract account ID from JWT token
                account_id = extract_account_id(self.api_key)
            except ValueError as e:
                raise ValueError(f"Invalid OAuth token: {e}")

            # Strip provider prefix from model name (openai-codex/gpt-5.3-codex -> gpt-5.3-codex)
            api_model = model.split("/")[-1] if "/" in model else model

            # Build request
            body = build_chatgpt_request(
                model=api_model,
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            headers = build_chatgpt_headers(self.api_key, account_id)

            # Debug logging
            logger.info(f"ChatGPT Backend API Request - Model: {api_model}, Account: {account_id[:8]}...")
            logger.debug(f"Request body: {json.dumps(body, indent=2)}")

            # Make request to ChatGPT backend API
            url = "https://chatgpt.com/backend-api/codex/responses"

            try:
                response = requests.post(
                    url=url,
                    headers=headers,
                    json=body,
                    timeout=120,
                )

                # Log response for debugging
                logger.info(f"ChatGPT Backend API Response Status: {response.status_code}")

                response.raise_for_status()

                # Parse SSE stream from UTF-8 bytes first to avoid mojibake
                # when requests guesses charset incorrectly.
                sse_text = response.text
                raw_payload = getattr(response, "content", None)
                if isinstance(raw_payload, (bytes, bytearray)):
                    try:
                        sse_text = raw_payload.decode("utf-8")
                    except UnicodeDecodeError:
                        sse_text = raw_payload.decode("utf-8", errors="replace")

                parsed_response = parse_chatgpt_stream_events(parse_sse_stream(sse_text))

                # Fallback for non-streaming JSON payloads
                if not parsed_response.get("content") and not parsed_response.get("tool_calls"):
                    try:
                        payload = response.json()
                        parsed_response = parse_chatgpt_response_payload(payload)
                    except ValueError:
                        pass

                return parsed_response

            except requests.exceptions.HTTPError as e:
                # Log error response body for debugging
                error_body = ""
                if e.response is not None:
                    try:
                        error_body = e.response.text
                        logger.error(f"ChatGPT Backend API Error Response: {error_body}")
                    except Exception:
                        pass

                    status = e.response.status_code
                    if status == 429:
                        raise RateLimitError(message=str(e), llm_provider="openai-codex", model=model)
                    elif status >= 500:
                        raise ServiceUnavailableError(message=str(e), llm_provider="openai-codex", model=model)
                    elif status == 401 or status == 403:
                        raise InvalidRequestError(message=f"Authentication failed: {e}", llm_provider="openai-codex", model=model)
                    else:
                        raise InvalidRequestError(message=str(e), llm_provider="openai-codex", model=model)
                else:
                    raise APIConnectionError(message=str(e), llm_provider="openai-codex", model=model)
            except requests.exceptions.RequestException as e:
                raise APIConnectionError(message=str(e), llm_provider="openai-codex", model=model)

        try:
            loop = asyncio.get_running_loop()
            response_data = await loop.run_in_executor(None, _make_request)

            parsed_tool_calls: list[ToolCallRequest] = []
            for tc in response_data.get("tool_calls", []):
                if not isinstance(tc, dict):
                    continue

                name = tc.get("name")
                if not isinstance(name, str) or not name.strip():
                    continue

                tc_id = tc.get("id")
                if not isinstance(tc_id, str) or not tc_id.strip():
                    tc_id = f"call_{len(parsed_tool_calls) + 1}"

                arguments = tc.get("arguments")
                if isinstance(arguments, dict):
                    parsed_args = arguments
                elif isinstance(arguments, str):
                    try:
                        loaded = json.loads(arguments) if arguments.strip() else {}
                        # Guard: LLM sometimes sends [] for no-param tools instead of {}
                        parsed_args = loaded if isinstance(loaded, dict) else {}
                    except json.JSONDecodeError:
                        parsed_args = {"raw": arguments}
                elif arguments is None:
                    parsed_args = {}
                else:
                    parsed_args = {}

                parsed_tool_calls.append(
                    ToolCallRequest(
                        id=tc_id,
                        name=name,
                        arguments=parsed_args,
                    )
                )

            content = response_data.get("content", "")
            logger.debug(f"ChatGPT Backend API response: {len(content)} chars, {len(parsed_tool_calls)} tool calls")
            return LLMResponse(
                content=content,
                tool_calls=parsed_tool_calls,
                finish_reason="tool_calls" if parsed_tool_calls else "stop",
                usage={},
            )
        except (RateLimitError, APIConnectionError, ServiceUnavailableError, InvalidRequestError):
            raise
        except Exception as e:
            raise e

    async def _chat_openrouter(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Handle OpenRouter requests using raw requests lib."""

        def _make_request():
            api_key = self.api_key or os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY not found")

            # Prepare model name
            api_model = model
            if api_model.startswith("openrouter/"):
                stripped = api_model.replace("openrouter/", "", 1)
                if "/" in stripped:
                    api_model = stripped

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            if self.extra_headers:
                headers.update(self.extra_headers)

            # Prepare messages
            api_messages = []
            system_prompts = []

            for msg in messages:
                if msg["role"] == "system":
                    system_prompts.append(msg["content"])
                else:
                    new_msg = msg.copy()
                    if "reasoning_content" in new_msg:
                        new_msg["reasoning_details"] = new_msg.pop("reasoning_content")
                    api_messages.append(new_msg)

            # Merge system prompts
            if system_prompts and api_messages:
                for i, m in enumerate(api_messages):
                    if m["role"] == "user":
                        combined_system = "\n\n".join(system_prompts)
                        if isinstance(m["content"], str):
                            api_messages[i]["content"] = f"{combined_system}\n\n{m['content']}"
                        elif isinstance(m["content"], list):
                            api_messages[i]["content"].insert(0, {"type": "text", "text": combined_system + "\n\n"})
                        break
                else:
                    api_messages.insert(0, {"role": "user", "content": "\n\n".join(system_prompts)})

            data = {
                "model": api_model,
                "messages": api_messages,
                "reasoning": {"enabled": True}
            }

            if tools:
                data["tools"] = tools
                data["tool_choice"] = "auto"

            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    data=json.dumps(data)
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.HTTPError as e:
                # Handle specific HTTP errors to map to LiteLLM exceptions for retry logic
                if e.response is not None:
                    status = e.response.status_code
                    if status == 429:
                        raise RateLimitError(message=str(e), llm_provider="openrouter", model=model)
                    elif status >= 500:
                        raise ServiceUnavailableError(message=str(e), llm_provider="openrouter", model=model)
                    elif status == 400:
                        # Special handling for tools 400
                        try:
                            # Retry cleanly without tools/reasoning/extra params
                            data.pop("tools", None)
                            data.pop("tool_choice", None)
                            data.pop("reasoning", None)

                            # Note: This recursive-ish retry is synchronous and blocking,
                            # but within run_in_executor. It handles the "Smart Fallback" for tools specifically.
                            response = requests.post(
                                url="https://openrouter.ai/api/v1/chat/completions",
                                headers=headers,
                                data=json.dumps(data)
                            )
                            response.raise_for_status()
                            return response.json()
                        except Exception as retry_e:
                            raise InvalidRequestError(message=f"OpenRouter 400 (retry failed): {retry_e}", llm_provider="openrouter", model=model)

                    # Other 4xx
                    raise InvalidRequestError(message=str(e), llm_provider="openrouter", model=model)
                else:
                    raise APIConnectionError(message=str(e), llm_provider="openrouter", model=model)
            except requests.exceptions.RequestException as e:
                raise APIConnectionError(message=str(e), llm_provider="openrouter", model=model)
            except Exception as e:
                raise e

        try:
            loop = asyncio.get_running_loop()
            response_data = await loop.run_in_executor(None, _make_request)
            return self._parse_openrouter_response(response_data)
        except (RateLimitError, APIConnectionError, ServiceUnavailableError, InvalidRequestError):
            # Re-raise known exceptions for handling in caller
            raise
        except Exception as e:
            # Map generic errors to APIConnectionError if safe, or bubble up?
            # Safe to bubble up to be caught by catch-all in chat()
            raise e

    def _parse_openrouter_response(self, response: dict) -> LLMResponse:
        """Parse OpenRouter raw response."""
        # Handle API errors returned in JSON
        if "error" in response:
            error_msg = response["error"].get("message", str(response["error"]))
            raise Exception(f"API Error: {error_msg}")

        if "choices" not in response or not response["choices"]:
            # Provide detailed debug info if choices is missing
            keys_preview = ", ".join(list(response.keys()))
            raise Exception(f"Invalid response format: missing 'choices' field. Keys found: {keys_preview}")

        choice = response['choices'][0]
        message = choice['message']

        content = message.get('content')
        # OpenRouter returns 'reasoning_details' or sometimes 'reasoning' in message
        reasoning = message.get('reasoning') or message.get('reasoning_details')

        tool_calls = []
        if 'tool_calls' in message and message['tool_calls']:
            for tc in message['tool_calls']:
                args = tc['function']['arguments']
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}

                tool_calls.append(ToolCallRequest(
                    id=tc['id'],
                    name=tc['function']['name'],
                    arguments=args,
                ))

        usage = {}
        if 'usage' in response:
            usage = {
                "prompt_tokens": response['usage'].get('prompt_tokens', 0),
                "completion_tokens": response['usage'].get('completion_tokens', 0),
                "total_tokens": response['usage'].get('total_tokens', 0),
            }

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=choice.get('finish_reason', 'stop'),
            usage=usage,
            reasoning_content=reasoning,
        )

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response into our standard format."""
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                # Parse arguments from JSON string if needed
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}

                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        reasoning_content = getattr(message, "reasoning_content", None)

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
            reasoning_content=reasoning_content,
        )

    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
