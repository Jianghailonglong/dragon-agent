import pytest
import asyncio
from pathlib import Path

from resilience.delivery import DeliveryQueue
from core.types import OutboundMessage


@pytest.fixture
def delivery_dir(tmp_path):
    return str(tmp_path / "deliveries")


@pytest.mark.asyncio
async def test_delivery_success(delivery_dir):
    sent = []

    async def send_fn(msg):
        sent.append(msg)

    queue = DeliveryQueue(storage_dir=delivery_dir, send_fn=send_fn)
    msg = OutboundMessage(channel="cli", chat_id="c1", content="hello")
    entry_id = await queue.enqueue(msg)

    assert len(sent) == 1
    assert sent[0].content == "hello"
    assert queue.pending_count() == 0  # delivered and removed


@pytest.mark.asyncio
async def test_delivery_failure_persists(delivery_dir):
    async def send_fn(msg):
        raise ConnectionError("network down")

    queue = DeliveryQueue(storage_dir=delivery_dir, send_fn=send_fn)
    msg = OutboundMessage(channel="cli", chat_id="c1", content="hello")
    await queue.enqueue(msg)

    assert queue.pending_count() == 1
    # Verify persisted on disk
    files = list(Path(delivery_dir).glob("del_*.json"))
    assert len(files) == 1


@pytest.mark.asyncio
async def test_retry_pending_succeeds(delivery_dir):
    fail_count = 0

    async def send_fn(msg):
        nonlocal fail_count
        fail_count += 1
        if fail_count <= 1:
            raise ConnectionError("first attempt fails")

    queue = DeliveryQueue(storage_dir=delivery_dir, send_fn=send_fn)
    msg = OutboundMessage(channel="cli", chat_id="c1", content="hello")
    await queue.enqueue(msg)
    assert queue.pending_count() == 1

    # Retry — should succeed now
    success = await queue.retry_pending()
    assert success == 1
    assert queue.pending_count() == 0


@pytest.mark.asyncio
async def test_delivery_max_attempts_drops(delivery_dir):
    async def send_fn(msg):
        raise ConnectionError("always fails")

    queue = DeliveryQueue(storage_dir=delivery_dir, send_fn=send_fn)
    msg = OutboundMessage(channel="cli", chat_id="c1", content="hello")
    await queue.enqueue(msg)

    # Retry until max attempts
    for _ in range(5):
        await queue.retry_pending()

    # Should be dropped after max_attempts
    assert queue.pending_count() == 0


@pytest.mark.asyncio
async def test_delivery_load_from_disk(delivery_dir):
    async def send_fn(msg):
        raise ConnectionError("fail")

    # Create a pending delivery
    queue1 = DeliveryQueue(storage_dir=delivery_dir, send_fn=send_fn)
    await queue1.enqueue(OutboundMessage(channel="cli", chat_id="c1", content="persisted"))

    # New queue instance — should load from disk
    sent = []

    async def send_fn_ok(msg):
        sent.append(msg)

    queue2 = DeliveryQueue(storage_dir=delivery_dir, send_fn=send_fn_ok)
    assert queue2.pending_count() == 1

    success = await queue2.retry_pending()
    assert success == 1
    assert sent[0].content == "persisted"
