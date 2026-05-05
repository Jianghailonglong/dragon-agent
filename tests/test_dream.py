import pytest
import json

from providers.base import LLMProvider, LLMResponse
from intelligence.memory import MemoryStore
from intelligence.dream import Dream


class MockProvider(LLMProvider):
    def __init__(self, response_text="[]"):
        self._response_text = response_text

    async def chat_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096):
        return LLMResponse(
            content=self._response_text,
            stop_reason="end_turn",
            usage={"input_tokens": 10, "output_tokens": 5},
        )

    async def stream_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096, on_delta=None):
        return await self.chat_completion(messages, tools, model, system, max_tokens)


@pytest.mark.asyncio
async def test_dream_extracts_nothing(tmp_path):
    memory = MemoryStore(workspace=str(tmp_path))
    provider = MockProvider(response_text="[]")
    dream = Dream(provider=provider, memory=memory)

    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
        {"role": "user", "content": "how are you"},
        {"role": "assistant", "content": "good"},
    ]

    extracted = await dream.run(messages)
    assert extracted == []


@pytest.mark.asyncio
async def test_dream_extracts_memories(tmp_path):
    entries = [
        {"name": "user_role", "content": "Senior Python developer", "type": "user"},
        {"name": "project_deadline", "content": "Project due Friday", "type": "project"},
    ]
    memory = MemoryStore(workspace=str(tmp_path))
    provider = MockProvider(response_text=json.dumps(entries))
    dream = Dream(provider=provider, memory=memory)

    messages = [
        {"role": "user", "content": "I'm a senior Python dev"},
        {"role": "assistant", "content": "Great!"},
        {"role": "user", "content": "Project deadline is Friday"},
        {"role": "assistant", "content": "Noted."},
    ]

    extracted = await dream.run(messages)
    assert len(extracted) == 2
    assert "user_role" in extracted
    assert "project_deadline" in extracted

    # Verify memory was saved
    content = memory.load()
    assert "Senior Python developer" in content
    assert "Project due Friday" in content


@pytest.mark.asyncio
async def test_dream_too_few_messages(tmp_path):
    memory = MemoryStore(workspace=str(tmp_path))
    provider = MockProvider()
    dream = Dream(provider=provider, memory=memory)

    messages = [{"role": "user", "content": "hi"}]
    extracted = await dream.run(messages)
    assert extracted == []


@pytest.mark.asyncio
async def test_dream_handles_invalid_json(tmp_path):
    memory = MemoryStore(workspace=str(tmp_path))
    provider = MockProvider(response_text="this is not json")
    dream = Dream(provider=provider, memory=memory)

    messages = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
        {"role": "assistant", "content": "d"},
    ]

    extracted = await dream.run(messages)
    assert extracted == []
