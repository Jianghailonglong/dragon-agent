from __future__ import annotations

from typing import Callable

import anthropic

from .base import LLMProvider, LLMResponse


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514", base_url: str | None = None) -> None:
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = anthropic.AsyncAnthropic(**kwargs)
        self._default_model = model

    async def chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": model or self._default_model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        resp = await self._client.messages.create(**kwargs)
        return self._parse_response(resp)

    async def stream_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
        on_delta: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": model or self._default_model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        content_blocks: list[dict] = []
        current_text = ""

        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_start":
                    content_blocks.append(event.content_block.model_dump())
                elif event.type == "content_block_delta":
                    delta = event.delta
                    if hasattr(delta, "text") and delta.text:
                        current_text += delta.text
                        if on_delta:
                            on_delta(delta.text)
                    elif hasattr(delta, "partial_json"):
                        # tool use input delta
                        pass
                elif event.type == "content_block_stop":
                    pass

            final = await stream.get_final_message()

        return self._parse_response(final)

    def _parse_response(self, resp) -> LLMResponse:
        content = ""
        tool_calls = []

        for block in resp.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=resp.stop_reason or "",
            usage={
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
        )
