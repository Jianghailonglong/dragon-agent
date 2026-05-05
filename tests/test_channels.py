import pytest
from channels.manager import ChannelManager
from channels.base import BaseChannel
from core.types import InboundMessage, OutboundMessage


class FakeChannel(BaseChannel):
    def __init__(self, name="fake"):
        self._name = name
        self.sent = []

    @property
    def name(self):
        return self._name

    async def connect(self):
        pass

    async def receive(self):
        return InboundMessage(channel=self._name, sender_id="u", chat_id="c", content="test")

    async def send(self, msg):
        self.sent.append(msg)


def test_channel_manager_register_get():
    mgr = ChannelManager()
    ch = FakeChannel()
    mgr.register(ch)
    assert mgr.get("fake") is ch
    assert mgr.get("missing") is None


def test_channel_manager_list():
    mgr = ChannelManager()
    mgr.register(FakeChannel("a"))
    mgr.register(FakeChannel("b"))
    assert set(mgr.list_channels()) == {"a", "b"}


@pytest.mark.asyncio
async def test_fake_channel():
    ch = FakeChannel()
    await ch.connect()
    msg = await ch.receive()
    assert msg.content == "test"

    out = OutboundMessage(channel="fake", chat_id="c", content="reply")
    await ch.send(out)
    assert ch.sent[0].content == "reply"
