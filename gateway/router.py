from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any

import yaml

from core.types import InboundMessage
from config.schema import AgentConfig

logger = logging.getLogger(__name__)


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

    def __init__(
        self,
        default_agent: str = "default",
        configs: dict[str, AgentConfig] | None = None,
    ) -> None:
        self._bindings: list[Binding] = []
        self._default_agent = default_agent
        self._configs: dict[str, AgentConfig] = configs or {}
        # Ensure default config exists
        if default_agent not in self._configs:
            self._configs[default_agent] = AgentConfig(name=default_agent)

    def add_binding(self, binding: Binding) -> None:
        """Add a routing binding."""
        self._bindings.append(binding)
        # Keep sorted by priority
        self._bindings.sort(key=lambda b: b.tier_priority)

    def resolve(self, msg: InboundMessage) -> AgentConfig:
        """
        Resolve message to an AgentConfig.
        Returns the config from the highest-priority matching binding.
        Falls back to default config if no binding matches or config not found.
        """
        for binding in self._bindings:
            if binding.matches(msg):
                config = self._configs.get(binding.agent)
                if config:
                    return config
                logger.warning(f"Agent config '{binding.agent}' not found, using default")
                return self._configs[self._default_agent]
        return self._configs[self._default_agent]

    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
        default_agent: str = "default",
        configs_dir: str | Path | None = None,
    ) -> GatewayRouter:
        """Load bindings from a YAML file, optionally loading agent configs from a directory."""
        p = Path(path)
        configs: dict[str, AgentConfig] = {}

        # Load agent configs from directory if provided
        if configs_dir:
            configs_path = Path(configs_dir)
            if configs_path.is_dir():
                for config_file in configs_path.glob("*.yaml"):
                    agent_name = config_file.stem
                    try:
                        agent_data = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
                        configs[agent_name] = AgentConfig(name=agent_name, **agent_data)
                    except Exception as e:
                        logger.warning(f"Failed to load agent config {config_file}: {e}")

        router = cls(default_agent=default_agent, configs=configs)

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
