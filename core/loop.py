from __future__ import annotations

import asyncio
import logging

from config.schema import AgentConfig
from providers.base import LLMProvider
from providers.factory import ProviderFactory
from tools.registry import ToolRegistry
from session.manager import SessionManager
from channels.base import BaseChannel
from core.types import InboundMessage, OutboundMessage
from core.runner import AgentRunner, AgentRunSpec
from core.hook import AgentHook
from core.logger import ConversationLogger
from intelligence.context import ContextBuilder
from intelligence.skills import SkillsLoader
from intelligence.dream import Dream
from intelligence.workspace import UserWorkspace
from resilience.checkpoint import CheckpointManager
from resilience.delivery import DeliveryQueue
from orchestration.heartbeat import HeartbeatService
from orchestration.cron import CronScheduler

logger = logging.getLogger(__name__)


class AgentLoop:
    """
    Top-level orchestrator: consumes messages from channels,
    manages sessions, and delegates to AgentRunner.
    """

    def __init__(
        self,
        agent_config: AgentConfig,
        channel: BaseChannel,
        session_manager: SessionManager,
        tools: ToolRegistry,
        hook: AgentHook | None = None,
        system_prompt: str = "",
        conversation_logger: ConversationLogger | None = None,
        dream: Dream | None = None,
        checkpoint_manager: CheckpointManager | None = None,
        provider: LLMProvider | None = None,
        delivery_queue: DeliveryQueue | None = None,
        heartbeat: HeartbeatService | None = None,
        cron: CronScheduler | None = None,
        user_workspace: UserWorkspace | None = None,
        context_builder: ContextBuilder | None = None,
        skills_loader: SkillsLoader | None = None,
    ) -> None:
        self._config = agent_config
        self._channel = channel
        self._sessions = session_manager
        self._tools = tools
        self._hook = hook
        self._system_prompt = system_prompt
        self._runner = AgentRunner()
        self._provider = provider or ProviderFactory.create(agent_config.provider)
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._concurrency_gate = asyncio.Semaphore(1)  # single user for now
        self._pending_queues: dict[str, asyncio.Queue[dict]] = {}  # mid-turn injection
        self._conv_logger = conversation_logger
        self._dream = dream
        self._checkpoint = checkpoint_manager or CheckpointManager(session_manager)
        self._delivery = delivery_queue
        self._heartbeat = heartbeat
        self._cron = cron
        self._user_workspace = user_workspace
        self._context_builder = context_builder
        self._skills_loader = skills_loader

    def _build_user_system_prompt(self, channel: str) -> str:
        """Build system prompt for the current user (resolves per-user workspace)."""
        if self._context_builder and self._skills_loader:
            always_on = self._skills_loader.load_always_on()
            return self._context_builder.build_system_prompt(
                channel=channel, skills=always_on
            )
        return self._system_prompt

    async def run(self) -> None:
        """Main loop: receive messages and process them."""
        await self._channel.connect()

        # Start background services
        if self._heartbeat:
            await self._heartbeat.start()
        if self._cron:
            await self._cron.start()

        try:
            while True:
                msg = await self._channel.receive()
                await self._dispatch(msg)
        except (SystemExit, KeyboardInterrupt):
            pass
        finally:
            if self._heartbeat:
                await self._heartbeat.stop()
            if self._cron:
                await self._cron.stop()

    async def _send(self, msg: OutboundMessage) -> None:
        """Send message via delivery queue or directly."""
        if self._delivery:
            await self._delivery.enqueue(msg)
        else:
            await self._channel.send(msg)

    async def _run_dream(self, messages: list[dict]) -> None:
        """Run Dream auto-memory extraction in background."""
        try:
            await self._dream.run(messages)
        except Exception as e:
            logger.warning(f"Dream extraction failed: {e}")

    async def _dispatch(self, msg: InboundMessage) -> None:
        """Process a single inbound message."""
        session_key = msg.session_key
        lock = self._session_locks.setdefault(session_key, asyncio.Lock())

        async with lock:
            async with self._concurrency_gate:
                await self._process_message(msg, session_key)

    async def inject_message(self, session_key: str, content: str) -> None:
        """
        Inject a message into the pending queue for a session.
        If the session is currently processing, the message will be
        drained after the current tool execution completes.
        """
        queue = self._pending_queues.setdefault(session_key, asyncio.Queue())
        await queue.put({"role": "user", "content": content})

    async def _drain_injection_queue(self, session_key: str) -> list[dict] | None:
        """Drain all pending injections for a session."""
        queue = self._pending_queues.get(session_key)
        if queue is None or queue.empty():
            return None
        injections = []
        while not queue.empty():
            injections.append(queue.get_nowait())
        return injections if injections else None

    async def _process_message(self, msg: InboundMessage, session_key: str) -> None:
        # Set current user for per-user workspace resolution
        if self._user_workspace:
            self._user_workspace.set_current_user(msg.sender_id)

        session = self._sessions.get_or_create(session_key)
        session.add_message("user", msg.content)

        # Log user message
        if self._conv_logger:
            self._conv_logger.log_user_message(session_key, msg.content)

        # Build per-user system prompt
        system_prompt = self._build_user_system_prompt(msg.channel)

        # Build messages for the runner (include system prompt via spec)
        messages = session.get_messages()

        async def checkpoint_cb(tool_index: int, tool_name: str) -> None:
            self._checkpoint.save_tool_checkpoint(session, tool_index, tool_name)
            if hasattr(self._channel, 'start_spinner'):
                self._channel.start_spinner(f"Running {tool_name}")

        async def injection_cb() -> list[dict] | None:
            return await self._drain_injection_queue(session_key)

        spec = AgentRunSpec(
            messages=messages,
            tools=self._tools,
            provider=self._provider,
            model=self._config.model,
            system=system_prompt or None,
            max_iterations=self._config.max_iterations,
            max_tokens=self._config.provider.max_tokens,
            hook=self._hook,
            context_window_tokens=self._config.context_window_tokens,
            checkpoint_callback=checkpoint_cb,
            injection_callback=injection_cb,
        )

        self._checkpoint.begin_user_turn(session)

        # Start spinner before running
        if hasattr(self._channel, 'start_spinner'):
            self._channel.start_spinner("Thinking")

        try:
            result = await self._runner.run(spec)
        except Exception as e:
            if hasattr(self._channel, 'stop_spinner'):
                self._channel.stop_spinner()
            error_msg = f"Error: {e}"
            if self._conv_logger:
                self._conv_logger.log_error(session_key, error_msg)
            await self._send(OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=error_msg,
            ))
            return
        finally:
            # Stop spinner
            if hasattr(self._channel, 'stop_spinner'):
                self._channel.stop_spinner()

        # Update session with full message history
        session.messages = result.messages
        self._checkpoint.commit_user_turn(session)

        # Log assistant response
        if self._conv_logger and result.content:
            self._conv_logger.log_assistant_message(
                session_key, result.content,
                iterations=result.iterations, usage=result.usage,
            )

        # Send response back through channel
        if result.content:
            await self._send(OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=result.content,
            ))

        # Trigger Dream auto-memory extraction (fire-and-forget)
        # User workspace context is already set from the beginning of this method
        if self._dream and len(result.messages) >= 4:
            asyncio.create_task(self._run_dream(result.messages))
