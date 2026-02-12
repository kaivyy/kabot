import litellm
from loguru import logger
from typing import List, Dict, Any, Optional
from kabot.providers.models import ModelMetadata, ModelPricing
from kabot.providers.registry import ModelRegistry, PROVIDERS

class ModelScanner:
    """Scans provider APIs for available models and normalizes metadata."""

    def __init__(self, registry: ModelRegistry, db=None):
        self.registry = registry
        self.db = db

    def scan_provider(self, provider_name: str, api_key: str, api_base: Optional[str] = None) -> List[ModelMetadata]:
        """Fetch models from a specific provider API."""
        logger.info(f"Scanning models for provider: {provider_name}")
        scanned_models = []
        
        try:
            # Use LiteLLM to list models
            response = litellm.utils.get_model_list(
                provider=provider_name,
                api_key=api_key,
                api_base=api_base
            )
            
            for model_id in response:
                full_id = model_id
                if "/" not in model_id:
                    full_id = f"{provider_name}/{model_id}"
                
                metadata = ModelMetadata(
                    id=full_id,
                    name=model_id.split("/")[-1].replace("-", " ").title(),
                    provider=provider_name,
                    is_premium=False
                )
                
                scanned_models.append(metadata)
                self.registry.register(metadata)
                
                if self.db:
                    self.db.save_model({
                        "id": metadata.id,
                        "name": metadata.name,
                        "provider": metadata.provider,
                        "context_window": metadata.context_window,
                        "max_output": metadata.max_output,
                        "pricing_input": metadata.pricing.input_1m,
                        "pricing_output": metadata.pricing.output_1m,
                        "capabilities": metadata.capabilities,
                        "is_premium": metadata.is_premium
                    })
                    
        except Exception as e:
            logger.error(f"Failed to scan models for {provider_name}: {e}")
            
        return scanned_models

    def scan_all(self, config_providers: Dict[str, Any]) -> int:
        """Scan all providers configured in the system."""
        count = 0
        for provider_name, provider_conf in config_providers.items():
            api_key = getattr(provider_conf, "api_key", None)
            if not api_key:
                continue
                
            api_base = getattr(provider_conf, "api_base", None)
            models = self.scan_provider(provider_name, api_key, api_base)
            count += len(models)
            
        return count
