from __future__ import annotations

import json
from typing import Callable, Awaitable

from providers.base import LLMProvider


class Microcompact:
    """
    Layer 1: Zero-cost local compaction.
    Replace old tool results with stubs, keep only recent N tool results.
    """

    def __init__(self, keep_recent: int = 10) -> None:
        self._keep_recent = keep_recent

    def compact(self, messages: list[dict]) -> list[dict]:
        """Replace old tool results with omission stubs."""
        # Find indices of tool_result messages
        tool_result_indices = []
        for i, msg in enumerate(messages):
            if isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool_result_indices.append(i)
                        break

        if len(tool_result_indices) <= self._keep_recent:
            return messages

        # Indices to compact (all except the last keep_recent)
        to_compact = set(tool_result_indices[:-self._keep_recent])

        result = []
        for i, msg in enumerate(messages):
            if i in to_compact and isinstance(msg.get("content"), list):
                new_content = []
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        new_content.append({
                            "type": "tool_result",
                            "tool_use_id": block.get("tool_use_id", ""),
                            "content": "[result omitted]",
                        })
                    else:
                        new_content.append(block)
                result.append({**msg, "content": new_content})
            else:
                result.append(msg)
        return result


class ToolResultBudget:
    """
    Layer 2: Truncate or offload oversized tool results.
    """

    def __init__(self, max_chars: int = 50_000) -> None:
        self._max_chars = max_chars

    def apply(self, messages: list[dict]) -> list[dict]:
        """Truncate tool results that exceed the budget."""
        result = []
        for msg in messages:
            if isinstance(msg.get("content"), list):
                new_content = []
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        content = block.get("content", "")
                        if isinstance(content, str) and len(content) > self._max_chars:
                            truncated = content[:self._max_chars] + f"\n... [truncated, {len(content)} chars total]"
                            new_content.append({**block, "content": truncated})
                        else:
                            new_content.append(block)
                    else:
                        new_content.append(block)
                result.append({**msg, "content": new_content})
            else:
                result.append(msg)
        return result


class SnipHistory:
    """
    Layer 3: Token-budget trimming.
    Trim from oldest to newest, ensuring the first message is a user message.
    """

    def __init__(self, max_tokens: int = 180_000, chars_per_token: float = 4.0) -> None:
        self._max_tokens = max_tokens
        self._chars_per_token = chars_per_token

    def snip(self, messages: list[dict]) -> list[dict]:
        """Trim messages to fit within token budget."""
        if not messages:
            return messages

        max_chars = int(self._max_tokens * self._chars_per_token)
        total = sum(self._estimate_chars(m) for m in messages)

        if total <= max_chars:
            return messages

        # Drop from the front, but keep at least the last user message pair
        budget = max_chars
        keep_from = len(messages)

        for i in range(len(messages) - 1, -1, -1):
            chars = self._estimate_chars(messages[i])
            if budget - chars < 0 and i < len(messages) - 2:
                break
            budget -= chars
            keep_from = i

        trimmed = messages[keep_from:]

        # Ensure first message is a user message
        while trimmed and trimmed[0].get("role") != "user":
            trimmed = trimmed[1:]

        return trimmed if trimmed else messages[-2:]

    def _estimate_chars(self, msg: dict) -> int:
        content = msg.get("content", "")
        if isinstance(content, str):
            return len(content)
        if isinstance(content, list):
            return sum(len(json.dumps(b, ensure_ascii=False)) for b in content)
        return len(json.dumps(content, ensure_ascii=False))


class AutoCompact:
    """Idle session auto-compaction (triggered after N minutes of inactivity)."""

    def __init__(self, idle_minutes: int = 30) -> None:
        self._idle_minutes = idle_minutes

    def should_compact(self, last_updated: float, now: float) -> bool:
        """Check if session has been idle long enough to compact."""
        return (now - last_updated) > self._idle_minutes * 60


class Consolidator:
    """Use LLM to compress old messages into a summary when over token budget."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def consolidate(self, messages: list[dict], target_tokens: int = 50_000) -> list[dict]:
        """
        Compress older messages into a summary.
        Keeps the last few messages intact and summarizes the rest.
        """
        if len(messages) <= 4:
            return messages

        # Split: old messages to summarize, recent messages to keep
        split_at = max(2, len(messages) // 2)
        old_messages = messages[:split_at]
        recent_messages = messages[split_at:]

        # Build a summarization prompt
        old_text = json.dumps(old_messages, ensure_ascii=False, indent=2)
        summary_prompt = [
            {"role": "user", "content": (
                "Summarize the following conversation history concisely, "
                "preserving key facts, decisions, and context:\n\n" + old_text
            )},
        ]

        resp = await self._provider.chat_completion(
            messages=summary_prompt,
            max_tokens=1024,
        )

        # Handle empty or None response gracefully
        summary_text = resp.content if resp and resp.content else "[Summary unavailable]"

        summary_msg = {
            "role": "user",
            "content": f"[Conversation summary]\n{summary_text}",
        }

        return [summary_msg] + recent_messages
