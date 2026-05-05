import pytest
import asyncio

from gateway.bus import MessageBus
from core.types import InboundMessage, OutboundMessage


@pytest.mark.asyncio
async def test_bus_inbound_roundtrip():
    bus = MessageBus()
    msg = InboundMessage(channel="cli", sender_id="u", chat_id="c", content="hi")
    await bus.publish_inbound(msg)
    assert bus.inbound_size() == 1
    got = await bus.consume_inbound()
    assert got.content == "hi"
    assert bus.inbound_empty()


@pytest.mark.asyncio
async def test_bus_outbound_roundtrip():
    bus = MessageBus()
    msg = OutboundMessage(channel="cli", chat_id="c", content="reply")
    await bus.publish_outbound(msg)
    assert bus.outbound_size() == 1
    got = await bus.consume_outbound()
    assert got.content == "reply"


@pytest.mark.asyncio
async def test_bus_fifo_order():
    bus = MessageBus()
    for i in range(3):
        await bus.publish_inbound(InboundMessage(channel="cli", sender_id="u", chat_id="c", content=str(i)))

    results = []
    for _ in range(3):
        msg = await bus.consume_inbound()
        results.append(msg.content)
    assert results == ["0", "1", "2"]
