import pytest
from pathlib import Path

from gateway.router import GatewayRouter, Binding, TierPriority
from core.types import InboundMessage


def _msg(channel="telegram", chat_id="groupA", sender_id="user1") -> InboundMessage:
    return InboundMessage(channel=channel, sender_id=sender_id, chat_id=chat_id, content="hi")


def test_default_route():
    router = GatewayRouter(default_agent="default")
    assert router.resolve(_msg()) == "default"


def test_peer_binding():
    router = GatewayRouter()
    router.add_binding(Binding(tier="peer", agent="agent_x", channel="telegram", chat_id="groupA", sender_id="user1"))
    assert router.resolve(_msg()) == "agent_x"


def test_peer_does_not_match_different_sender():
    router = GatewayRouter()
    router.add_binding(Binding(tier="peer", agent="agent_x", channel="telegram", chat_id="groupA", sender_id="user1"))
    assert router.resolve(_msg(sender_id="user2")) == "default"


def test_guild_binding():
    router = GatewayRouter()
    router.add_binding(Binding(tier="guild", agent="agent_g", channel="telegram", chat_id="groupA"))
    assert router.resolve(_msg(sender_id="anyone")) == "agent_g"


def test_channel_binding():
    router = GatewayRouter()
    router.add_binding(Binding(tier="channel", agent="agent_tg", channel="telegram"))
    assert router.resolve(_msg(chat_id="any", sender_id="any")) == "agent_tg"


def test_priority_peer_over_guild():
    router = GatewayRouter()
    router.add_binding(Binding(tier="guild", agent="guild_agent", channel="telegram", chat_id="groupA"))
    router.add_binding(Binding(tier="peer", agent="peer_agent", channel="telegram", chat_id="groupA", sender_id="user1"))
    # peer should win
    assert router.resolve(_msg()) == "peer_agent"


def test_priority_guild_over_channel():
    router = GatewayRouter()
    router.add_binding(Binding(tier="channel", agent="channel_agent", channel="telegram"))
    router.add_binding(Binding(tier="guild", agent="guild_agent", channel="telegram", chat_id="groupA"))
    assert router.resolve(_msg()) == "guild_agent"


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
    assert router.resolve(_msg()) == "agent_a"
    assert router.resolve(_msg(chat_id="groupB", sender_id="other")) == "agent_b"
    assert len(router.bindings) == 3


def test_from_yaml_missing_file(tmp_path):
    router = GatewayRouter.from_yaml(tmp_path / "nope.yaml")
    assert router.resolve(_msg()) == "default"
