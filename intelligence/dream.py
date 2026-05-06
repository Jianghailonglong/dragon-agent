from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

from providers.base import LLMProvider
from .memory import MemoryStore

logger = logging.getLogger(__name__)


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

        try:
            resp = await self._provider.chat_completion(
                messages=prompt,
                max_tokens=1024,
            )
        except Exception as e:
            logger.error(f"Dream LLM call failed ({len(messages)} messages): {e}")
            return []

        extracted = []
        # Handle None or empty content gracefully
        if not resp or not resp.content:
            logger.debug("Dream: LLM returned empty response, skipping extraction")
            return []

        text = resp.content.strip()

        # Skip if response is empty after stripping
        if not text:
            logger.debug("Dream: LLM returned whitespace-only response, skipping extraction")
            return []

        try:
            # Try direct JSON parse first
            entries = json.loads(text)
        except json.JSONDecodeError:
            # Try extracting JSON array from markdown code blocks or surrounding text
            entries = self._extract_json_array(text)

        if entries is None:
            logger.warning(f"Dream: could not parse JSON from response. Raw: {text[:200]}")
            return []

        try:
            if isinstance(entries, list):
                for entry in entries:
                    name = entry.get("name", "unnamed")
                    content = entry.get("content", "")
                    entry_type = entry.get("type", "note")
                    if content:
                        self._memory.save_entry(name, content, entry_type)
                        extracted.append(name)
        except (KeyError, AttributeError) as e:
            logger.warning(f"Dream: error processing entries: {e}")

        return extracted

    def _extract_json_array(self, text: str) -> list | None:
        """Extract a JSON array from text that may contain markdown or other content."""
        # Try removing markdown code block wrapping
        if "```" in text:
            # Extract content between ``` markers
            match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except json.JSONDecodeError:
                    pass

        # Try finding a JSON array in the text using regex
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None
