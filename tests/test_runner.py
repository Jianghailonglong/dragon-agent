import pytest
from dataclasses import dataclass, field

from providers.base import LLMProvider, LLMResponse
from tools.registry import ToolRegistry
from tools.base import BaseTool
from core.runner import AgentRunner, AgentRunSpec
from core.hook import AgentHook, HookContext


# --- Mock provider ---

class MockProvider(LLMProvider):
    def __init__(self, responses):
        self._responses = list(responses)
        self._calls = []

    async def chat_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096):
        self._calls.append(messages)
        return self._responses.pop(0)

    async def stream_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096, on_delta=None):
        return await self.chat_completion(messages, tools, model, system, max_tokens)


class EchoTool(BaseTool):
    @property
    def name(self):
        return "echo"

    @property
    def description(self):
        return "Echo input"

    @property
    def parameters(self):
        return {"type": "object", "properties": {"text": {"type": "string"}}}

    async def execute(self, **kwargs):
        return f"echoed: {kwargs.get('text', '')}"


@pytest.mark.asyncio
async def test_simple_end_turn():
    provider = MockProvider([
        LLMResponse(content="Hello!", stop_reason="end_turn", usage={"input_tokens": 10, "output_tokens": 5}),
    ])
    tools = ToolRegistry()
    spec = AgentRunSpec(
        messages=[{"role": "user", "content": "hi"}],
        tools=tools,
        provider=provider,
    )

    runner = AgentRunner()
    result = await runner.run(spec)

    assert result.content == "Hello!"
    assert result.iterations == 1
    assert result.usage["input_tokens"] == 10


@pytest.mark.asyncio
async def test_tool_use_then_end_turn():
    provider = MockProvider([
        LLMResponse(
            content="",
            tool_calls=[{"id": "tc1", "name": "echo", "input": {"text": "hi"}}],
            stop_reason="tool_use",
            usage={"input_tokens": 10, "output_tokens": 5},
        ),
        LLMResponse(content="Done!", stop_reason="end_turn", usage={"input_tokens": 20, "output_tokens": 3}),
    ])
    tools = ToolRegistry()
    tools.register(EchoTool())

    spec = AgentRunSpec(
        messages=[{"role": "user", "content": "say hi"}],
        tools=tools,
        provider=provider,
    )

    runner = AgentRunner()
    result = await runner.run(spec)

    assert result.content == "Done!"
    assert result.iterations == 2
    # Check tool result was added to messages
    tool_msgs = [m for m in result.messages if m.get("role") == "user" and isinstance(m.get("content"), list)]
    assert len(tool_msgs) == 1
    assert "echoed: hi" in tool_msgs[0]["content"][0]["content"]


@pytest.mark.asyncio
async def test_unknown_tool():
    provider = MockProvider([
        LLMResponse(
            content="",
            tool_calls=[{"id": "tc1", "name": "unknown", "input": {}}],
            stop_reason="tool_use",
            usage={"input_tokens": 5, "output_tokens": 2},
        ),
        LLMResponse(content="ok", stop_reason="end_turn", usage={"input_tokens": 5, "output_tokens": 2}),
    ])
    tools = ToolRegistry()

    spec = AgentRunSpec(messages=[{"role": "user", "content": "test"}], tools=tools, provider=provider)
    result = await AgentRunner().run(spec)

    # Error fed back to LLM, then end_turn
    assert "unknown tool" in str(result.messages)


@pytest.mark.asyncio
async def test_max_iterations():
    """Repeated identical tool calls trigger loop detection and force a final answer."""
    responses = [
        # 3 identical tool calls (loop detection triggers after 3rd)
        LLMResponse(content="", tool_calls=[{"id": "tc0", "name": "echo", "input": {"text": "loop"}}], stop_reason="tool_use", usage={"input_tokens": 1, "output_tokens": 1}),
        LLMResponse(content="", tool_calls=[{"id": "tc1", "name": "echo", "input": {"text": "loop"}}], stop_reason="tool_use", usage={"input_tokens": 1, "output_tokens": 1}),
        LLMResponse(content="", tool_calls=[{"id": "tc2", "name": "echo", "input": {"text": "loop"}}], stop_reason="tool_use", usage={"input_tokens": 1, "output_tokens": 1}),
        # Final call without tools (loop detection forces this)
        LLMResponse(content="Here is my answer.", stop_reason="end_turn", usage={"input_tokens": 1, "output_tokens": 1}),
    ]

    provider = MockProvider(responses)
    tools = ToolRegistry()
    tools.register(EchoTool())

    spec = AgentRunSpec(
        messages=[{"role": "user", "content": "loop"}],
        tools=tools,
        provider=provider,
        max_iterations=10,
    )

    result = await AgentRunner().run(spec)
    assert result.iterations == 3
    assert "answer" in result.content.lower()


@pytest.mark.asyncio
async def test_max_iterations_preserves_content():
    """When max iterations hit with content, preserve last output and add continuation prompt."""
    responses = [
        LLMResponse(
            content="Working on it...",
            tool_calls=[{"id": "tc1", "name": "echo", "input": {"text": "loop"}}],
            stop_reason="tool_use",
            usage={"input_tokens": 1, "output_tokens": 1},
        ),
        LLMResponse(
            content="Still going...",
            tool_calls=[{"id": "tc2", "name": "echo", "input": {"text": "loop"}}],
            stop_reason="tool_use",
            usage={"input_tokens": 1, "output_tokens": 1},
        ),
    ]

    provider = MockProvider(responses)
    tools = ToolRegistry()
    tools.register(EchoTool())

    spec = AgentRunSpec(
        messages=[{"role": "user", "content": "do something"}],
        tools=tools,
        provider=provider,
        max_iterations=2,
    )

    result = await AgentRunner().run(spec)
    assert result.hit_iteration_limit is True
    assert "Still going..." in result.content
    assert "partially completed" in result.content
    # Check continuation prompt was added
    last_msg = result.messages[-1]
    assert "continue" in last_msg["content"].lower()


@pytest.mark.asyncio
async def test_hook_lifecycle():
    class TestHook(AgentHook):
        def __init__(self):
            self.events = []

        def before_iteration(self, ctx):
            self.events.append(f"before_{ctx.iteration}")

        def after_iteration(self, ctx):
            self.events.append(f"after_{ctx.iteration}")

        def finalize_content(self, ctx, content):
            return f"[finalized] {content}"

    hook = TestHook()
    provider = MockProvider([
        LLMResponse(content="hi", stop_reason="end_turn", usage={"input_tokens": 1, "output_tokens": 1}),
    ])

    spec = AgentRunSpec(
        messages=[{"role": "user", "content": "test"}],
        tools=ToolRegistry(),
        provider=provider,
        hook=hook,
    )

    result = await AgentRunner().run(spec)
    assert result.content == "[finalized] hi"
    assert "before_0" in hook.events
    assert "after_0" in hook.events
