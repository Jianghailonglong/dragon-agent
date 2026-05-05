from __future__ import annotations

import asyncio
from typing import Any

from tools.base import BaseTool


class WebFetchTool(BaseTool):
    """Fetch content from a URL."""

    def __init__(self, max_chars: int = 50_000) -> None:
        self._max_chars = max_chars

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch content from a URL and return it as text."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch."},
            },
            "required": ["url"],
        }

    async def execute(self, **kwargs: Any) -> str:
        url = kwargs.get("url", "")
        if not url.startswith(("http://", "https://")):
            return "Error: URL must start with http:// or https://"

        # SSRF check: block private IPs
        if any(url.startswith(prefix) for prefix in [
            "http://localhost", "https://localhost",
            "http://127.", "https://127.",
            "http://10.", "https://10.",
            "http://192.168.", "https://192.168.",
            "http://172.16.", "https://172.16.",
        ]):
            return "Error: fetching from private/internal URLs is not allowed."

        try:
            import urllib.request
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(None, self._fetch, url)
            if len(content) > self._max_chars:
                content = content[:self._max_chars] + f"\n... [truncated, {len(content)} chars total]"
            return content
        except Exception as e:
            return f"Error fetching URL: {e}"

    def _fetch(self, url: str) -> str:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "DragonAgent/0.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
