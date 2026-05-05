from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HookContext:
    """Context passed to hook methods."""
    iteration: int = 0
    messages: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class AgentHook:
    """Base class for agent lifecycle hooks. Override methods as needed."""

    def before_iteration(self, ctx: HookContext) -> None:
        """Called before each agent loop iteration."""

    def before_execute_tools(self, ctx: HookContext) -> None:
        """Called before tool execution begins."""

    def after_execute_tools(self, ctx: HookContext) -> None:
        """Called after all tools in an iteration finish."""

    def after_iteration(self, ctx: HookContext) -> None:
        """Called after each agent loop iteration."""

    def finalize_content(self, ctx: HookContext, content: str) -> str:
        """Post-process the final content before returning."""
        return content

    def wants_streaming(self) -> bool:
        """Whether this hook wants streaming callbacks."""
        return False

    def on_stream(self, ctx: HookContext, delta: str) -> None:
        """Called on each streaming text delta."""

    def on_stream_end(self, ctx: HookContext, resuming: bool) -> None:
        """Called when streaming for a turn ends."""


class CompositeHook(AgentHook):
    """Combines multiple hooks into one, calling them in order."""

    def __init__(self, hooks: list[AgentHook] | None = None):
        self._hooks: list[AgentHook] = hooks or []

    def add(self, hook: AgentHook) -> None:
        self._hooks.append(hook)

    def before_iteration(self, ctx: HookContext) -> None:
        for h in self._hooks:
            h.before_iteration(ctx)

    def before_execute_tools(self, ctx: HookContext) -> None:
        for h in self._hooks:
            h.before_execute_tools(ctx)

    def after_execute_tools(self, ctx: HookContext) -> None:
        for h in self._hooks:
            h.after_execute_tools(ctx)

    def after_iteration(self, ctx: HookContext) -> None:
        for h in self._hooks:
            h.after_iteration(ctx)

    def finalize_content(self, ctx: HookContext, content: str) -> str:
        for h in self._hooks:
            content = h.finalize_content(ctx, content)
        return content

    def wants_streaming(self) -> bool:
        return any(h.wants_streaming() for h in self._hooks)

    def on_stream(self, ctx: HookContext, delta: str) -> None:
        for h in self._hooks:
            h.on_stream(ctx, delta)

    def on_stream_end(self, ctx: HookContext, resuming: bool) -> None:
        for h in self._hooks:
            h.on_stream_end(ctx, resuming)
