from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Callable, Awaitable

from providers.base import LLMProvider, LLMResponse
from tools.registry import ToolRegistry
from session.compact import Microcompact, ToolResultBudget, SnipHistory
from .hook import AgentHook, HookContext

logger = logging.getLogger(__name__)


@dataclass
class AgentRunSpec:
    """Full specification for a single agent run — no dependency on upper layers."""
    messages: list[dict]
    tools: ToolRegistry
    provider: LLMProvider
    model: str | None = None
    system: str | None = None
    max_iterations: int = 20
    max_tokens: int = 4096
    hook: AgentHook | None = None
    context_window_tokens: int = 200_000
    checkpoint_callback: Callable[[int, str], Awaitable[None]] | None = None
    injection_callback: Callable[[], Awaitable[list[dict] | None]] | None = None
    llm_timeout: float = 120.0  # seconds


@dataclass
class AgentRunResult:
    """Result of an agent run."""
    content: str = ""
    messages: list[dict] = field(default_factory=list)
    iterations: int = 0
    usage: dict = field(default_factory=dict)  # cumulative token usage
    hit_iteration_limit: bool = False


class AgentRunner:
    """
    Pure execution engine: LLM call → tool dispatch loop.
    No dependency on MessageBus, SessionManager, or Channels.
    """

    def __init__(self) -> None:
        # 3-layer context defense
        self._microcompact = Microcompact(keep_recent=10)
        self._tool_budget = ToolResultBudget(max_chars=50_000)
        self._snip = SnipHistory(max_tokens=180_000, chars_per_token=4.0)

    def govern_context(self, messages: list[dict]) -> list[dict]:
        """Apply 3-layer context defense before each LLM call."""
        messages = self._microcompact.compact(messages)
        messages = self._tool_budget.apply(messages)
        messages = self._snip.snip(messages)
        return messages

    async def run(self, spec: AgentRunSpec) -> AgentRunResult:
        messages = list(spec.messages)
        iterations = 0
        total_usage = {"input_tokens": 0, "output_tokens": 0}
        recent_tool_calls: list[str] = []  # track (name, input_hash) for loop detection

        for iteration in range(spec.max_iterations):
            iterations = iteration + 1
            ctx = HookContext(iteration=iteration, messages=messages)

            if spec.hook:
                spec.hook.before_iteration(ctx)

            # Apply context governance before LLM call
            messages = self.govern_context(messages)

            # LLM call with timeout
            tool_schemas = spec.tools.list_schemas()
            try:
                response = await asyncio.wait_for(
                    spec.provider.chat_completion(
                        messages=messages,
                        tools=tool_schemas if tool_schemas else None,
                        model=spec.model,
                        system=spec.system,
                        max_tokens=spec.max_tokens,
                    ),
                    timeout=spec.llm_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(f"LLM call timed out after {spec.llm_timeout}s")
                return AgentRunResult(
                    content="(LLM request timed out — the context may be too long. Try sending a shorter message.)",
                    messages=messages,
                    iterations=iterations,
                    usage=total_usage,
                )

            # accumulate usage
            for k in total_usage:
                total_usage[k] += response.usage.get(k, 0)

            # append assistant message
            assistant_msg = self._build_assistant_message(response)
            messages.append(assistant_msg)

            if response.should_execute_tools:
                # Detect tool call loops: same tool + same input repeated
                for tc in response.tool_calls:
                    tc_key = f"{tc['name']}:{json.dumps(tc.get('input', {}), sort_keys=True)}"
                    recent_tool_calls.append(tc_key)
                # Keep only last 6 entries
                recent_tool_calls = recent_tool_calls[-6:]
                # If we see the same call 3+ times in recent history, break the loop
                if len(recent_tool_calls) >= 3:
                    from collections import Counter
                    counts = Counter(recent_tool_calls)
                    most_common, count = counts.most_common(1)[0]
                    if count >= 3:
                        logger.warning(f"Tool loop detected: {most_common} called {count} times")
                        # Force the model to answer without tools
                        messages.append({
                            "role": "user",
                            "content": "[System: You have called the same tool multiple times with the same input. "
                                       "Stop using tools and provide your final answer to the user based on what you have so far.]",
                        })
                        recent_tool_calls.clear()
                        # One more LLM call without tools
                        try:
                            response = await asyncio.wait_for(
                                spec.provider.chat_completion(
                                    messages=messages,
                                    tools=None,  # no tools this time
                                    model=spec.model,
                                    system=spec.system,
                                    max_tokens=spec.max_tokens,
                                ),
                                timeout=spec.llm_timeout,
                            )
                            final_content = response.content or "(No response generated.)"
                            messages.append(self._build_assistant_message(response))
                            return AgentRunResult(
                                content=final_content,
                                messages=messages,
                                iterations=iterations,
                                usage=total_usage,
                            )
                        except Exception:
                            return AgentRunResult(
                                content="(Agent stopped due to repeated tool calls.)",
                                messages=messages,
                                iterations=iterations,
                                usage=total_usage,
                                hit_iteration_limit=True,
                            )
                if spec.hook:
                    spec.hook.before_execute_tools(ctx)

                ctx.tool_calls = response.tool_calls

                # execute tools
                for i, tool_call in enumerate(response.tool_calls):
                    result = await self._execute_tool(spec.tools, tool_call)
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_call["id"],
                            "content": result,
                        }],
                    })

                    # checkpoint after each tool
                    if spec.checkpoint_callback:
                        await spec.checkpoint_callback(i, tool_call["name"])

                ctx.tool_results = [
                    m for m in messages[-len(response.tool_calls):]
                ]

                if spec.hook:
                    spec.hook.after_execute_tools(ctx)
                    spec.hook.after_iteration(ctx)

                # drain injection queue after tools
                if spec.injection_callback:
                    injections = await spec.injection_callback()
                    if injections:
                        messages.extend(injections)

                continue

            # end_turn — finalize
            final_content = response.content
            if spec.hook:
                final_content = spec.hook.finalize_content(ctx, final_content)
                spec.hook.after_iteration(ctx)

            return AgentRunResult(
                content=final_content,
                messages=messages,
                iterations=iterations,
                usage=total_usage,
            )

        # max iterations reached — extract last assistant content and ask to continue
        last_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                parts = msg.get("content", [])
                if isinstance(parts, list):
                    texts = [p["text"] for p in parts if isinstance(p, dict) and p.get("type") == "text"]
                    last_content = "\n".join(texts)
                elif isinstance(parts, str):
                    last_content = parts
                break

        if last_content:
            messages.append({
                "role": "user",
                "content": "[System: The previous response was cut short due to iteration limit. "
                           "Please continue from where you left off.]",
            })
            return AgentRunResult(
                content=last_content + "\n\n[Task partially completed — you can send a message to continue.]",
                messages=messages,
                iterations=iterations,
                usage=total_usage,
                hit_iteration_limit=True,
            )

        return AgentRunResult(
            content="(max iterations reached with no output)",
            messages=messages,
            iterations=iterations,
            usage=total_usage,
            hit_iteration_limit=True,
        )

    async def _execute_tool(self, registry: ToolRegistry, tool_call: dict) -> str:
        name = tool_call["name"]
        tool = registry.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"
        try:
            result = await tool.execute(**tool_call.get("input", {}))
            return result if isinstance(result, str) else json.dumps(result)
        except Exception as e:
            return f"Error executing tool '{name}': {e}"

    def _build_assistant_message(self, response: LLMResponse) -> dict:
        """Build an assistant message dict from LLMResponse."""
        content_parts = []
        if response.content:
            content_parts.append({"type": "text", "text": response.content})
        for tc in response.tool_calls:
            content_parts.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": tc["name"],
                "input": tc["input"],
            })
        return {"role": "assistant", "content": content_parts}
