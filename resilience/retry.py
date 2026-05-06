from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable, TypeVar

from providers.base import LLMProvider, LLMResponse
from core.runner import TokenOverflowError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RateLimitError(Exception):
    """API rate limit hit."""
    pass


class LLMAPIError(Exception):
    """Transient LLM API error."""
    pass


class RetryOnion:
    """
    3-Layer Retry Onion:
    - Layer 1: Tool self-correction (errors fed back to LLM, not a code retry)
    - Layer 2: Emergency compaction on TokenOverflowError
    - Layer 3: Key rotation + exponential backoff on RateLimitError / LLMAPIError
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_backoff: float = 1.0,
        max_backoff: float = 30.0,
        auth_profiles: list[str] | None = None,
    ) -> None:
        self._max_retries = max_retries
        self._base_backoff = base_backoff
        self._max_backoff = max_backoff
        self._auth_profiles = auth_profiles or []
        self._current_profile_index = 0

    async def execute_with_retry(
        self,
        fn: Callable[..., Awaitable[T]],
        emergency_compact: Callable[[], list[dict]] | None = None,
        **kwargs,
    ) -> T:
        """
        Execute an async function with retry logic.
        Handles TokenOverflowError (compact), RateLimitError (rotate key), LLMAPIError (backoff).
        """
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                return await fn(**kwargs)
            except TokenOverflowError as e:
                logger.warning(f"Token overflow on attempt {attempt + 1}, compacting...")
                if emergency_compact and "messages" in kwargs:
                    kwargs["messages"] = emergency_compact()
                    continue
                raise
            except RateLimitError as e:
                last_error = e
                self._rotate_auth_profile()
                wait = self._backoff_delay(attempt)
                logger.warning(f"Rate limit hit, rotating key, waiting {wait:.1f}s...")
                await asyncio.sleep(wait)
            except LLMAPIError as e:
                last_error = e
                wait = self._backoff_delay(attempt)
                logger.warning(f"LLM API error on attempt {attempt + 1}, waiting {wait:.1f}s: {e}")
                await asyncio.sleep(wait)

        raise last_error or LLMAPIError("Max retries exceeded")

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter."""
        import random
        delay = min(self._base_backoff * (2 ** attempt), self._max_backoff)
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter

    def _rotate_auth_profile(self) -> None:
        """Rotate to the next auth profile if available."""
        if len(self._auth_profiles) > 1:
            self._current_profile_index = (self._current_profile_index + 1) % len(self._auth_profiles)

    @property
    def current_profile(self) -> str | None:
        if self._auth_profiles:
            return self._auth_profiles[self._current_profile_index]
        return None
