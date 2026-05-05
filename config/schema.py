from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """LLM provider configuration."""
    type: str = "anthropic"  # "anthropic" | "openai_compat"
    model: str = "claude-sonnet-4-20250514"
    api_key: str = ""
    base_url: str | None = None
    max_tokens: int = 4096


class AgentConfig(BaseModel):
    """Per-agent configuration."""
    name: str = "default"
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    model: str | None = None  # override provider.model if set
    max_iterations: int = 20
    context_window_tokens: int = 200_000
    concurrent_tools: bool = True
    system_prompt_extra: str = ""


class DragonConfig(BaseModel):
    """Top-level configuration."""
    workspace: str = "./workspace"
    agents: dict[str, AgentConfig] = Field(default_factory=lambda: {"default": AgentConfig()})
    default_agent: str = "default"
    concurrency_limit: int = 4
    session_idle_compact_minutes: int = 30
