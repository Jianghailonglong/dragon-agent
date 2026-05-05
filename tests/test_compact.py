import pytest
import json

from session.compact import Microcompact, ToolResultBudget, SnipHistory


def _make_tool_result_msg(tool_use_id: str, content: str) -> dict:
    return {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": content}],
    }


def test_microcompact_keeps_recent():
    mc = Microcompact(keep_recent=3)
    messages = [
        {"role": "user", "content": "start"},
    ]
    # Add 5 tool results
    for i in range(5):
        messages.append(_make_tool_result_msg(f"t{i}", f"result_{i}"))
    messages.append({"role": "assistant", "content": "done"})

    result = mc.compact(messages)

    # First 2 tool results should be compacted, last 3 kept
    tool_msgs = [m for m in result if isinstance(m.get("content"), list) and any(
        isinstance(b, dict) and b.get("type") == "tool_result" for b in m.get("content", [])
    )]

    compacted = [m for m in tool_msgs if m["content"][0]["content"] == "[result omitted]"]
    assert len(compacted) == 2


def test_microcompact_no_compaction_when_few():
    mc = Microcompact(keep_recent=10)
    messages = [_make_tool_result_msg(f"t{i}", f"r{i}") for i in range(3)]
    result = mc.compact(messages)
    # All should be unchanged
    for msg in result:
        if isinstance(msg.get("content"), list):
            assert msg["content"][0]["content"] != "[result omitted]"


def test_tool_result_budget_truncates():
    tb = ToolResultBudget(max_chars=50)
    msg = _make_tool_result_msg("t1", "x" * 100)
    result = tb.apply([msg])
    content = result[0]["content"][0]["content"]
    assert "truncated" in content
    assert len(content) < 100


def test_tool_result_budget_no_change():
    tb = ToolResultBudget(max_chars=1000)
    msg = _make_tool_result_msg("t1", "short")
    result = tb.apply([msg])
    assert result[0]["content"][0]["content"] == "short"


def test_snip_history_trims_old():
    snip = SnipHistory(max_tokens=10, chars_per_token=1.0)  # 10 chars budget
    messages = [
        {"role": "user", "content": "a" * 20},
        {"role": "assistant", "content": "b" * 20},
        {"role": "user", "content": "c" * 5},
        {"role": "assistant", "content": "d" * 5},
    ]
    result = snip.snip(messages)
    # Should trim to fit, keeping recent messages
    total = sum(len(m.get("content", "")) for m in result)
    assert total <= 40  # some trimming happened


def test_snip_ensures_first_is_user():
    snip = SnipHistory(max_tokens=5, chars_per_token=1.0)
    messages = [
        {"role": "assistant", "content": "old"},
        {"role": "user", "content": "new"},
        {"role": "assistant", "content": "reply"},
    ]
    result = snip.snip(messages)
    assert result[0]["role"] == "user"
