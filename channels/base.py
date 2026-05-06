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

    def start_spinner(self, message: str = "Thinking") -> None:
        """Show a loading indicator (optional, no-op by default)."""

    def stop_spinner(self) -> None:
        """Hide the loading indicator (optional, no-op by default)."""

    async def disconnect(self) -> None:
        """Clean up channel resources."""
