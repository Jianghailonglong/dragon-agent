"""Tests for ResilientProvider."""
import pytest

from providers.base import LLMProvider, LLMResponse
from resilience.provider_wrapper import ResilientProvider, wrap_provider_with_retry
from resilience.retry import RetryOnion, RateLimitError, LLMAPIError, TokenOverflowError


class FlakyProvider(LLMProvider):
    """Provider that fails N times then succeeds."""
    def __init__(self, fail_count: int, error_type: type = Exception):
        self._fail_count = fail_count
        self._error_type = error_type
        self._calls = 0

    async def chat_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096):
        self._calls += 1
        if self._calls <= self._fail_count:
            raise self._error_type(f"fail #{self._calls}")
        return LLMResponse(content="ok", stop_reason="end_turn", usage={})

    async def stream_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096, on_delta=None):
        return await self.chat_completion(messages, tools, model, system, max_tokens)


class GoodProvider(LLMProvider):
    async def chat_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096):
        return LLMResponse(content="hello", stop_reason="end_turn", usage={"input_tokens": 1, "output_tokens": 1})

    async def stream_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096, on_delta=None):
        return await self.chat_completion(messages, tools, model, system, max_tokens)


def _make_resilient(provider, max_retries=3, base_backoff=0.01):
    retry = RetryOnion(max_retries=max_retries, base_backoff=base_backoff, max_backoff=0.05)
    return ResilientProvider(provider, retry=retry)


@pytest.mark.asyncio
async def test_resilient_provider_success():
    provider = wrap_provider_with_retry(GoodProvider())
    resp = await provider.chat_completion(messages=[{"role": "user", "content": "hi"}])
    assert resp.content == "hello"


@pytest.mark.asyncio
async def test_resilient_provider_retries_on_rate_limit():
    flaky = FlakyProvider(fail_count=2, error_type=RateLimitError)
    provider = _make_resilient(flaky)
    resp = await provider.chat_completion(messages=[{"role": "user", "content": "hi"}])
    assert resp.content == "ok"
    assert flaky._calls == 3


@pytest.mark.asyncio
async def test_resilient_provider_retries_on_api_error():
    flaky = FlakyProvider(fail_count=1, error_type=LLMAPIError)
    provider = _make_resilient(flaky)
    resp = await provider.chat_completion(messages=[{"role": "user", "content": "hi"}])
    assert resp.content == "ok"
    assert flaky._calls == 2


@pytest.mark.asyncio
async def test_resilient_provider_raises_on_token_overflow():
    flaky = FlakyProvider(fail_count=1, error_type=TokenOverflowError)
    provider = _make_resilient(flaky)
    with pytest.raises(TokenOverflowError):
        await provider.chat_completion(messages=[{"role": "user", "content": "hi"}])
    assert flaky._calls == 1


@pytest.mark.asyncio
async def test_resilient_provider_exhausts_retries():
    flaky = FlakyProvider(fail_count=5, error_type=LLMAPIError)
    provider = _make_resilient(flaky, max_retries=2)
    with pytest.raises(LLMAPIError):
        await provider.chat_completion(messages=[{"role": "user", "content": "hi"}])
    assert flaky._calls == 3
