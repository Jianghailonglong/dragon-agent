# Dragon Agent

[中文](README.md) | **English**

> A production-grade AI Agent framework. Core philosophy: `Agent = while + stop_reason + layer by layer production capabilities`.

---

## Introduction

Dragon Agent combines progressive teaching philosophy with production-grade implementation to build an extensible AI Agent framework from scratch.

**Tech Stack**: Python 3.11+ / asyncio / Anthropic API (OpenAI compatible)

---

## Quick Start

### 1. Install

```bash
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```env
ANTHROPIC_API_KEY=your_api_key
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

### 3. Run

```bash
# CLI mode
dragon agent

# Web UI mode
dragon web

# Telegram Bot
dragon telegram

# Feishu Bot
dragon feishu

# Run tests
python -m pytest tests/ -v
```

### 4. Customize Persona

Edit files under `workspace/`:

| File | Purpose |
|------|---------|
| `IDENTITY.md` | Agent identity definition |
| `SOUL.md` | Personality and behavior style |
| `TOOLS.md` | Tool usage guidance |
| `MEMORY.md` | Persistent memory |

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│              Application Layer                    │
│              CLI / WebUI / API Gateway            │
├──────────────────────────────────────────────────┤
│              Orchestration Layer                  │
│    Named Lanes │ SubagentManager │ Heartbeat/Cron │
├──────────────────────────────────────────────────┤
│              Resilience Layer                     │
│    3-Layer Retry │ Checkpoint │ Delivery Queue    │
├──────────────────────────────────────────────────┤
│              Intelligence Layer                   │
│    ContextBuilder (8-layer) │ Memory │ Skills     │
├──────────────────────────────────────────────────┤
│              Gateway Layer                        │
│    MessageBus │ 5-Tier Router │ SessionManager    │
├──────────────────────────────────────────────────┤
│              Channel Layer                        │
│    BaseChannel │ CLI │ Telegram │ Feishu │ WeChat │
├──────────────────────────────────────────────────┤
│              Core Layer                           │
│    AgentLoop │ AgentRunner │ ToolRegistry │ Hook  │
└──────────────────────────────────────────────────┘
```

**Layering Principles:**
- Each layer only depends on the one below; upper layers are replaceable
- Core Layer stays pure: only LLM calls + tool dispatch
- Each layer is independently testable

---

## Core Features

### 1. Agent Loop — Top-level Orchestration

```python
# Agent = while loop + stop_reason
while not stop:
    response = llm_call(messages)
    if response.should_execute_tools:
        results = execute_tools(response.tool_calls)
        messages.extend(results)
        continue
    break
```

- `AgentRunner`: Pure execution engine, reusable by subagent/cron/tests
- `AgentLoop`: Consumes messages, manages sessions, orchestrates Runner
- `AgentHook`: Lifecycle hooks (before/after iteration, streaming, finalize)

### 2. 3-Layer Context Defense

| Layer | Strategy | Purpose |
|-------|----------|---------|
| L1 Microcompact | Replace old tool results with `[result omitted]` | Zero-cost local compaction |
| L2 Tool Budget | Truncate oversized single results | Prevent context blowup from large results |
| L3 Snip History | Trim oldest-first, ensure first msg is user | Token budget safety net |

### 3. Session Persistence + Crash Recovery

- **JSONL Persistence**: Append-only, naturally crash-safe, human-readable
- **Checkpoint**: Write session metadata after each tool execution
- **Recovery**: Scan interrupted sessions on startup, auto-append `interrupted` marker

### 4. 8-Layer Prompt Assembly

```
1. Identity    — Identity (IDENTITY.md)
2. Soul        — Personality (SOUL.md)
3. Tools       — Tool guidance (TOOLS.md)
4. Skills      — Skill injection (SKILL.md)
5. Memory      — Persistent memory (MEMORY.md)
6. Bootstrap   — Bootstrap context
7. Runtime     — Runtime metadata
8. Channel     — Channel hints (CLI/Telegram/Feishu)
```

### 5. 5-Tier Gateway Router

```
peer (channel + chat + sender)
  > guild (channel + chat)
    > account (channel + sender)
      > channel
        > default
```

Different message sources can be routed to different Agent configurations.

### 6. Resilience

- **3-Layer Retry Onion**: Tool self-correction → Emergency compaction → Key rotation + backoff
- **Write-Ahead Delivery**: Persist to disk before sending, auto-retry on failure
- **ToolSafetyGuard**: Workspace boundary, SSRF protection, repeated query detection

### 7. Concurrency Model

- `Semaphore`: Cross-session concurrency control
- `Lock`: Intra-session serial processing
- `Named Lanes`: main / cron / heartbeat priority queues
- `SubagentManager`: Parallel sub-agent execution

### 8. Multi-Channel

| Channel | Status | Description |
|---------|--------|-------------|
| CLI | ✅ Available | Local command-line interaction |
| Web | ✅ Available | Web UI interface |
| Telegram | ✅ Available | Bot API long-polling |
| Feishu | ✅ Available | WebSocket long connection |
| WeChat | ✅ Available | WeCom webhook |

---

## Project Structure

```
dragon-agent/
├── core/           # AgentLoop, AgentRunner, AgentHook, types
├── tools/          # ToolRegistry, BaseTool, builtin tools
├── providers/      # LLMProvider, AnthropicProvider, factory
├── session/        # Session (JSONL), SessionManager, compact
├── channels/       # BaseChannel, CLI, Telegram, Feishu, WeChat
├── gateway/        # MessageBus, 5-Tier Router
├── intelligence/   # ContextBuilder, Memory, Skills, Dream
├── resilience/     # Checkpoint, Retry, Delivery, Safety
├── orchestration/  # Lanes, Heartbeat, Cron, Subagent
├── config/         # Schema, Loader (.env + YAML)
├── workspace/      # Agent persona files
├── cli/            # CLI entry point
├── web/            # Web UI
└── tests/          # Unit tests
```

---

## Advantages

| Dimension | Description |
|-----------|-------------|
| **Progressive Design** | From while loop to production-grade, each layer independently understandable and replaceable |
| **High Testability** | Runner has no upper-layer dependency, each layer mock-testable |
| **Production Ready** | Crash recovery, write-ahead delivery, retry resilience, safety guards |
| **Unified Multi-Channel** | Unified message types + 5-tier routing, one codebase for multiple platforms |
| **Context Governance** | 3-layer defense + Dream auto memory extraction, no key info loss in long conversations |
| **Concurrency Safe** | Semaphore + Lock + Named Lanes, session isolation + priority scheduling |
| **Zero External Dependencies** | JSONL persistence needs no database, files are the database |

---

## License

MIT
