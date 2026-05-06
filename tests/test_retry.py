import pytest
import asyncio

from resilience.retry import RetryOnion, RateLimitError, LLMAPIError
from core.runner import TokenOverflowError


@pytest.mark.asyncio
async def test_retry_success_first_attempt():
    onion = RetryOnion(max_retries=3)
    call_count = 0

    async def fn():
        nonlocal call_count
        call_count += 1
        return "ok"

    result = await onion.execute_with_retry(fn)
    assert result == "ok"
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_on_api_error():
    onion = RetryOnion(max_retries=2, base_backoff=0.01, max_backoff=0.05)
    call_count = 0

    async def fn():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise LLMAPIError("transient error")
        return "ok"

    result = await onion.execute_with_retry(fn)
    assert result == "ok"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_exhausted():
    onion = RetryOnion(max_retries=1, base_backoff=0.01, max_backoff=0.01)

    async def fn():
        raise LLMAPIError("always fails")

    with pytest.raises(LLMAPIError):
        await onion.execute_with_retry(fn)


@pytest.mark.asyncio
async def test_retry_rate_limit_rotates_key():
    onion = RetryOnion(max_retries=2, base_backoff=0.01, auth_profiles=["key1", "key2", "key3"])
    call_count = 0

    async def fn():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RateLimitError("rate limited")
        return "ok"

    result = await onion.execute_with_retry(fn)
    assert result == "ok"


@pytest.mark.asyncio
async def test_retry_token_overflow_compacts():
    onion = RetryOnion(max_retries=1, base_backoff=0.01)
    messages = [{"role": "user", "content": "x" * 1000}]
    compacted = False

    async def fn(messages=None):
        nonlocal compacted
        if not compacted:
            raise TokenOverflowError("too many tokens")
        return "compacted"

    def compact():
        nonlocal compacted
        compacted = True
        return [{"role": "user", "content": "short"}]

    result = await onion.execute_with_retry(fn, emergency_compact=compact, messages=messages)
    assert result == "compacted"


def test_current_profile():
    onion = RetryOnion(auth_profiles=["k1", "k2"])
    assert onion.current_profile == "k1"
    onion._rotate_auth_profile()
    assert onion.current_profile == "k2"
    onion._rotate_auth_profile()
    assert onion.current_profile == "k1"
