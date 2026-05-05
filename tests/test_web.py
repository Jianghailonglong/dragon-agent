"""Tests for WebChannel and FastAPI web app."""
import asyncio

import pytest
import pytest_asyncio

from channels.web import WebChannel
from core.types import InboundMessage, OutboundMessage


@pytest.mark.asyncio
async def test_web_channel_name():
    ch = WebChannel()
    assert ch.name == "web"


@pytest.mark.asyncio
async def test_web_channel_connect():
    ch = WebChannel()
    await ch.connect()  # no-op, should not raise


@pytest.mark.asyncio
async def test_submit_message():
    ch = WebChannel()
    request_id = await ch.submit_message("hello")
    assert isinstance(request_id, str)
    assert len(request_id) == 8

    msg = await asyncio.wait_for(ch.receive(), timeout=1.0)
    assert isinstance(msg, InboundMessage)
    assert msg.content == "hello"
    assert msg.channel == "web"
    assert msg.sender_id == "user"


@pytest.mark.asyncio
async def test_send_broadcasts_to_clients():
    ch = WebChannel()
    q1 = ch.register_client("c1")
    q2 = ch.register_client("c2")

    out = OutboundMessage(channel="web", chat_id="web:local", content="hi all")
    await ch.send(out)

    msg1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    msg2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert msg1.content == "hi all"
    assert msg2.content == "hi all"


@pytest.mark.asyncio
async def test_unregister_client():
    ch = WebChannel()
    ch.register_client("c1")
    ch.unregister_client("c1")
    assert "c1" not in ch._outbound_queues


@pytest.mark.asyncio
async def test_stream_events_yields_sse():
    ch = WebChannel()
    client_id = "test_client"

    # Put a message then cancel
    async def produce():
        await asyncio.sleep(0.1)
        await ch.send(OutboundMessage(channel="web", chat_id="w", content="hello world"))

    producer = asyncio.create_task(produce())

    events = []
    async for event in ch.stream_events(client_id):
        events.append(event)
        if len(events) >= 1:
            break

    producer.cancel()
    try:
        await producer
    except asyncio.CancelledError:
        pass

    assert len(events) == 1
    assert events[0] == "data: hello world\n\n"


# --- FastAPI app tests (using httpx TestClient) ---


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    from web.app import app, set_channel, get_channel

    ch = WebChannel()
    set_channel(ch)

    with TestClient(app) as c:
        yield c


def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Dragon Agent" in resp.text
    assert "<html" in resp.text


def test_chat_empty_message(client):
    resp = client.post("/api/chat", json={"message": ""})
    assert resp.status_code == 200
    assert resp.json() == {"error": "empty message"}


def test_chat_submit(client):
    resp = client.post("/api/chat", json={"message": "test msg"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "request_id" in data
