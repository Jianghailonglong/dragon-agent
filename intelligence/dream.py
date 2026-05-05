from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from providers.base import LLMProvider
from .memory import MemoryStore


class Dream:
    """
    Automatic memory extraction: scan conversation history,
    extract noteworthy information and write to MEMORY.md.
    (Like memory consolidation during sleep.)

    Supports per-user workspace via MemoryStore backed by UserWorkspace.
    """

    def __init__(self, provider: LLMProvider, memory: MemoryStore) -> None:
        self._provider = provider
        self._memory = memory

    async def run(self, messages: list[dict]) -> list[str]:
        """
        Analyze conversation and extract memories.
        Returns list of extracted memory names.
        """
        if len(messages) < 4:
            return []

        # Build extraction prompt
        conversation = json.dumps(messages[-20:], ensure_ascii=False, indent=2)
        prompt = [
            {"role": "user", "content": (
                "Analyze the following conversation and extract noteworthy information "
                "that should be remembered for future interactions. "
                "Return a JSON array of objects with 'name', 'content', and 'type' fields. "
                "Type can be 'user', 'feedback', 'project', or 'reference'. "
                "Only extract truly important information. Return [] if nothing noteworthy.\n\n"
                f"Conversation:\n{conversation}"
            )},
        ]

        resp = await self._provider.chat_completion(
            messages=prompt,
            max_tokens=1024,
        )

        extracted = []
        try:
            # Parse JSON from response
            text = resp.content.strip()
            # Handle markdown code blocks
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                text = text.rsplit("```", 1)[0]
            entries = json.loads(text)
            if isinstance(entries, list):
                for entry in entries:
                    name = entry.get("name", "unnamed")
                    content = entry.get("content", "")
                    entry_type = entry.get("type", "note")
                    if content:
                        self._memory.save_entry(name, content, entry_type)
                        extracted.append(name)
        except (json.JSONDecodeError, KeyError):
            pass

        return extracted
