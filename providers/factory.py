from __future__ import annotations

from config.schema import ProviderConfig
from .base import LLMProvider
from .anthropic import AnthropicProvider


class ProviderFactory:
    """Create LLM providers from configuration."""

    @staticmethod
    def create(config: ProviderConfig) -> LLMProvider:
        model = config.model or "claude-sonnet-4-20250514"

        if config.type == "anthropic":
            return AnthropicProvider(api_key=config.api_key, model=model, base_url=config.base_url)
        else:
            raise ValueError(f"Unknown provider type: {config.type}")
