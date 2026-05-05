from __future__ import annotations

import logging
from typing import Callable

from providers.base import LLMProvider, LLMResponse
from .retry import RetryOnion, RateLimitError, LLMAPIError, TokenOverflowError

logger = logging.getLogger(__name__)


def _map_exception(e: Exception) -> Exception:
    """Map provider-specific exceptions to retry-friendly exceptions."""
    try:
        import anthropic
        if isinstance(e, anthropic.RateLimitError):
            return RateLimitError(str(e))
        if isinstance(e, anthropic.BadRequestError) and "too long" in str(e).lower():
            return TokenOverflowError(str(e))
        if isinstance(e, (anthropic.APIStatusError, anthropic.APIConnectionError, anthropic.APITimeoutError)):
            return LLMAPIError(str(e))
    except ImportError:
        pass

    msg = str(e).lower()
    if "rate limit" in msg or "429" in msg:
        return RateLimitError(str(e))
    if "too long" in msg or "context length" in msg:
        return TokenOverflowError(str(e))
    return e


class ResilientProvider(LLMProvider):
    """
    Wraps an LLMProvider with RetryOnion for automatic retry on API errors.
    """

    def __init__(self, inner: LLMProvider, retry: RetryOnion | None = None) -> None:
        self._inner = inner
        self._retry = retry or RetryOnion()

    async def chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        async def _call():
            try:
                return await self._inner.chat_completion(
                    messages=messages, tools=tools, model=model,
                    system=system, max_tokens=max_tokens,
                )
            except Exception as e:
                raise _map_exception(e) from e

        return await self._retry.execute_with_retry(_call)

    async def stream_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
        on_delta: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        return await self._inner.stream_completion(
            messages=messages, tools=tools, model=model,
            system=system, max_tokens=max_tokens, on_delta=on_delta,
        )


def wrap_provider_with_retry(provider: LLMProvider, max_retries: int = 3) -> ResilientProvider:
    """Convenience: wrap a provider with default retry settings."""
    return ResilientProvider(provider, retry=RetryOnion(max_retries=max_retries))
