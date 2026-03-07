"""Image generation tool using multi-provider support."""

from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.tools.base import Tool


class ImageGenTool(Tool):
    """Tool to generate images using various AI providers."""

    name = "image_gen"
    description = "Generate an image from a text prompt and return the local file path."
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Descriptive prompt for the image"
            },
            "provider": {
                "type": "string",
                "description": "Provider to use: 'openai' (DALL-E 3) or 'gemini' (Imagen)",
                "enum": ["openai", "gemini"],
                "default": "openai"
            },
            "size": {
                "type": "string",
                "description": "Image size (e.g., '1024x1024')",
                "default": "1024x1024"
            }
        },
        "required": ["prompt"]
    }

    def __init__(self, workspace: Path, config: Any):
        self.workspace = workspace
        self.config = config
        self.media_dir = workspace / "media"
        self.media_dir.mkdir(parents=True, exist_ok=True)

    def _default_model(self) -> str:
        defaults = getattr(getattr(self.config, "agents", None), "defaults", None)
        return str(getattr(defaults, "model", "") or "").strip()

    def _resolve_openai_credentials(self) -> tuple[str, str | None]:
        providers = getattr(self.config, "providers", None)
        openai_cfg = getattr(providers, "openai", None)
        api_key = str(getattr(openai_cfg, "api_key", "") or "").strip()

        get_api_key = getattr(self.config, "get_api_key", None)
        if not api_key and callable(get_api_key):
            api_key = str(get_api_key(self._default_model()) or "").strip()
        if not api_key and callable(get_api_key):
            api_key = str(get_api_key("openai/dall-e-3") or "").strip()

        api_base = str(getattr(openai_cfg, "api_base", "") or "").strip() or None
        get_api_base = getattr(self.config, "get_api_base", None)
        if not api_base and callable(get_api_base):
            api_base = str(get_api_base(self._default_model()) or "").strip() or None
        if not api_base and callable(get_api_base):
            api_base = str(get_api_base("openai/dall-e-3") or "").strip() or None
        return api_key, api_base

    def _resolve_gemini_api_key(self) -> str:
        providers = getattr(self.config, "providers", None)
        gemini_cfg = getattr(providers, "gemini", None)
        api_key = str(getattr(gemini_cfg, "api_key", "") or "").strip()
        get_api_key = getattr(self.config, "get_api_key", None)
        if not api_key and callable(get_api_key):
            api_key = str(get_api_key("gemini/gemini-2.0-flash") or "").strip()
        return api_key

    async def execute(self, prompt: str, provider: str | None = None, size: str = "1024x1024", **kwargs: Any) -> str:
        """Execute image generation with smart fallback."""
        try:
            import uuid
            filename = f"gen_{uuid.uuid4().hex[:8]}.png"
            file_path = self.media_dir / filename

            # SMART PROVIDER SELECTION
            # 1. Check which providers are actually configured
            openai_api_key, openai_api_base = self._resolve_openai_credentials()
            gemini_api_key = self._resolve_gemini_api_key()
            has_openai = bool(openai_api_key)
            has_gemini = bool(gemini_api_key)

            # 2. Determine which one to try first
            target_provider = provider.lower() if provider else ("openai" if has_openai else "gemini")

            # 3. Execution logic with fallback
            if target_provider == "openai":
                if has_openai:
                    return await self._generate_openai(
                        prompt,
                        size,
                        file_path,
                        api_key=openai_api_key,
                        api_base=openai_api_base,
                    )
                elif has_gemini:
                    logger.info("OpenAI not configured, falling back to Gemini")
                    return await self._generate_gemini(prompt, size, file_path, api_key=gemini_api_key)

            if target_provider == "gemini":
                if has_gemini:
                    return await self._generate_gemini(prompt, size, file_path, api_key=gemini_api_key)
                elif has_openai:
                    logger.info("Gemini not configured, falling back to OpenAI")
                    return await self._generate_openai(
                        prompt,
                        size,
                        file_path,
                        api_key=openai_api_key,
                        api_base=openai_api_base,
                    )

            return i18n_t("image_gen.provider_missing", prompt)

        except Exception as e:
            logger.error(f"Image gen failed: {e}")
            return i18n_t("image_gen.error", prompt, error=str(e))

    async def _generate_openai(
        self,
        prompt: str,
        size: str,
        output_path: Path,
        *,
        api_key: str,
        api_base: str | None = None,
    ) -> str:
        """Generate image via OpenAI DALL-E 3."""
        endpoint_base = str(api_base or "https://api.openai.com/v1").rstrip("/")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{endpoint_base}/images/generations",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": "dall-e-3", "prompt": prompt, "n": 1, "size": size},
                timeout=60.0
            )
            if response.status_code != 200:
                raise Exception(f"OpenAI Error: {response.text}")

            image_url = response.json()["data"][0]["url"]
            img_res = await client.get(image_url)
            output_path.write_bytes(img_res.content)
            return f"Image generated via OpenAI: {output_path.resolve()}"

    async def _generate_gemini(
        self,
        prompt: str,
        size: str,
        output_path: Path,
        *,
        api_key: str | None = None,
    ) -> str:
        """Generate image via Google Gemini (Imagen)."""
        # Use the Google Generative AI endpoint for Imagen
        async with httpx.AsyncClient():
            # Note: Imagen API typically uses a different endpoint or requires Vertex AI.
            # This implementation uses the standard Google AI Studio logic if available.
            # Placeholder for exact payload structure of Imagen 3
            # If the user has access to Imagen via AI Studio, the call would go here.
            # For now, if Imagen call fails, we provide a clear technical error.
            return i18n_t("image_gen.provider_unavailable", prompt, provider="Gemini")
