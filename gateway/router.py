from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any

import yaml

from core.types import InboundMessage
from config.schema import AgentConfig


class TierPriority(IntEnum):
    """5-tier binding priority (lower = higher priority)."""
    PEER = 1      # channel + chat_id + sender_id
    GUILD = 2     # channel + chat_id
    ACCOUNT = 3   # channel + sender_id
    CHANNEL = 4   # channel only
    DEFAULT = 5   # fallback


@dataclass
class Binding:
    """A routing binding that maps messages to agent configs."""
    tier: str
    agent: str
    channel: str | None = None
    chat_id: str | None = None
    sender_id: str | None = None

    @property
    def tier_priority(self) -> TierPriority:
        return TierPriority[self.tier.upper()]

    def matches(self, msg: InboundMessage) -> bool:
        """Check if this binding matches the given message."""
        if self.channel and self.channel != msg.channel:
            return False
        if self.chat_id and self.chat_id != msg.chat_id:
            return False
        if self.sender_id and self.sender_id != msg.sender_id:
            return False
        return True


class GatewayRouter:
    """
    5-tier binding router: peer > guild > account > channel > default.
    Resolves messages to agent configurations.
    """

    def __init__(self, default_agent: str = "default") -> None:
        self._bindings: list[Binding] = []
        self._default_agent = default_agent

    def add_binding(self, binding: Binding) -> None:
        """Add a routing binding."""
        self._bindings.append(binding)
        # Keep sorted by priority
        self._bindings.sort(key=lambda b: b.tier_priority)

    def resolve(self, msg: InboundMessage) -> str:
        """
        Resolve message to an agent name.
        Returns the agent name from the highest-priority matching binding.
        """
        for binding in self._bindings:
            if binding.matches(msg):
                return binding.agent
        return self._default_agent

    @classmethod
    def from_yaml(cls, path: str | Path, default_agent: str = "default") -> GatewayRouter:
        """Load bindings from a YAML file."""
        p = Path(path)
        router = cls(default_agent=default_agent)

        if not p.exists():
            return router

        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        for entry in data.get("bindings", []):
            router.add_binding(Binding(
                tier=entry.get("tier", "default"),
                agent=entry.get("agent", default_agent),
                channel=entry.get("channel"),
                chat_id=entry.get("chat_id"),
                sender_id=entry.get("sender_id"),
            ))

        return router

    @property
    def bindings(self) -> list[Binding]:
        return list(self._bindings)
