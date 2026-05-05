from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    stop_reason: str = ""  # "end_turn" | "tool_use" | "max_tokens"
    usage: dict = field(default_factory=dict)  # {"input_tokens": N, "output_tokens": N}

    @property
    def should_execute_tools(self) -> bool:
        return self.stop_reason == "tool_use" and len(self.tool_calls) > 0


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a chat completion request and return the full response."""

    @abstractmethod
    async def stream_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
        on_delta: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        """Stream a chat completion, calling on_delta for each text chunk."""
