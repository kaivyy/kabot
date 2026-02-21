"""Meta Graph tool for Threads and Instagram outbound actions."""

from __future__ import annotations

import json
import os
from typing import Any

from kabot.agent.tools.base import Tool
from kabot.integrations.meta_graph import MetaGraphClient


class MetaGraphTool(Tool):
    """Call Meta Graph API actions for Threads and Instagram."""

    def __init__(self, config: Any | None = None, client: Any | None = None, meta_config: Any | None = None):
        cfg = meta_config or self._resolve_meta_config(config)
        self.enabled = bool(getattr(cfg, "enabled", False))
        self.threads_user_id = (getattr(cfg, "threads_user_id", "") or "").strip() or "me"
        self.instagram_user_id = (getattr(cfg, "instagram_user_id", "") or "").strip() or "me"
        self._access_token_env = (getattr(cfg, "access_token_env", "") or "").strip()
        access_token = (getattr(cfg, "access_token", "") or "").strip()
        self._access_token = access_token

        self.client = client
        self._client_provided = client is not None
        if self.client is None and access_token:
            self.client = MetaGraphClient(access_token=access_token)

    @property
    def name(self) -> str:
        return "meta_graph"

    @property
    def description(self) -> str:
        return (
            "Execute Meta Graph outbound actions for Threads and Instagram. "
            "Actions: threads_create, threads_publish, ig_media_create, ig_media_publish."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "threads_create",
                        "threads_publish",
                        "ig_media_create",
                        "ig_media_publish",
                    ],
                    "description": "Meta action to run",
                },
                "text": {
                    "type": "string",
                    "description": "Text/caption for creation endpoints",
                },
                "creation_id": {
                    "type": "string",
                    "description": "Creation ID for publish endpoints",
                },
                "media_type": {
                    "type": "string",
                    "description": "Threads media type (e.g., TEXT, IMAGE, VIDEO)",
                },
                "image_url": {
                    "type": "string",
                    "description": "Image URL for Instagram media creation",
                },
                "video_url": {
                    "type": "string",
                    "description": "Video URL for Threads/Instagram media creation",
                },
                "reply_to_id": {
                    "type": "string",
                    "description": "Optional Threads parent post ID",
                },
                "access_token": {
                    "type": "string",
                    "description": "Optional per-request token override (preferred over saved config)",
                },
                "threads_user_id": {
                    "type": "string",
                    "description": "Optional per-request Threads user ID override",
                },
                "instagram_user_id": {
                    "type": "string",
                    "description": "Optional per-request Instagram user ID override",
                },
                "extra": {
                    "type": "object",
                    "description": "Additional key/value fields passed to Graph API payload",
                },
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        text: str | None = None,
        creation_id: str | None = None,
        media_type: str | None = None,
        image_url: str | None = None,
        video_url: str | None = None,
        reply_to_id: str | None = None,
        access_token: str | None = None,
        threads_user_id: str | None = None,
        instagram_user_id: str | None = None,
        extra: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        if threads_user_id:
            self.threads_user_id = str(threads_user_id).strip() or self.threads_user_id
        if instagram_user_id:
            self.instagram_user_id = str(instagram_user_id).strip() or self.instagram_user_id

        token_to_use = self._resolve_access_token(access_token)
        if token_to_use:
            should_build_client = (
                self.client is None
                or (not self._client_provided and token_to_use != self._access_token)
            )
            if should_build_client:
                self.client = MetaGraphClient(access_token=token_to_use)
            self._access_token = token_to_use

        if self.client is None:
            return (
                "Error: Meta integration is missing access token. "
                "Provide `access_token` in the call, set "
                "`THREADS_ACCESS_TOKEN`/`KABOT_META_ACCESS_TOKEN`, or set "
                "`integrations.meta.access_token` in `~/.kabot/config.json`."
            )

        action_map = {
            "threads_create": self._build_threads_create,
            "threads_publish": self._build_threads_publish,
            "ig_media_create": self._build_ig_media_create,
            "ig_media_publish": self._build_ig_media_publish,
        }

        if action not in action_map:
            return f"Error: Unsupported action '{action}'."

        try:
            method, path, payload = action_map[action](
                text=text,
                creation_id=creation_id,
                media_type=media_type,
                image_url=image_url,
                video_url=video_url,
                reply_to_id=reply_to_id,
                extra=extra or {},
            )
            result = await self.client.request(method, path, payload)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except Exception as exc:
            return f"Error: {exc}"

    def _resolve_access_token(self, inline_token: str | None = None) -> str:
        """Resolve token with precedence: inline > configured-env > env > current > config."""
        if inline_token and inline_token.strip():
            return inline_token.strip()

        configured_env_token = self._resolve_env_token_by_name(self._access_token_env)
        if configured_env_token:
            return configured_env_token

        env_token = (os.getenv("THREADS_ACCESS_TOKEN") or os.getenv("KABOT_META_ACCESS_TOKEN") or "").strip()
        if env_token:
            return env_token

        if self._access_token:
            return self._access_token

        # Try lazy loading from config if configured during the session
        try:
            from kabot.config.loader import load_config
            cfg = self._resolve_meta_config(load_config())
            self._access_token_env = (getattr(cfg, "access_token_env", "") or "").strip() or self._access_token_env
            configured_env_token = self._resolve_env_token_by_name(self._access_token_env)
            if configured_env_token:
                return configured_env_token
            token = (getattr(cfg, "access_token", "") or "").strip()
            if token:
                self.threads_user_id = (getattr(cfg, "threads_user_id", "") or "").strip() or self.threads_user_id
                self.instagram_user_id = (getattr(cfg, "instagram_user_id", "") or "").strip() or self.instagram_user_id
                self.enabled = bool(getattr(cfg, "enabled", False))
                return token
        except Exception:
            return ""
        return ""

    def _resolve_env_token_by_name(self, env_name: str | None) -> str:
        """Resolve token from a configured env var name."""
        if not env_name:
            return ""
        return (os.getenv(env_name) or "").strip()

    def _resolve_meta_config(self, config: Any | None) -> Any | None:
        if config is None:
            return None
        integrations = getattr(config, "integrations", None)
        if integrations is not None:
            meta = getattr(integrations, "meta", None)
            if meta is not None:
                return meta
        meta = getattr(config, "meta", None)
        if meta is not None:
            return meta
        return config

    def _build_threads_create(
        self,
        *,
        text: str | None,
        media_type: str | None,
        image_url: str | None,
        video_url: str | None,
        reply_to_id: str | None,
        extra: dict[str, Any],
        **_: Any,
    ) -> tuple[str, str, dict[str, Any]]:
        user_id = self.threads_user_id
        if not user_id:
            raise ValueError("threads_user_id is missing")
        if not text and not image_url and not video_url:
            raise ValueError("threads_create requires at least one of text, image_url, or video_url")

        payload: dict[str, Any] = {}
        if text:
            payload["text"] = text
        effective_media_type = media_type
        if not effective_media_type:
            if video_url:
                effective_media_type = "VIDEO"
            elif image_url:
                effective_media_type = "IMAGE"
            else:
                effective_media_type = "TEXT"
        payload["media_type"] = effective_media_type
        if image_url:
            payload["image_url"] = image_url
        if video_url:
            payload["video_url"] = video_url
        if reply_to_id:
            payload["reply_control"] = "SELF_ONLY"
            payload["reply_to_id"] = reply_to_id
        payload.update(extra)
        return "POST", f"/{user_id}/threads", payload

    def _build_threads_publish(
        self,
        *,
        creation_id: str | None,
        extra: dict[str, Any],
        **_: Any,
    ) -> tuple[str, str, dict[str, Any]]:
        user_id = self.threads_user_id
        if not user_id:
            raise ValueError("threads_user_id is missing")
        if not creation_id:
            raise ValueError("threads_publish requires creation_id")

        payload = {"creation_id": creation_id}
        payload.update(extra)
        return "POST", f"/{user_id}/threads_publish", payload

    def _build_ig_media_create(
        self,
        *,
        text: str | None,
        image_url: str | None,
        video_url: str | None,
        extra: dict[str, Any],
        **_: Any,
    ) -> tuple[str, str, dict[str, Any]]:
        user_id = self.instagram_user_id
        if not user_id:
            raise ValueError("instagram_user_id is missing")
        if not image_url and not video_url:
            raise ValueError("ig_media_create requires image_url or video_url")

        payload: dict[str, Any] = {}
        if text:
            payload["caption"] = text
        if image_url:
            payload["image_url"] = image_url
        if video_url:
            payload["video_url"] = video_url
        payload.update(extra)
        return "POST", f"/{user_id}/media", payload

    def _build_ig_media_publish(
        self,
        *,
        creation_id: str | None,
        extra: dict[str, Any],
        **_: Any,
    ) -> tuple[str, str, dict[str, Any]]:
        user_id = self.instagram_user_id
        if not user_id:
            raise ValueError("instagram_user_id is missing")
        if not creation_id:
            raise ValueError("ig_media_publish requires creation_id")

        payload = {"creation_id": creation_id}
        payload.update(extra)
        return "POST", f"/{user_id}/media_publish", payload
