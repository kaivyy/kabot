from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class ModelPricing(BaseModel):
    """Pricing metadata for a model (USD per 1M tokens)."""
    input_1m: float = 0.0
    output_1m: float = 0.0
    cache_read_1m: Optional[float] = None
    cache_write_1m: Optional[float] = None

class ModelMetadata(BaseModel):
    """Comprehensive metadata for an AI model."""
    id: str  # Unique identifier (e.g. "openai/gpt-4o")
    name: str  # Display name
    provider: str  # Provider ID (e.g. "openai")
    context_window: int = 8192
    max_output: Optional[int] = None
    pricing: ModelPricing = Field(default_factory=ModelPricing)
    capabilities: List[str] = [] # vision, tools, reasoning, json
    is_premium: bool = False # Whether it's part of the static catalog
    description: Optional[str] = None
    
    @property
    def short_id(self) -> str:
        """Returns the ID without the provider prefix if present."""
        if "/" in self.id:
            return self.id.split("/", 1)[1]
        return self.id
