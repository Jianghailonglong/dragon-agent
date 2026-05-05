from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

import lark_oapi as lark
from lark_oapi.ws import Client as WsClient

from .base import BaseChannel
from core.types import InboundMessage, OutboundMessage


class FeishuChannel(BaseChannel):
    """
    Feishu (Lark) Bot channel using WebSocket long connection.
    No need for public IP or webhook setup.
    """

    def __init__(
        self,
        app_id: str,
        app_secret: str,
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._message_queue: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self._ws_client: WsClient | None = None
        self._api_client: lark.Client | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def name(self) -> str:
        return "feishu"

    async def connect(self) -> None:
        """Start WebSocket long connection."""
        print("[feishu] Connecting via WebSocket...")

        # Get the current event loop
        self._loop = asyncio.get_event_loop()

        # Create API client for sending messages FIRST
        self._api_client = lark.Client.builder() \
            .app_id(self._app_id) \
            .app_secret(self._app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()

        # Verify API client is ready
        if not self._api_client:
            raise RuntimeError("Failed to initialize Feishu API client")

        print("[feishu] API client initialized")

        # Create event handler for receiving messages
        handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._handle_message)
            .build()
        )

        # Create WebSocket client for receiving messages
        self._ws_client = WsClient(
            app_id=self._app_id,
            app_secret=self._app_secret,
            event_handler=handler,
            log_level=lark.LogLevel.INFO,
        )

        # Start WebSocket client in background thread
        # WsClient.start() uses a global loop variable from lark_oapi.ws.client module
        # We need to create a new event loop for this thread and set it as the global loop
        def run_client():
            import lark_oapi.ws.client as ws_module
            # Create a new event loop for this thread
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            # Override the global loop in the module
            ws_module.loop = new_loop
            try:
                self._ws_client.start()
            except Exception as e:
                print(f"[feishu] WebSocket client error: {e}")
            finally:
                new_loop.close()

        thread = threading.Thread(target=run_client, daemon=True)
        thread.start()

        print("[feishu] WebSocket client started")
        print("[feishu] Ready to send and receive messages")

    def _handle_message(self, data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        """Handle incoming message from Feishu."""
        msg = data.event.message
        content_str = msg.content or "{}"
        try:
            content = json.loads(content_str).get("text", "")
        except json.JSONDecodeError:
            content = content_str

        # Remove @mention prefix if present
        if content.startswith("@"):
            parts = content.split(" ", 1)
            if len(parts) > 1:
                content = parts[1]

        # Get sender info
        sender_id = ""
        if data.event.sender and data.event.sender.sender_id:
            sender_id = data.event.sender.sender_id.open_id or ""

        # Get chat ID
        chat_id = msg.chat_id or ""

        # Create InboundMessage
        inbound_msg = InboundMessage(
            channel="feishu",
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            metadata={"message_id": msg.message_id},
        )

        # Put message in queue (need to handle async in sync callback)
        asyncio.run_coroutine_threadsafe(
            self._message_queue.put(inbound_msg),
            self._loop,
        )

    async def handle_event(self, event: dict) -> InboundMessage | None:
        """
        Handle a raw event dict (from webhook or test).
        Returns InboundMessage for message events, None for other event types.
        """
        event_type = event.get("header", {}).get("event_type", "")
        if event_type != "im.message.receive_v1":
            return None

        event_data = event.get("event", {})
        msg = event_data.get("message", {})
        sender = event_data.get("sender", {})

        content_str = msg.get("content", "{}")
        try:
            content = json.loads(content_str).get("text", "")
        except json.JSONDecodeError:
            content = content_str

        # Remove @mention prefix if present
        if content.startswith("@"):
            parts = content.split(" ", 1)
            if len(parts) > 1:
                content = parts[1]

        sender_id = sender.get("sender_id", {}).get("open_id", "")
        chat_id = msg.get("chat_id", "")
        message_id = msg.get("message_id", "")

        return InboundMessage(
            channel="feishu",
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            metadata={"message_id": message_id},
        )

    async def receive(self) -> InboundMessage:
        """Receive message from queue."""
        try:
            return await self._message_queue.get()
        except asyncio.CancelledError:
            # Graceful shutdown on Ctrl+C
            raise SystemExit(0)

    async def send(self, msg: OutboundMessage) -> None:
        """Send message via Feishu API."""
        if not self._api_client:
            raise RuntimeError("Feishu API client not connected")

        # Build request
        request = (
            lark.im.v1.CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                lark.im.v1.CreateMessageRequestBody.builder()
                .receive_id(msg.chat_id)
                .msg_type("text")
                .content(json.dumps({"text": msg.content}))
                .build()
            )
            .build()
        )

        # Send message
        response = self._api_client.im.v1.message.create(request)

        if not response.success():
            print(f"[feishu] Failed to send message: {response.msg}")

    async def disconnect(self) -> None:
        """Disconnect from Feishu."""
        if self._ws_client:
            self._ws_client.stop()
            self._ws_client = None
        self._api_client = None
