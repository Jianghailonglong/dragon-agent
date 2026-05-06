# Dragon Agent

**[English](README_EN.md)** | 中文

> 一个生产级 AI Agent 框架。核心理念：`Agent = while + stop_reason + 逐层叠加生产级能力`。

---

## 简介

Dragon Agent 结合了渐进式教学理念与生产级实现，从零构建一个可扩展的 AI Agent 框架。

**技术栈**: Python 3.11+ / asyncio / Anthropic API（兼容 OpenAI）

---

## 快速开始

### 1. 安装

```bash
pip install -e .
```

### 2. 配置

```bash
cp .env.example .env
```

编辑 `.env`:

```env
ANTHROPIC_API_KEY=your_api_key
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

### 3. 运行

```bash
# CLI 模式
dragon agent

# Web UI 模式
dragon web

# Telegram Bot
dragon telegram

# 飞书 Bot
dragon feishu

# 运行测试
python -m pytest tests/ -v
```

### 4. 自定义人格

编辑 `workspace/` 下的文件:

| 文件 | 用途 |
|------|------|
| `IDENTITY.md` | Agent 身份定义 |
| `SOUL.md` | 人格与行为风格 |
| `TOOLS.md` | 工具使用指引 |
| `MEMORY.md` | 持久化记忆 |

---

## 架构

```
┌──────────────────────────────────────────────────┐
│              Application Layer                    │
│              CLI / WebUI / API Gateway            │
├──────────────────────────────────────────────────┤
│              Orchestration Layer                  │
│    Named Lanes │ SubagentManager │ Heartbeat/Cron │
├──────────────────────────────────────────────────┤
│              Delivery Layer                       │
│    Write-Ahead Queue │ Persist │ Auto-Retry       │
├──────────────────────────────────────────────────┤
│              Resilience Layer                     │
│    3-Layer Retry │ Checkpoint │ Safety Guard      │
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

**分层原则:**
- 每层只依赖下一层，上层可替换不影响下层
- Core Layer 保持纯粹：只关心 LLM 调用 + 工具分发
- 各层可独立测试

---

## 核心功能

### 1. Agent Loop — 顶层编排

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

- `AgentRunner`: 纯执行引擎，可被 subagent/cron/测试复用
- `AgentLoop`: 消费消息、管理会话、编排 Runner
- `AgentHook`: 生命周期钩子 (before/after iteration, streaming, finalize)

### 2. 上下文管理 3 层防御

| Layer | 策略 | 作用 |
|-------|------|------|
| L1 Microcompact | 旧工具结果替换为 `[result omitted]` | 零成本本地压缩 |
| L2 Tool Budget | 单条结果超限截断 | 防止单条巨量结果撑爆上下文 |
| L3 Snip History | 从旧到新裁剪，保证首条是 user | Token 预算兜底 |

### 3. 会话持久化 + 崩溃恢复

- **JSONL 持久化**: Append-only，天然 crash-safe，人类可读
- **Checkpoint**: 每个工具执行完写入 session metadata
- **恢复机制**: 启动时扫描中断的 session，自动补一条 `interrupted` 标记

### 4. 8 层 Prompt 组装

```
1. Identity    — 身份 (IDENTITY.md)
2. Soul        — 人格 (SOUL.md)
3. Tools       — 工具指引 (TOOLS.md)
4. Skills      — 技能注入 (SKILL.md)
5. Memory      — 持久化记忆 (MEMORY.md)
6. Bootstrap   — 启动上下文
7. Runtime     — 运行时元数据
8. Channel     — 通道提示 (CLI/Telegram/Feishu)
```

### 5. 5-Tier 网关路由

```
peer (channel + chat + sender)
  > guild (channel + chat)
    > account (channel + sender)
      > channel
        > default
```

不同消息来源可路由到不同 Agent 配置。

### 6. 容错设计

- **3-Layer Retry Onion**: 工具自纠正 → 紧急压缩 → key 轮换 + backoff
- **Write-Ahead Delivery**: 先写磁盘再发送，失败自动重试
- **ToolSafetyGuard**: workspace 边界、SSRF 防护、重复查询限制

### 7. 并发模型

- `Semaphore`: 跨会话并发控制
- `Lock`: 会话内串行处理
- `Named Lanes`: main / cron / heartbeat 优先级队列
- `SubagentManager`: 子 agent 并行执行

### 8. 多通道

| Channel | 状态 | 说明 |
|---------|------|------|
| CLI | ✅ 可用 | 本地命令行交互 |
| Web | ✅ 可用 | Web UI 界面 |
| Telegram | ✅ 可用 | Bot API long-polling |
| Feishu | ✅ 可用 | WebSocket 长连接 |
| WeChat | ✅ 可用 | WeCom webhook |

---

## 项目结构

```
dragon-agent/
├── core/           # AgentLoop, AgentRunner, AgentHook, types
├── tools/          # ToolRegistry, BaseTool, builtin tools
├── providers/      # LLMProvider, AnthropicProvider, factory
├── session/        # Session (JSONL), SessionManager, compact
├── channels/       # BaseChannel, CLI, Telegram, Feishu, WeChat
├── gateway/        # MessageBus, 5-Tier Router, MessageBus
├── intelligence/   # ContextBuilder, Memory, Skills, Dream
├── resilience/     # Checkpoint, Retry, Safety
├── delivery/       # Write-Ahead Delivery Queue
├── orchestration/  # Lanes, Heartbeat, Cron, Subagent
├── config/         # Schema, Loader (.env + YAML)
├── workspace/      # Agent persona files
├── docs/           # Documentation
├── cli/            # CLI entry point
├── web/            # Web UI
└── tests/          # Unit tests
```

---

## 优势

| 维度 | 说明 |
|------|------|
| **渐进式设计** | 从 while loop 到生产级，每层可独立理解和替换 |
| **高可测试性** | Runner 不依赖上层，每层可 mock 测试 |
| **生产就绪** | 崩溃恢复、写前投递、重试容错、安全防护 |
| **多通道统一** | 统一消息类型 + 5-tier 路由，一套代码接多平台 |
| **上下文治理** | 3 层防御 + Dream 自动记忆提取，长对话不丢失关键信息 |
| **并发安全** | Semaphore + Lock + Named Lanes，会话隔离 + 优先级调度 |
| **零外部依赖** | JSONL 持久化无需数据库，文件即数据库 |

---

## License

MIT
