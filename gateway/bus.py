from __future__ import annotations

import asyncio

from core.types import InboundMessage, OutboundMessage


class MessageBus:
    """Async message bus with inbound and outbound queues."""

    def __init__(self, maxsize: int = 100) -> None:
        self._inbound: asyncio.Queue[InboundMessage] = asyncio.Queue(maxsize=maxsize)
        self._outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue(maxsize=maxsize)

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish an inbound message (from channels)."""
        await self._inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        return await self._inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Publish an outbound message (from agent)."""
        await self._outbound.put(msg)

    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message (blocks until available)."""
        return await self._outbound.get()

    def inbound_empty(self) -> bool:
        return self._inbound.empty()

    def outbound_empty(self) -> bool:
        return self._outbound.empty()

    def inbound_size(self) -> int:
        return self._inbound.qsize()

    def outbound_size(self) -> int:
        return self._outbound.qsize()
