import pytest
import asyncio
from dataclasses import dataclass, field

from providers.base import LLMProvider, LLMResponse
from tools.registry import ToolRegistry
from tools.base import BaseTool
from core.runner import AgentRunner, AgentRunSpec


class MockProvider(LLMProvider):
    def __init__(self, responses):
        self._responses = list(responses)

    async def chat_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096):
        return self._responses.pop(0)

    async def stream_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096, on_delta=None):
        return await self.chat_completion(messages, tools, model, system, max_tokens)


class SlowTool(BaseTool):
    @property
    def name(self):
        return "slow"

    @property
    def description(self):
        return "A slow tool"

    @property
    def parameters(self):
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        return "done"


@pytest.mark.asyncio
async def test_injection_callback_called():
    injection_count = 0

    async def injection_cb():
        nonlocal injection_count
        injection_count += 1
        return None

    provider = MockProvider([
        LLMResponse(content="done", stop_reason="end_turn", usage={"input_tokens": 1, "output_tokens": 1}),
    ])

    spec = AgentRunSpec(
        messages=[{"role": "user", "content": "test"}],
        tools=ToolRegistry(),
        provider=provider,
        injection_callback=injection_cb,
    )

    await AgentRunner().run(spec)
    # No tool calls, so injection_callback should NOT be called
    assert injection_count == 0


@pytest.mark.asyncio
async def test_injection_after_tools():
    """After tool execution, injection messages are appended."""
    injection_messages = [{"role": "user", "content": "[injected] new context"}]

    async def injection_cb():
        return injection_messages

    provider = MockProvider([
        LLMResponse(
            content="",
            tool_calls=[{"id": "tc1", "name": "slow", "input": {}}],
            stop_reason="tool_use",
            usage={"input_tokens": 1, "output_tokens": 1},
        ),
        LLMResponse(content="final", stop_reason="end_turn", usage={"input_tokens": 1, "output_tokens": 1}),
    ])

    tools = ToolRegistry()
    tools.register(SlowTool())

    spec = AgentRunSpec(
        messages=[{"role": "user", "content": "test"}],
        tools=tools,
        provider=provider,
        injection_callback=injection_cb,
    )

    result = await AgentRunner().run(spec)
    # The injected message should be in the message history
    contents = [m.get("content") for m in result.messages]
    assert any("[injected]" in str(c) for c in contents)


@pytest.mark.asyncio
async def test_checkpoint_callback_called():
    checkpoints = []

    async def checkpoint_cb(tool_index, tool_name):
        checkpoints.append((tool_index, tool_name))

    provider = MockProvider([
        LLMResponse(
            content="",
            tool_calls=[
                {"id": "tc1", "name": "slow", "input": {}},
                {"id": "tc2", "name": "slow", "input": {}},
            ],
            stop_reason="tool_use",
            usage={"input_tokens": 1, "output_tokens": 1},
        ),
        LLMResponse(content="done", stop_reason="end_turn", usage={"input_tokens": 1, "output_tokens": 1}),
    ])

    tools = ToolRegistry()
    tools.register(SlowTool())

    spec = AgentRunSpec(
        messages=[{"role": "user", "content": "test"}],
        tools=tools,
        provider=provider,
        checkpoint_callback=checkpoint_cb,
    )

    await AgentRunner().run(spec)
    assert len(checkpoints) == 2
    assert checkpoints[0] == (0, "slow")
    assert checkpoints[1] == (1, "slow")
