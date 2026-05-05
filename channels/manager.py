from __future__ import annotations

from .base import BaseChannel


class ChannelManager:
    """Manages registered channels."""

    def __init__(self) -> None:
        self._channels: dict[str, BaseChannel] = {}

    def register(self, channel: BaseChannel) -> None:
        self._channels[channel.name] = channel

    def get(self, name: str) -> BaseChannel | None:
        return self._channels.get(name)

    def list_channels(self) -> list[str]:
        return list(self._channels.keys())
