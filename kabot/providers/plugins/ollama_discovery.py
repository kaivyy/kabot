import json
import logging
import os
import urllib.error
import urllib.request

from kabot.providers.models import ModelMetadata, ModelPricing

logger = logging.getLogger(__name__)


def register(registry):
    """
    Auto-discover models from local Ollama instance.
    Checks OLLAMA_HOST or defaults to http://127.0.0.1:11434.
    """
    # Detect configured host
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    tags_url = f"{host}/api/tags"

    try:
        req = urllib.request.Request(tags_url)
        # Use a short timeout so we don't block startup if Ollama isn't running
        with urllib.request.urlopen(req, timeout=2.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                models = data.get("models", [])

                for model_data in models:
                    model_name = model_data.get("name")
                    if not model_name:
                        continue

                    # Provide defaults for Ollama models
                    # Vision/Tools capabilities are often model-dependent, but we can assume "chat" as baseline.
                    capabilities = ["chat"]

                    # Heuristics for capabilities (e.g. llama3.2-vision, qwen2.5-coder)
                    name_lower = model_name.lower()
                    if "vision" in name_lower or "llava" in name_lower:
                        capabilities.append("vision")
                    if "coder" in name_lower or "code" in name_lower or "starcoder" in name_lower or "qwen2.5-coder" in name_lower:
                        capabilities.append("coding")
                    if "r1" in name_lower or "reasoning" in name_lower or "think" in name_lower:
                        capabilities.append("reasoning")

                    # Register the discovered model
                    metadata = ModelMetadata(
                        id=f"ollama/{model_name}",
                        name=model_name,
                        provider="ollama",
                        context_window=128000, # Defaulting to a safe large context for modern local models
                        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
                        capabilities=capabilities,
                        is_premium=False
                    )
                    registry.register(metadata)

                if models:
                    logger.debug(f"Auto-discovered {len(models)} models from local Ollama instance")

    except (urllib.error.URLError, TimeoutError, ConnectionRefusedError, OSError):
        # Ollama is likely not running or unreachable, skip discovery silently
        pass
    except Exception as e:
        logger.debug(f"Failed to discover Ollama models: {e}")
