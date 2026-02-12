"""Tests for Model Registry and Metadata."""
import pytest
from kabot.providers.models import ModelMetadata, ModelPricing
from kabot.providers.registry import ModelRegistry

def test_model_metadata_creation():
    """Verify ModelMetadata can be instantiated."""
    metadata = ModelMetadata(
        id="openai/gpt-4o",
        name="GPT-4o",
        provider="openai",
        context_window=128000,
        pricing=ModelPricing(input_1m=5.0, output_1m=15.0),
        capabilities=["vision", "tools"]
    )
    assert metadata.id == "openai/gpt-4o"
    assert metadata.short_id == "gpt-4o"
    assert metadata.pricing.input_1m == 5.0

def test_registry_singleton_or_instance():
    """Verify ModelRegistry instance can be created."""
    registry = ModelRegistry()
    assert registry is not None

def test_register_and_get_model():
    """Test registering and retrieving a model from the registry."""
    registry = ModelRegistry()
    metadata = ModelMetadata(
        id="test/model",
        name="Test Model",
        provider="test",
        context_window=4096,
        pricing=ModelPricing()
    )
    registry.register(metadata)
    
    retrieved = registry.get_model("test/model")
    assert retrieved == metadata
    assert retrieved.name == "Test Model"

def test_get_non_existent_model():
    """Verify registry returns None for unknown models."""
    registry = ModelRegistry()
    assert registry.get_model("unknown/model") is None

def test_list_models():
    """Test listing models in the registry."""
    registry = ModelRegistry()
    registry.clear() # Start clean
    
    m1 = ModelMetadata(id="p1/m1", name="M1", provider="p1", context_window=1, pricing=ModelPricing())
    m2 = ModelMetadata(id="p2/m2", name="M2", provider="p2", context_window=1, pricing=ModelPricing())
    
    registry.register(m1)
    registry.register(m2)
    
    models = registry.list_models()
    assert len(models) == 2
    ids = [m.id for m in models]
    assert "p1/m1" in ids
    assert "p2/m2" in ids
