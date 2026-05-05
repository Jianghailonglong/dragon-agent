from __future__ import annotations

import asyncio
import uuid
from typing import AsyncIterator

from .base import BaseChannel
from core.types import InboundMessage, OutboundMessage


class WebChannel(BaseChannel):
    """
    Web channel for browser-based chat.
    Uses async queues to bridge HTTP requests and the agent loop.
    """

    def __init__(self) -> None:
        self._chat_id = "web:local"
        self._sender_id = "user"
        self._inbound_queue: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self._outbound_queues: dict[str, asyncio.Queue[OutboundMessage]] = {}

    @property
    def name(self) -> str:
        return "web"

    async def connect(self) -> None:
        pass

    async def receive(self) -> InboundMessage:
        return await self._inbound_queue.get()

    async def send(self, msg: OutboundMessage) -> None:
        # Broadcast to all connected SSE clients
        for queue in self._outbound_queues.values():
            await queue.put(msg)

    async def submit_message(self, content: str) -> str:
        """Submit a user message from HTTP endpoint. Returns request ID."""
        request_id = uuid.uuid4().hex[:8]
        msg = InboundMessage(
            channel="web",
            sender_id=self._sender_id,
            chat_id=self._chat_id,
            content=content,
        )
        await self._inbound_queue.put(msg)
        return request_id

    def register_client(self, client_id: str) -> asyncio.Queue[OutboundMessage]:
        """Register an SSE client and return its message queue."""
        queue: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self._outbound_queues[client_id] = queue
        return queue

    def unregister_client(self, client_id: str) -> None:
        """Unregister an SSE client."""
        self._outbound_queues.pop(client_id, None)

    async def stream_events(self, client_id: str) -> AsyncIterator[str]:
        """Yield SSE events for a client."""
        queue = self.register_client(client_id)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {msg.content}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment to prevent idle disconnect
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            self.unregister_client(client_id)
