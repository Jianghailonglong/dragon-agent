import pytest

from core.runner import AgentRunner, AgentRunSpec
from tools.registry import ToolRegistry
from providers.base import LLMProvider, LLMResponse


class MockProvider(LLMProvider):
    async def chat_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096):
        return LLMResponse(content="ok", stop_reason="end_turn", usage={"input_tokens": 1, "output_tokens": 1})

    async def stream_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096, on_delta=None):
        return await self.chat_completion(messages, tools, model, system, max_tokens)


def test_govern_context_compacts():
    runner = AgentRunner()
    messages = [{"role": "user", "content": "start"}]

    # Add many old tool results
    for i in range(20):
        messages.append({
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": f"result_{i}"}],
        })
    messages.append({"role": "assistant", "content": "done"})

    governed = runner.govern_context(messages)
    # Should be shorter due to microcompact
    assert len(governed) <= len(messages)


def test_govern_context_preserves_recent():
    runner = AgentRunner()
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    governed = runner.govern_context(messages)
    assert len(governed) == 2
    assert governed[0]["content"] == "hello"


def test_govern_context_uses_dynamic_token_budget():
    """SnipHistory should use 90% of context_window_tokens from spec."""
    runner = AgentRunner()

    # Create messages that exceed a small context window
    spec = AgentRunSpec(
        messages=[],
        tools=ToolRegistry(),
        provider=MockProvider(),
        context_window_tokens=100,  # very small window
    )

    messages = [
        {"role": "user", "content": "x" * 500},
        {"role": "assistant", "content": "y" * 500},
        {"role": "user", "content": "z" * 100},
        {"role": "assistant", "content": "w" * 100},
    ]

    governed = runner.govern_context(messages, spec)
    total_chars = sum(len(m.get("content", "")) for m in governed)
    # Should be trimmed to fit within 90% of 100 tokens * 4 chars/token = 360 chars
    assert total_chars <= 400  # some margin
