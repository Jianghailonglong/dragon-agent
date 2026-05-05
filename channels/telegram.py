from __future__ import annotations

import asyncio
import json
import urllib.request
import urllib.parse
from typing import Any

from .base import BaseChannel
from core.types import InboundMessage, OutboundMessage


class TelegramChannel(BaseChannel):
    """
    Telegram Bot API channel.
    Uses long-polling to receive messages.
    """

    def __init__(self, token: str, allowed_chat_ids: list[str] | None = None) -> None:
        self._token = token
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._offset: int = 0
        self._allowed_chat_ids = allowed_chat_ids  # None = allow all

    @property
    def name(self) -> str:
        return "telegram"

    async def connect(self) -> None:
        """Verify bot token by calling getMe."""
        result = await self._api_call("getMe")
        if not result.get("ok"):
            raise ConnectionError(f"Telegram bot auth failed: {result}")
        bot_name = result.get("result", {}).get("username", "unknown")
        print(f"[telegram] Connected as @{bot_name}")

    async def receive(self) -> InboundMessage:
        """Long-poll for the next message."""
        while True:
            params = {"offset": self._offset, "timeout": 30}
            updates = await self._api_call("getUpdates", params)

            for update in updates.get("result", []):
                self._offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg:
                    continue

                chat_id = str(msg["chat"]["id"])
                if self._allowed_chat_ids and chat_id not in self._allowed_chat_ids:
                    continue

                text = msg.get("text", "")
                if not text:
                    continue

                return InboundMessage(
                    channel="telegram",
                    sender_id=str(msg.get("from", {}).get("id", "")),
                    chat_id=chat_id,
                    content=text,
                    metadata={"message_id": msg.get("message_id")},
                )

    async def send(self, msg: OutboundMessage) -> None:
        """Send message via Telegram Bot API."""
        await self._api_call("sendMessage", {
            "chat_id": msg.chat_id,
            "text": msg.content,
            "parse_mode": "Markdown",
        })

    async def _api_call(self, method: str, params: dict | None = None) -> dict:
        """Make a Telegram Bot API call in a thread."""
        url = f"{self._base_url}/{method}"
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_api_call, url, params or {})

    def _sync_api_call(self, url: str, params: dict) -> dict:
        data = json.dumps(params).encode() if params else None
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"} if data else {},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
