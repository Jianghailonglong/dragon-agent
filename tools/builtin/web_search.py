from __future__ import annotations

from typing import Any

from tools.base import BaseTool


class WebSearchTool(BaseTool):
    """Search the web (stub - requires external API)."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for information. Returns search result snippets."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> str:
        # Stub: in production, integrate with a search API
        return f"[web_search] No search API configured. Query was: {kwargs.get('query', '')}"
