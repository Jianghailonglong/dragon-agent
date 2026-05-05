from core.types import InboundMessage, OutboundMessage


def test_inbound_session_key_default():
    msg = InboundMessage(channel="cli", sender_id="u1", chat_id="c1", content="hi")
    assert msg.session_key == "cli:c1"


def test_inbound_session_key_override():
    msg = InboundMessage(channel="cli", sender_id="u1", chat_id="c1", content="hi", session_key_override="custom")
    assert msg.session_key == "custom"


def test_outbound_creation():
    msg = OutboundMessage(channel="cli", chat_id="c1", content="hello")
    assert msg.channel == "cli"
    assert msg.metadata == {}
