from __future__ import annotations

import asyncio
import json
import urllib.request
from typing import Any

from .base import BaseChannel
from core.types import InboundMessage, OutboundMessage


class WeChatChannel(BaseChannel):
    """
    WeChat Official Account / WeCom Bot channel.
    Uses webhook for sending, webhook callback for receiving.
    """

    def __init__(
        self,
        webhook_key: str = "",
        webhook_url: str = "",
        base_url: str = "https://qyapi.weixin.qq.com/cgi-bin",
    ) -> None:
        self._webhook_key = webhook_key
        self._webhook_url = webhook_url
        self._base_url = base_url

    @property
    def name(self) -> str:
        return "wechat"

    async def connect(self) -> None:
        """Verify webhook configuration."""
        if not self._webhook_key and not self._webhook_url:
            print("[wechat] No webhook configured, send-only mode")
        else:
            print("[wechat] Connected")

    async def receive(self) -> InboundMessage:
        """
        Receive messages. In production, use webhook callback.
        This is a stub — use WeChatChannel.handle_event() from your webhook handler.
        """
        raise NotImplementedError(
            "WeChat receive() requires webhook setup. "
            "Use WeChatChannel with an external webhook server that calls "
            "WeChatChannel.handle_event() instead."
        )

    async def send(self, msg: OutboundMessage) -> None:
        """Send message via WeCom webhook."""
        if self._webhook_key:
            url = f"{self._base_url}/webhook/send?key={self._webhook_key}"
        elif self._webhook_url:
            url = self._webhook_url
        else:
            raise ValueError("No webhook configured for WeChatChannel")

        body = {
            "msgtype": "text",
            "text": {"content": msg.content},
        }

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_post, url, body)

    async def handle_event(self, event: dict) -> InboundMessage | None:
        """
        Process a WeChat/WeCom webhook event.
        Call this from your webhook handler.
        """
        msg_type = event.get("MsgType", "")
        if msg_type != "text":
            return None

        return InboundMessage(
            channel="wechat",
            sender_id=event.get("FromUserName", ""),
            chat_id=event.get("ToUserName", ""),
            content=event.get("Content", ""),
            metadata={"msg_id": event.get("MsgId", "")},
        )

    def _sync_post(self, url: str, body: dict) -> dict:
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
