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


@pytest.mark.asyncio
async def test_dream_handles_markdown_code_block(tmp_path):
    """Dream should extract JSON from markdown code blocks."""
    entries = [{"name": "test", "content": "value", "type": "note"}]
    response = f"```json\n{json.dumps(entries)}\n```"

    memory = MemoryStore(workspace=str(tmp_path))
    provider = MockProvider(response_text=response)
    dream = Dream(provider=provider, memory=memory)

    messages = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
        {"role": "assistant", "content": "d"},
    ]

    extracted = await dream.run(messages)
    assert len(extracted) == 1
    assert "test" in extracted


@pytest.mark.asyncio
async def test_dream_handles_json_with_surrounding_text(tmp_path):
    """Dream should find JSON array within surrounding text."""
    entries = [{"name": "info", "content": "data", "type": "project"}]
    response = f"Here are the extracted memories:\n{json.dumps(entries)}\nEnd of analysis."

    memory = MemoryStore(workspace=str(tmp_path))
    provider = MockProvider(response_text=response)
    dream = Dream(provider=provider, memory=memory)

    messages = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
        {"role": "assistant", "content": "d"},
    ]

    extracted = await dream.run(messages)
    assert len(extracted) == 1
    assert "info" in extracted


class FailingProvider(LLMProvider):
    async def chat_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096):
        raise ConnectionError("API unavailable")

    async def stream_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096, on_delta=None):
        raise ConnectionError("API unavailable")


@pytest.mark.asyncio
async def test_dream_handles_llm_failure(tmp_path):
    """Dream should handle LLM call failures gracefully."""
    memory = MemoryStore(workspace=str(tmp_path))
    dream = Dream(provider=FailingProvider(), memory=memory)

    messages = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
        {"role": "assistant", "content": "d"},
    ]

    extracted = await dream.run(messages)
    assert extracted == []


class EmptyProvider(LLMProvider):
    """Provider that returns empty content."""
    async def chat_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096):
        return LLMResponse(content="", stop_reason="end_turn", usage={"input_tokens": 1, "output_tokens": 1})

    async def stream_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096, on_delta=None):
        return await self.chat_completion(messages, tools, model, system, max_tokens)


class NoneContentProvider(LLMProvider):
    """Provider that returns None content."""
    async def chat_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096):
        return LLMResponse(content=None, stop_reason="end_turn", usage={"input_tokens": 1, "output_tokens": 1})

    async def stream_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096, on_delta=None):
        return await self.chat_completion(messages, tools, model, system, max_tokens)


@pytest.mark.asyncio
async def test_dream_handles_empty_content(tmp_path):
    """Dream should handle empty LLM response gracefully without warning."""
    memory = MemoryStore(workspace=str(tmp_path))
    dream = Dream(provider=EmptyProvider(), memory=memory)

    messages = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
        {"role": "assistant", "content": "d"},
    ]

    extracted = await dream.run(messages)
    assert extracted == []


@pytest.mark.asyncio
async def test_dream_handles_none_content(tmp_path):
    """Dream should handle None content in LLM response gracefully."""
    memory = MemoryStore(workspace=str(tmp_path))
    dream = Dream(provider=NoneContentProvider(), memory=memory)

    messages = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
        {"role": "assistant", "content": "d"},
    ]

    extracted = await dream.run(messages)
    assert extracted == []
