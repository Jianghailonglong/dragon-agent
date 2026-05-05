from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class InboundMessage:
    """Unified inbound message from any channel."""
    channel: str  # "telegram" | "feishu" | "wechat" | "cli"
    sender_id: str
    chat_id: str
    content: str
    media: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    session_key_override: str | None = None

    @property
    def session_key(self) -> str:
        return self.session_key_override or f"{self.channel}:{self.chat_id}"


@dataclass
class OutboundMessage:
    """Unified outbound message to any channel."""
    channel: str
    chat_id: str
    content: str
    metadata: dict = field(default_factory=dict)
