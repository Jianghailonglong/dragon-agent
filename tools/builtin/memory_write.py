from __future__ import annotations

from typing import Any

from tools.base import BaseTool
from intelligence.memory import MemoryStore


class MemoryWriteTool(BaseTool):
    """Write a memory entry to MEMORY.md for future conversations."""

    def __init__(self, memory: MemoryStore) -> None:
        self._memory = memory

    @property
    def name(self) -> str:
        return "memory_write"

    @property
    def description(self) -> str:
        return (
            "Save information to long-term memory (MEMORY.md). "
            "Use this when the user asks you to remember something, or when you "
            "learn important facts about the user, their preferences, or the project "
            "that should persist across conversations."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Short identifier for this memory (e.g. 'user_name', 'project_lang').",
                },
                "content": {
                    "type": "string",
                    "description": "The information to remember.",
                },
                "entry_type": {
                    "type": "string",
                    "description": "Category: 'user', 'feedback', 'project', 'reference', or 'note'.",
                    "enum": ["user", "feedback", "project", "reference", "note"],
                    "default": "note",
                },
            },
            "required": ["name", "content"],
        }

    async def execute(self, **kwargs: Any) -> str:
        name = kwargs["name"]
        content = kwargs["content"]
        entry_type = kwargs.get("entry_type", "note")

        self._memory.save_entry(name, content, entry_type)
        return f"Memory saved: {name} ({entry_type})"
