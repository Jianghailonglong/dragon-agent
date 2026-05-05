import pytest
from channels.manager import ChannelManager
from channels.telegram import TelegramChannel
from channels.feishu import FeishuChannel
from channels.wechat import WeChatChannel
from core.types import OutboundMessage


def test_channel_manager_register_all_types():
    mgr = ChannelManager()
    tg = TelegramChannel(token="fake:token")
    fs = FeishuChannel(app_id="fake", app_secret="fake")
    wc = WeChatChannel(webhook_key="fake")

    mgr.register(tg)
    mgr.register(fs)
    mgr.register(wc)

    assert set(mgr.list_channels()) == {"telegram", "feishu", "wechat"}
    assert mgr.get("telegram") is tg
    assert mgr.get("feishu") is fs


def test_telegram_name():
    ch = TelegramChannel(token="fake:token")
    assert ch.name == "telegram"


def test_feishu_name():
    ch = FeishuChannel(app_id="fake", app_secret="fake")
    assert ch.name == "feishu"


def test_wechat_name():
    ch = WeChatChannel(webhook_key="fake")
    assert ch.name == "wechat"


@pytest.mark.asyncio
async def test_feishu_handle_event():
    ch = FeishuChannel(app_id="fake", app_secret="fake")
    event = {
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_abc"}},
            "message": {
                "chat_id": "oc_xyz",
                "content": '{"text": "hello from feishu"}',
                "message_id": "msg_001",
            },
        },
    }
    msg = await ch.handle_event(event)
    assert msg is not None
    assert msg.channel == "feishu"
    assert msg.content == "hello from feishu"
    assert msg.sender_id == "ou_abc"
    assert msg.chat_id == "oc_xyz"


@pytest.mark.asyncio
async def test_feishu_handle_non_message_event():
    ch = FeishuChannel(app_id="fake", app_secret="fake")
    event = {"header": {"event_type": "other.event"}}
    msg = await ch.handle_event(event)
    assert msg is None


@pytest.mark.asyncio
async def test_wechat_handle_event():
    ch = WeChatChannel(webhook_key="fake")
    event = {
        "MsgType": "text",
        "FromUserName": "user_abc",
        "ToUserName": "bot_xyz",
        "Content": "hello from wechat",
        "MsgId": "12345",
    }
    msg = await ch.handle_event(event)
    assert msg is not None
    assert msg.channel == "wechat"
    assert msg.content == "hello from wechat"


@pytest.mark.asyncio
async def test_wechat_handle_non_text_event():
    ch = WeChatChannel(webhook_key="fake")
    event = {"MsgType": "image"}
    msg = await ch.handle_event(event)
    assert msg is None
