from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from channels.web import WebChannel
from core.types import OutboundMessage

TEMPLATE_DIR = Path(__file__).parent / "templates"

# Module-level state, set by cmd_web() before uvicorn starts
_web_channel: WebChannel | None = None
_agent_loop = None  # AgentLoop instance


def set_channel(channel: WebChannel) -> None:
    global _web_channel
    _web_channel = channel


def set_agent_loop(loop) -> None:
    global _agent_loop
    _agent_loop = loop


def get_channel() -> WebChannel:
    assert _web_channel is not None, "WebChannel not initialized"
    return _web_channel


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the agent loop as a background task."""
    task = None
    if _agent_loop is not None:
        task = asyncio.create_task(_agent_loop.run())
    yield
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Dragon Agent", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def index():
    html_file = TEMPLATE_DIR / "chat.html"
    return html_file.read_text(encoding="utf-8")


@app.post("/api/chat")
async def chat(request: Request):
    """Receive a user message and submit to agent."""
    data = await request.json()
    content = data.get("message", "").strip()
    if not content:
        return {"error": "empty message"}

    channel = get_channel()
    request_id = await channel.submit_message(content)
    return {"status": "ok", "request_id": request_id}


@app.get("/api/events")
async def events(request: Request):
    """SSE endpoint for streaming agent responses."""
    channel = get_channel()
    client_id = uuid.uuid4().hex[:8]

    async def event_generator():
        async for data in channel.stream_events(client_id):
            yield data

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
