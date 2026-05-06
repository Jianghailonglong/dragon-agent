import pytest
from pathlib import Path

from gateway.router import GatewayRouter, Binding, TierPriority
from core.types import InboundMessage
from config.schema import AgentConfig


def _msg(channel="telegram", chat_id="groupA", sender_id="user1") -> InboundMessage:
    return InboundMessage(channel=channel, sender_id=sender_id, chat_id=chat_id, content="hi")


def test_default_route():
    router = GatewayRouter(default_agent="default")
    result = router.resolve(_msg())
    assert isinstance(result, AgentConfig)
    assert result.name == "default"


def test_peer_binding():
    configs = {"agent_x": AgentConfig(name="agent_x", model="gpt-4")}
    router = GatewayRouter(configs=configs)
    router.add_binding(Binding(tier="peer", agent="agent_x", channel="telegram", chat_id="groupA", sender_id="user1"))
    result = router.resolve(_msg())
    assert result.name == "agent_x"
    assert result.model == "gpt-4"


def test_peer_does_not_match_different_sender():
    configs = {"agent_x": AgentConfig(name="agent_x")}
    router = GatewayRouter(configs=configs)
    router.add_binding(Binding(tier="peer", agent="agent_x", channel="telegram", chat_id="groupA", sender_id="user1"))
    result = router.resolve(_msg(sender_id="user2"))
    assert result.name == "default"


def test_guild_binding():
    configs = {"agent_g": AgentConfig(name="agent_g")}
    router = GatewayRouter(configs=configs)
    router.add_binding(Binding(tier="guild", agent="agent_g", channel="telegram", chat_id="groupA"))
    result = router.resolve(_msg(sender_id="anyone"))
    assert result.name == "agent_g"


def test_channel_binding():
    configs = {"agent_tg": AgentConfig(name="agent_tg")}
    router = GatewayRouter(configs=configs)
    router.add_binding(Binding(tier="channel", agent="agent_tg", channel="telegram"))
    result = router.resolve(_msg(chat_id="any", sender_id="any"))
    assert result.name == "agent_tg"


def test_priority_peer_over_guild():
    configs = {
        "guild_agent": AgentConfig(name="guild_agent"),
        "peer_agent": AgentConfig(name="peer_agent"),
    }
    router = GatewayRouter(configs=configs)
    router.add_binding(Binding(tier="guild", agent="guild_agent", channel="telegram", chat_id="groupA"))
    router.add_binding(Binding(tier="peer", agent="peer_agent", channel="telegram", chat_id="groupA", sender_id="user1"))
    # peer should win
    result = router.resolve(_msg())
    assert result.name == "peer_agent"


def test_priority_guild_over_channel():
    configs = {
        "channel_agent": AgentConfig(name="channel_agent"),
        "guild_agent": AgentConfig(name="guild_agent"),
    }
    router = GatewayRouter(configs=configs)
    router.add_binding(Binding(tier="channel", agent="channel_agent", channel="telegram"))
    router.add_binding(Binding(tier="guild", agent="guild_agent", channel="telegram", chat_id="groupA"))
    result = router.resolve(_msg())
    assert result.name == "guild_agent"


def test_from_yaml(tmp_path):
    yaml_content = """
bindings:
  - tier: peer
    channel: telegram
    chat_id: "groupA"
    sender_id: "user1"
    agent: agent_a
  - tier: guild
    channel: telegram
    chat_id: "groupB"
    agent: agent_b
  - tier: default
    agent: default_agent
"""
    p = tmp_path / "bindings.yaml"
    p.write_text(yaml_content)

    router = GatewayRouter.from_yaml(p, default_agent="fallback")
    result = router.resolve(_msg())
    assert isinstance(result, AgentConfig)
    assert len(router.bindings) == 3


def test_from_yaml_missing_file(tmp_path):
    router = GatewayRouter.from_yaml(tmp_path / "nope.yaml")
    result = router.resolve(_msg())
    assert isinstance(result, AgentConfig)
    assert result.name == "default"


def test_resolve_missing_agent_config_falls_back():
    """When a binding references an agent with no config, fall back to default."""
    router = GatewayRouter(default_agent="default")
    router.add_binding(Binding(tier="channel", agent="nonexistent", channel="telegram"))
    result = router.resolve(_msg())
    assert result.name == "default"
