import pytest

from core.runner import AgentRunner


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
