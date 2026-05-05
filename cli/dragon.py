"""
Dragon Agent CLI

Usage:
    dragon agent        Start interactive CLI conversation
    dragon web          Start web UI conversation
    dragon telegram     Start Telegram bot
    dragon help         Show this help message
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import load_config, find_project_root
from config.schema import AgentConfig, DragonConfig
from session.manager import SessionManager
from tools.registry import ToolRegistry
from tools.builtin.read_file import ReadFileTool
from tools.builtin.exec import ExecTool
from tools.builtin.ask_user import AskUserTool
from tools.builtin.write_file import WriteFileTool
from tools.builtin.edit_file import EditFileTool
from tools.builtin.grep_tool import GrepTool
from tools.builtin.glob_tool import GlobTool
from tools.builtin.web_fetch import WebFetchTool
from tools.builtin.memory_write import MemoryWriteTool
from tools.builtin.subagent_spawn import SubagentSpawnTool
from tools.builtin.subagent_status import SubagentStatusTool
from channels.cli import CLIChannel
from channels.base import BaseChannel
from core.loop import AgentLoop
from core.logger import ConversationLogger
from intelligence.context import ContextBuilder
from intelligence.skills import SkillsLoader
from intelligence.memory import MemoryStore
from intelligence.workspace import UserWorkspace
from intelligence.dream import Dream
from providers.factory import ProviderFactory
from resilience.checkpoint import CheckpointManager
from resilience.provider_wrapper import wrap_provider_with_retry
from resilience.delivery import DeliveryQueue
from orchestration.heartbeat import HeartbeatService
from orchestration.cron import CronScheduler
from orchestration.subagent import SubagentManager


BANNER = r"""
       __________                  .___
       \______   \ ____   ____   __| _/
        |       _// __ \ /    \ / __ |
        |    |   \  ___/|   |  / /_/ |
        |____|_  /\___  >___|  \____ |
               \/     \/     \/     \/
  ____                                  __
 |  _ \ _ __ __ _  __ _  ___  _ __ ___/ _|
 | | | | '__/ _` |/ _` |/ _ \| '_ \_  / |
 | |_| | | | (_| | (_| | (_) | | | / /| |
 |____/|_|  \__,_|\__, |\___/|_| |_/___|_|
                   |___/
"""


def build_tools(
    user_workspace: UserWorkspace,
    memory: MemoryStore | None = None,
    subagent_mgr: SubagentManager | None = None,
) -> ToolRegistry:
    tools = ToolRegistry()
    tools.register(ReadFileTool(workspace=user_workspace))
    tools.register(WriteFileTool(workspace=user_workspace))
    tools.register(EditFileTool(workspace=user_workspace))
    tools.register(ExecTool(workspace=user_workspace))
    tools.register(AskUserTool())
    tools.register(GrepTool(workspace=user_workspace))
    tools.register(GlobTool(workspace=user_workspace))
    tools.register(WebFetchTool())
    if memory:
        tools.register(MemoryWriteTool(memory=memory))
    if subagent_mgr:
        tools.register(SubagentSpawnTool(manager=subagent_mgr))
        tools.register(SubagentStatusTool(manager=subagent_mgr))
    return tools


def create_agent_loop(
    config: DragonConfig,
    agent_config: AgentConfig,
    channel: BaseChannel,
    channel_name: str,
) -> tuple[AgentLoop, DeliveryQueue]:
    """Create a fully-wired AgentLoop with all layers connected."""
    base_workspace = str((find_project_root() / config.workspace).resolve())
    user_workspace = UserWorkspace(base_workspace)

    memory = MemoryStore(workspace=user_workspace)
    raw_provider = ProviderFactory.create(agent_config.provider)
    provider = wrap_provider_with_retry(raw_provider)
    dream = Dream(provider=raw_provider, memory=memory)

    # Context and skills (per-user workspace aware)
    context_builder = ContextBuilder(workspace=user_workspace)
    skills_loader = SkillsLoader(workspace=user_workspace)

    # Orchestration: subagent manager
    subagent_mgr = SubagentManager(
        provider=raw_provider,
        tools=ToolRegistry(),  # will be replaced below
        max_concurrent=3,
        system_prompt="",  # will be built per-user at runtime
    )

    tools = build_tools(user_workspace, memory=memory, subagent_mgr=subagent_mgr)
    # Give subagent the same tools
    subagent_mgr._tools = tools

    # System prompt will be built per-user in AgentLoop._process_message
    # Fallback prompt for non-user-aware contexts
    always_on = skills_loader.load_always_on()
    fallback_prompt = context_builder.build_system_prompt(
        channel=channel_name, skills=always_on
    )

    session_mgr = SessionManager(storage_dir=str((find_project_root() / "sessions").resolve()))
    checkpoint_mgr = CheckpointManager(session_mgr)
    log_dir = str((find_project_root() / "logs").resolve())
    conv_logger = ConversationLogger(log_dir=log_dir)
    delivery_dir = str((find_project_root() / "delivery").resolve())
    delivery = DeliveryQueue(storage_dir=delivery_dir, send_fn=channel.send)

    # Heartbeat: idle session compaction check
    heartbeat = HeartbeatService(interval_seconds=300.0)  # every 5 min

    # Cron scheduler (empty by default, jobs added programmatically)
    cron = CronScheduler()

    # Crash recovery
    recovered = checkpoint_mgr.recover_all()
    for key, status in recovered.items():
        print(f"  [recovery] Session '{key}': {status}")

    loop = AgentLoop(
        agent_config=agent_config,
        channel=channel,
        session_manager=session_mgr,
        tools=tools,
        system_prompt=fallback_prompt,
        conversation_logger=conv_logger,
        dream=dream,
        checkpoint_manager=checkpoint_mgr,
        provider=provider,
        delivery_queue=delivery,
        heartbeat=heartbeat,
        cron=cron,
        user_workspace=user_workspace,
        context_builder=context_builder,
        skills_loader=skills_loader,
    )

    return loop, delivery


def _load_agent_config(config: DragonConfig) -> AgentConfig:
    """Load the default agent config or exit."""
    agent_config = config.agents.get(config.default_agent)
    if agent_config is None:
        print(f"Error: default agent '{config.default_agent}' not found.")
        sys.exit(1)
    return agent_config


def cmd_agent() -> None:
    """Start interactive CLI conversation."""
    print(BANNER)
    config = load_config()
    agent_config = _load_agent_config(config)
    channel = CLIChannel()
    loop, delivery = create_agent_loop(config, agent_config, channel, "cli")

    async def startup():
        retried = await delivery.retry_pending()
        if retried:
            print(f"  [delivery] Retried {retried} pending messages")
        await loop.run()

    asyncio.run(startup())


def cmd_web() -> None:
    """Start web UI conversation."""
    import uvicorn
    from channels.web import WebChannel
    from web.app import app, set_channel, set_agent_loop

    config = load_config()
    agent_config = _load_agent_config(config)
    channel = WebChannel()
    loop, delivery = create_agent_loop(config, agent_config, channel, "web")

    set_channel(channel)
    set_agent_loop(loop)

    print(BANNER)
    print("  Web UI starting at http://127.0.0.1:8000")
    print("  Press Ctrl+C to stop\n")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


def cmd_telegram() -> None:
    """Start Telegram bot."""
    from channels.telegram import TelegramChannel

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not set.")
        print("Set it in .env or as an environment variable.")
        sys.exit(1)

    print(BANNER)
    config = load_config()
    agent_config = _load_agent_config(config)
    channel = TelegramChannel(token=token)
    loop, delivery = create_agent_loop(config, agent_config, channel, "telegram")

    async def startup():
        retried = await delivery.retry_pending()
        if retried:
            print(f"  [delivery] Retried {retried} pending messages")
        await loop.run()

    asyncio.run(startup())


def cmd_feishu() -> None:
    """Start Feishu (Lark) bot using WebSocket long connection."""
    from channels.feishu import FeishuChannel

    print(BANNER)
    config = load_config()
    agent_config = _load_agent_config(config)

    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        print("Error: FEISHU_APP_ID or FEISHU_APP_SECRET not set.")
        print("Set them in .env or as environment variables.")
        sys.exit(1)

    channel = FeishuChannel(app_id=app_id, app_secret=app_secret)
    loop, delivery = create_agent_loop(config, agent_config, channel, "feishu")

    print("  Feishu bot starting with WebSocket long connection")
    print("  No public IP or webhook setup required")
    print("  Press Ctrl+C to stop\n")

    async def startup():
        # Connect channel FIRST
        await channel.connect()
        print("[feishu] Channel connected")

        # Then retry pending messages
        retried = await delivery.retry_pending()
        if retried:
            print(f"  [delivery] Retried {retried} pending messages")

        # Finally run the agent loop
        await loop.run()

    asyncio.run(startup())


def cmd_help() -> None:
    """Show help message."""
    print(BANNER)
    print("  Usage:")
    print("    dragon agent        Start interactive CLI conversation")
    print("    dragon web          Start web UI conversation")
    print("    dragon telegram     Start Telegram bot")
    print("    dragon feishu       Start Feishu (Lark) bot")
    print("    dragon help         Show this help message")
    print()
    print("  Feishu Configuration:")
    print("    Set in .env file:")
    print("      FEISHU_APP_ID=your_app_id")
    print("      FEISHU_APP_SECRET=your_app_secret")
    print()
    print("    Uses WebSocket long connection - no public IP required")
    print()


COMMANDS = {
    "agent": cmd_agent,
    "web": cmd_web,
    "telegram": cmd_telegram,
    "feishu": cmd_feishu,
    "help": cmd_help,
}


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("help", "--help", "-h"):
        cmd_help()
        return

    cmd = args[0].lower()
    if cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print(f"  Unknown command: {cmd}")
        print("  Run 'dragon help' for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
