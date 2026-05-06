from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Callable, Awaitable

from providers.base import LLMProvider, LLMResponse
from tools.registry import ToolRegistry
from session.compact import Microcompact, ToolResultBudget, SnipHistory, Consolidator
from .hook import AgentHook, HookContext
from .structured_logger import StructuredLogger, timer, elapsed_ms

logger = logging.getLogger(__name__)


class TokenOverflowError(Exception):
    """Context window exceeded even after governance."""
    pass


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
    consolidator_provider: LLMProvider | None = None
    max_concurrent_tools: int = 5


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
        self._slog = StructuredLogger(__name__)

    def govern_context(self, messages: list[dict], spec: AgentRunSpec | None = None) -> list[dict]:
        """Apply sync context defense layers before each LLM call.

        Layer 1: Microcompact (zero-cost local compaction)
        Layer 2: Tool Result Budget (truncate oversized results)
        Layer 3: Snip History (token-budget trimming, dynamic from spec)
        """
        messages = self._microcompact.compact(messages)
        messages = self._tool_budget.apply(messages)

        # Layer 3: dynamic token budget from spec (90% of context_window)
        context_window = spec.context_window_tokens if spec else 200_000
        max_tokens = int(context_window * 0.9)
        snip = SnipHistory(max_tokens=max_tokens, chars_per_token=4.0)
        messages = snip.snip(messages)

        return messages

    async def consolidate_if_needed(self, messages: list[dict], spec: AgentRunSpec) -> list[dict]:
        """Layer 4: Consolidator — LLM-powered summary compression when still over budget."""
        if not spec.consolidator_provider:
            return messages

        context_window = spec.context_window_tokens
        max_chars = int(context_window * 4.0)
        total_chars = sum(self._estimate_chars(m) for m in messages)

        if total_chars <= max_chars:
            return messages

        try:
            consolidator = Consolidator(spec.consolidator_provider)
            target_tokens = int(context_window * 0.5)
            messages = await consolidator.consolidate(messages, target_tokens=target_tokens)
            logger.info("Consolidator compressed messages to fit context window")
        except Exception as e:
            logger.warning(f"Consolidator failed, using SnipHistory results: {e}")

        return messages

    def _estimate_chars(self, msg: dict) -> int:
        import json
        content = msg.get("content", "")
        if isinstance(content, str):
            return len(content)
        if isinstance(content, list):
            return sum(len(json.dumps(b, ensure_ascii=False)) for b in content)
        return len(json.dumps(content, ensure_ascii=False))

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
            messages = self.govern_context(messages, spec)
            messages = await self.consolidate_if_needed(messages, spec)

            # If messages are still too large after all governance, raise for retry layer
            total_chars = sum(self._estimate_chars(m) for m in messages)
            if total_chars > spec.context_window_tokens * 4:
                raise TokenOverflowError(
                    f"Context still exceeds {spec.context_window_tokens} tokens after governance"
                )

            # LLM call with timeout
            tool_schemas = spec.tools.list_schemas()
            model_name = spec.model or "default"
            self._slog.llm_call_start(model_name, len(messages))
            llm_start = timer()
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
                self._slog.llm_call_end(
                    model_name,
                    response.usage.get("input_tokens", 0),
                    response.usage.get("output_tokens", 0),
                    elapsed_ms(llm_start),
                    response.stop_reason,
                )
            except asyncio.TimeoutError:
                self._slog.llm_call_error(model_name, "timeout", elapsed_ms(llm_start))
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

                # execute tools — concurrent for 2+, sequential for 1
                if len(response.tool_calls) >= 2:
                    results = await self._execute_tools_concurrent(
                        spec.tools, response.tool_calls, spec.max_concurrent_tools
                    )
                    for i, (tool_call, result) in enumerate(results):
                        messages.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": tool_call["id"],
                                "content": result,
                            }],
                        })
                        if spec.checkpoint_callback:
                            await spec.checkpoint_callback(i, tool_call["name"])
                else:
                    tool_call = response.tool_calls[0]
                    result = await self._execute_tool(spec.tools, tool_call)
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_call["id"],
                            "content": result,
                        }],
                    })
                    if spec.checkpoint_callback:
                        await spec.checkpoint_callback(0, tool_call["name"])

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
            self._slog.tool_execute(name, 0, False, error=f"unknown tool '{name}'")
            return f"Error: unknown tool '{name}'"
        tool_start = timer()
        try:
            result = await tool.execute(**tool_call.get("input", {}))
            self._slog.tool_execute(name, elapsed_ms(tool_start), True)
            return result if isinstance(result, str) else json.dumps(result)
        except Exception as e:
            self._slog.tool_execute(name, elapsed_ms(tool_start), False, error=str(e))
            return f"Error executing tool '{name}': {e}"

    async def _execute_single_tool_safe(self, registry: ToolRegistry, tool_call: dict) -> tuple[dict, str]:
        """Execute a single tool and return (tool_call, result). Isolates errors."""
        try:
            result = await self._execute_tool(registry, tool_call)
        except Exception as e:
            result = f"Error executing tool '{tool_call['name']}': {e}"
        return tool_call, result

    async def _execute_tools_concurrent(
        self, registry: ToolRegistry, tool_calls: list[dict], max_concurrent: int
    ) -> list[tuple[dict, str]]:
        """Execute multiple tools concurrently with a concurrency limit."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_execute(tc: dict) -> tuple[dict, str]:
            async with semaphore:
                return await self._execute_single_tool_safe(registry, tc)

        return await asyncio.gather(*[bounded_execute(tc) for tc in tool_calls])

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
