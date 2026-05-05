from __future__ import annotations

from abc import ABC, abstractmethod

from core.types import InboundMessage, OutboundMessage


class BaseChannel(ABC):
    """Abstract base class for communication channels."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Channel identifier (e.g. 'cli', 'telegram', 'feishu')."""

    @abstractmethod
    async def connect(self) -> None:
        """Initialize the channel connection."""

    @abstractmethod
    async def receive(self) -> InboundMessage:
        """Wait for and return the next inbound message."""

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """Send an outbound message through this channel."""

    async def disconnect(self) -> None:
        """Clean up channel resources."""
