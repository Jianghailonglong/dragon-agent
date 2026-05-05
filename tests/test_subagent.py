import pytest
import asyncio

from providers.base import LLMProvider, LLMResponse
from tools.registry import ToolRegistry
from orchestration.subagent import SubagentManager


class MockProvider(LLMProvider):
    def __init__(self, response_text="subagent done"):
        self._response_text = response_text

    async def chat_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096):
        return LLMResponse(
            content=self._response_text,
            stop_reason="end_turn",
            usage={"input_tokens": 5, "output_tokens": 3},
        )

    async def stream_completion(self, messages, tools=None, model=None, system=None, max_tokens=4096, on_delta=None):
        return await self.chat_completion(messages, tools, model, system, max_tokens)


@pytest.mark.asyncio
async def test_subagent_spawn_and_wait():
    mgr = SubagentManager(provider=MockProvider(), tools=ToolRegistry())
    result = await mgr.spawn_and_wait("do something")
    assert result.content == "subagent done"
    assert mgr.completed_count == 1


@pytest.mark.asyncio
async def test_subagent_spawn_nonblocking():
    mgr = SubagentManager(provider=MockProvider(), tools=ToolRegistry())
    task_id = await mgr.spawn("background task")
    assert task_id.startswith("sub_")

    task = mgr.get_task(task_id)
    assert task is not None

    result = await mgr.wait(task_id)
    assert result.content == "subagent done"


@pytest.mark.asyncio
async def test_subagent_concurrent_limit():
    mgr = SubagentManager(provider=MockProvider(), tools=ToolRegistry(), max_concurrent=2)

    # Spawn 3 tasks — only 2 should run concurrently
    ids = []
    for i in range(3):
        task_id = await mgr.spawn(f"task {i}")
        ids.append(task_id)

    # Wait for all
    for tid in ids:
        await mgr.wait(tid)

    assert mgr.completed_count == 3


@pytest.mark.asyncio
async def test_subagent_with_context():
    mgr = SubagentManager(provider=MockProvider("context-aware response"), tools=ToolRegistry())
    result = await mgr.spawn_and_wait("analyze this", parent_context="project context here")
    assert result.content == "context-aware response"


@pytest.mark.asyncio
async def test_subagent_list_tasks():
    mgr = SubagentManager(provider=MockProvider(), tools=ToolRegistry())
    await mgr.spawn_and_wait("task a")
    await mgr.spawn_and_wait("task b")

    tasks = mgr.list_tasks()
    assert len(tasks) == 2
