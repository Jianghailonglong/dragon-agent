# Dragon Agent 架构设计文档

> 一个通用 AI Agent 框架，结合 claw0 的渐进教学理念与 nanobot 的生产级实现。

## 1. 项目定位

**目标**：构建一个从零到生产的 AI Agent 框架，核心理念是"Agent = while + stop_reason + 逐层叠加生产级能力"。

**技术栈**：Python 3.11+ / asyncio / Anthropic API（兼容 OpenAI）

**简历亮点**：
- Agent Loop 的工程化设计（Hook 生命周期、Checkpoint 恢复、Mid-turn Injection）
- 上下文管理的 3 层防御（Microcompact → Tool Budget → Snip History）
- asyncio 并发模型（Semaphore + Lock + Named Lanes）
- JSONL 会话持久化 + 崩溃恢复机制
- 8 层 Prompt 组装 + Memory 系统（Dream 自动提取）
- 5-tier 网关路由
- 3-layer Retry Onion + Write-Ahead Delivery

---

## 2. 整体架构

```
┌──────────────────────────────────────────────────────────┐
│                    Application Layer                       │
│  CLI / WebUI / API Gateway                                │
├──────────────────────────────────────────────────────────┤
│                    Orchestration Layer                     │
│  Named Lanes │ SubagentManager │ Heartbeat/Cron           │
├──────────────────────────────────────────────────────────┤
│                    Resilience Layer                        │
│  3-Layer Retry │ Checkpoint Recovery │ Delivery Queue      │
├──────────────────────────────────────────────────────────┤
│                    Intelligence Layer                      │
│  ContextBuilder (8-layer prompt) │ Memory + Dream │ Skills │
├──────────────────────────────────────────────────────────┤
│                    Gateway Layer                           │
│  MessageBus │ 5-Tier Router │ SessionManager               │
├──────────────────────────────────────────────────────────┤
│                    Channel Layer                           │
│  BaseChannel ABC │ CLI + Feishu + Telegram + WeChat        │
├──────────────────────────────────────────────────────────┤
│                    Core Layer                              │
│  AgentLoop │ AgentRunner │ ToolRegistry │ AgentHook        │
└──────────────────────────────────────────────────────────┘
```

**分层原则**：
- 每层只依赖下一层，上层可替换不影响下层
- Core Layer 保持纯粹：只关心 LLM 调用 + 工具分发
- Gateway Layer 处理路由、会话、消息总线
- 各层可独立测试

---

## 3. Core Layer（核心层）

### 3.1 AgentLoop — 顶层编排器

```python
class AgentLoop:
    """
    职责：从 MessageBus 消费消息，编排整个处理流程。
    不直接调 LLM，委托给 AgentRunner。
    """
    bus: MessageBus
    runner: AgentRunner
    sessions: SessionManager
    tools: ToolRegistry
    context: ContextBuilder

    # 并发控制
    _session_locks: dict[str, asyncio.Lock]      # 会话内串行
    _concurrency_gate: asyncio.Semaphore          # 跨会话并发
    _pending_queues: dict[str, asyncio.Queue]     # mid-turn 注入队列
```

### 3.2 AgentRunner — 纯执行引擎

```python
@dataclass
class AgentRunSpec:
    """一次 agent 执行的全部配置——不依赖任何上层模块"""
    initial_messages: list[dict]
    tools: ToolRegistry
    model: str
    max_iterations: int
    hook: AgentHook | None
    checkpoint_callback: Callable
    injection_callback: Callable
    concurrent_tools: bool
    context_window_tokens: int

class AgentRunner:
    async def run(self, spec: AgentRunSpec) -> AgentRunResult:
        for iteration in range(spec.max_iterations):
            messages = self._govern_context(spec, messages)
            response = await self._request_model(spec, messages)

            if response.should_execute_tools:
                results = await self._execute_tools(spec, tool_calls)
                await spec.checkpoint_callback(...)
                injections = await spec.injection_callback()
                if injections:
                    messages.extend(injections)
                continue

            # end_turn
            break
```

**设计决策**：AgentRunner 和 AgentLoop 分离。
- Runner 可被 subagent、cron、测试直接复用
- Runner 不依赖 MessageBus/SessionManager，方便单元测试

### 3.3 AgentHook — 生命周期钩子

```python
class AgentHook:
    def before_iteration(self, ctx): ...
    def before_execute_tools(self, ctx): ...
    def after_iteration(self, ctx): ...
    def finalize_content(self, ctx, content): ...
    def wants_streaming(self) -> bool: ...
    def on_stream(self, ctx, delta): ...
    def on_stream_end(self, ctx, resuming): ...
```

Hook 模式优于散落的 callback：
- 一个对象多个方法，可组合（CompositeHook）
- 横切关注点（streaming、logging、progress）有统一挂载点

### 3.4 Checkpoint + Injection 机制

```
用户消息 ──→ AgentLoop ──→ AgentRunner
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
               LLM 调用   工具执行   工具执行
                    │         │         │
                    │    checkpoint  checkpoint
                    │         │         │
                    │    drain injection
                    ▼         ▼         ▼
               stop_reason=end_turn → 返回
```

- **Checkpoint**：每个工具执行完写入 session metadata，崩溃后可恢复
- **Injection**：工具执行后检查 `_pending_queues`，新消息注入当前 turn

---

## 4. Channel Layer（通道层）

### 4.1 统一消息类型

```python
@dataclass
class InboundMessage:
    channel: str        # "telegram" | "feishu" | "wechat" | "cli"
    sender_id: str
    chat_id: str
    content: str
    media: list[str]
    metadata: dict
    session_key_override: str | None = None

    @property
    def session_key(self) -> str:
        return self.session_key_override or f"{self.channel}:{self.chat_id}"

@dataclass
class OutboundMessage:
    channel: str
    chat_id: str
    content: str
    metadata: dict
```

### 4.2 Channel 抽象

```python
class BaseChannel(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def receive(self) -> InboundMessage: ...

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None: ...

class ChannelManager:
    _channels: dict[str, BaseChannel]
    def register(self, name, channel): ...
    def get(self, name) -> BaseChannel: ...
```

**实现计划**：CLI + 飞书 + Telegram + 微信（4 个通道）

---

## 5. Gateway Layer（网关层）

### 5.1 MessageBus

```python
class MessageBus:
    _inbound: asyncio.Queue[InboundMessage]
    _outbound: asyncio.Queue[OutboundMessage]

    async def publish_inbound(self, msg): ...
    async def consume_inbound(self) -> InboundMessage: ...
    async def publish_outbound(self, msg): ...
    async def consume_outbound(self) -> OutboundMessage: ...
```

### 5.2 5-Tier Router（来自 claw0）

```python
class GatewayRouter:
    """
    5-tier binding: peer > guild > account > channel > default

    配置从 workspace/bindings.yaml 读取：
    bindings:
      - tier: peer
        channel: telegram
        chat_id: "groupA"
        sender_id: "user123"
        agent: agent_a
      - tier: guild
        channel: telegram
        chat_id: "groupB"
        agent: agent_b
      - tier: default
        agent: default_agent
    """
    def resolve(self, msg: InboundMessage) -> AgentConfig:
        # 按优先级匹配：peer → guild → account → channel → default
        for binding in sorted(self._bindings, key=lambda b: b.tier_priority):
            if binding.matches(msg):
                return binding.agent_config
        return self._default_config
```

### 5.3 数据流全景

```
Telegram ──→ TelegramChannel.receive()
                │
                ▼
         InboundMessage(channel="telegram", chat_id="groupA", ...)
                │
                ▼
           MessageBus.publish_inbound()
                │
                ▼
         GatewayRouter.resolve(msg) → AgentConfig
                │
                ▼
           AgentLoop._dispatch(msg)
                │
                ▼
           AgentRunner.run(spec)  ←── 会话 + 工具 + LLM
                │
                ▼
           OutboundMessage(channel="telegram", chat_id="groupA", ...)
                │
                ▼
         TelegramChannel.send(msg) ──→ Telegram API
```

---

## 6. Session Layer（会话层）

### 6.1 JSONL 持久化

```python
@dataclass
class Session:
    key: str
    messages: list[dict]
    metadata: dict  # checkpoint、pending_turn
    created_at: datetime
    updated_at: datetime

class SessionManager:
    def get_or_create(self, key: str) -> Session: ...
    def save(self, session: Session) -> None: ...    # append to JSONL
    def load(self, key: str) -> Session: ...          # replay JSONL
```

**为什么用 JSONL 而不是 SQLite**：
1. Append-only，天然 crash-safe
2. 人类可读，调试方便
3. 无外部依赖

### 6.2 上下文溢出的 3 层防御

```python
def _govern_context(self, spec, messages):
    # Layer 1: Microcompact（零成本本地操作）
    #   旧工具结果替换为 "[read_file result omitted]"
    #   保留最近 10 条工具结果
    messages = self._microcompact(messages)

    # Layer 2: Tool Result Budget
    #   单条结果超 max_chars → 截断或写磁盘
    messages = self._apply_tool_result_budget(spec, messages)

    # Layer 3: Snip History（token 预算裁剪）
    #   从旧到新裁剪，保证第一条是 user message
    messages = self._snip_history(spec, messages)

    return messages
```

### 6.3 崩溃恢复

```
用户消息 ─→ 持久化 ─→ LLM调用 ─→ 工具1 ─→ 工具2 ─→ 💥崩溃
              ✓          ✓         ✓        ✗
              │          │         │
         pending_turn  checkpoint  checkpoint
              │          │         │
恢复时：   补一条        已恢复    标记为
         assistant      已恢复    "interrupted"
         "interrupted"
```

### 6.4 AutoCompact + Consolidator

```python
class AutoCompact:
    """idle session 自动压缩（30 分钟无活动触发）"""

class Consolidator:
    """token 超预算时用 LLM 压缩旧消息为摘要"""
```

---

## 7. Intelligence Layer（智能层）

### 7.1 8 层 Prompt 组装

```python
class ContextBuilder:
    def build_system_prompt(self, channel, ...) -> str:
        parts = [
            self._layer_identity(channel),      # 1. 身份
            self._layer_soul(),                  # 2. 人格（SOUL.md）
            self._layer_tools_guidance(),        # 3. 工具指引
            self._layer_skills(skill_names),     # 4. 技能（SKILL.md）
            self._layer_memory(),                # 5. 记忆（MEMORY.md）
            self._layer_bootstrap(),             # 6. 启动上下文
            self._layer_runtime_context(msg),    # 7. 运行时元数据
            self._layer_channel_hints(channel),  # 8. 通道提示
        ]
        return "\n\n---\n\n".join(parts)
```

### 7.2 Memory 系统

```python
class MemoryStore:
    """文件即数据库：MEMORY.md + history.jsonl"""

class Consolidator:
    """对话压缩：token 超预算时 LLM 摘要化旧消息"""

class Dream:
    """
    自动记忆提取：后台扫描对话历史，
    提取值得记住的信息写入 MEMORY.md
    （类似人类睡眠时的记忆巩固）
    """
```

**记忆流转**：
```
对话历史 → Dream 提取 → MEMORY.md → ContextBuilder 注入 prompt
                ↓
         history.jsonl 归档
```

### 7.3 Skills 系统

```python
class SkillsLoader:
    """
    技能 = SKILL.md 文件（YAML frontmatter + Markdown body）
    放在 workspace/skills/ 下，启动时自动发现
    """

# SKILL.md 示例：
# ---
# name: code-review
# description: Review code for best practices
# always_on: false
# ---
# When invoked, review code for security, performance, style.
```

**Tool vs Skill 区别**：
- Tool = LLM 可调用的函数（有 schema、有 handler）
- Skill = 注入 prompt 的知识/指引（纯文本，无 schema）

---

## 8. Resilience Layer（韧性层）

### 8.1 Checkpoint 恢复（来自 nanobot）

```python
class AgentLoop:
    _RUNTIME_CHECKPOINT_KEY = "runtime_checkpoint"
    _PENDING_USER_TURN_KEY = "pending_user_turn"

    async def _process_message(self, msg, ...):
        # ① 用户消息先持久化
        session.add_message("user", msg.content)
        self._mark_pending_user_turn(session)
        self.sessions.save(session)

        # ② AgentRunner 每执行完工具写 checkpoint
        # ③ 完成后清理
        self._clear_pending_user_turn(session)
        self._clear_runtime_checkpoint(session)
```

### 8.2 3-Layer Retry Onion（来自 claw0）

```python
async def run_with_resilience(self, spec):
    for attempt in range(max_retries):
        try:
            return await self.runner.run(spec)
        except TokenOverflowError:
            # Layer 2: 紧急压缩
            spec.initial_messages = self._emergency_compact(...)
        except RateLimitError:
            # Layer 3: 切换 key
            self._rotate_auth_profile()
        except LLMAPIError:
            await asyncio.sleep(backoff(attempt))
    # Layer 1: 工具层重试由 LLM 自行决定（错误信息喂回 LLM）
```

**关键区分**：Layer 1 不是代码重试，是把错误信息喂回 LLM 让它自我纠正。

### 8.3 Write-Ahead Delivery Queue

```python
class DeliveryQueue:
    async def enqueue(self, msg: OutboundMessage):
        # ① 先写磁盘
        self._append_to_disk(entry)
        # ② 再发送
        try:
            await self.channel.send(msg)
            self._mark_delivered(entry_id)
        except DeliveryError:
            pass  # 保留在队列，后台指数退避重试
```

### 8.4 工具安全防护

```python
class ToolSafetyGuard:
    def check_workspace_boundary(self, tool_name, path):
        """文件操作不能超出 workspace"""

    def check_url_safety(self, url):
        """web_fetch 不能访问内网（SSRF 防护）"""

    def check_repeated_lookup(self, tool_name, args, counts):
        """同一外部查询不能重复太多次（防死循环）"""
```

---

## 9. Orchestration Layer（编排层）

### 9.1 Named Lanes（来自 claw0）

```python
class LaneQueue:
    """
    命名队列：不同优先级走不同 lane
    main:      用户消息（最高优先级）
    cron:      定时任务
    heartbeat: 心跳检查
    """
```

### 9.2 Heartbeat + Cron

```python
class HeartbeatService:
    """定时检查：agent 是否需要主动发言"""
    interval: int  # 秒

class CronScheduler:
    """定时任务：定期执行指定操作"""
    jobs: list[CronJob]
```

### 9.3 SubagentManager

```python
class SubagentManager:
    async def spawn(self, task, parent_session) -> str:
        """创建子 agent 并行处理子任务"""
        # 主 agent spawn 子 agent，结果通过 MessageBus 注回
```

---

## 10. Provider 抽象

```python
class LLMProvider(ABC):
    @abstractmethod
    async def chat_completion(self, messages, tools, model, ...) -> LLMResponse: ...

    @abstractmethod
    async def stream_completion(self, messages, ..., on_delta) -> LLMResponse: ...

class ProviderFactory:
    @staticmethod
    def create(config) -> LLMProvider:
        # 根据 model prefix 自动选择后端
        # anthropic/ → AnthropicProvider
        # bedrock/ → BedrockProvider
        # 默认 → OpenAICompatProvider
```

---

## 11. 项目结构

```
dragon-agent/
├── core/                    # Layer 1: 核心
│   ├── loop.py             # AgentLoop
│   ├── runner.py           # AgentRunner + AgentRunSpec
│   ├── hook.py             # AgentHook 生命周期
│   └── types.py            # InboundMessage, OutboundMessage
│
├── tools/                   # 工具系统
│   ├── registry.py         # ToolRegistry
│   ├── base.py             # BaseTool ABC
│   ├── safety.py           # ToolSafetyGuard
│   └── builtin/            # filesystem, shell, web, ask, message...
│
├── session/                 # Layer 2: 会话
│   ├── manager.py          # SessionManager
│   ├── session.py          # Session + JSONL
│   └── compact.py          # AutoCompact + Consolidator
│
├── channels/                # Layer 3: 通道
│   ├── base.py             # BaseChannel ABC
│   ├── manager.py          # ChannelManager
│   ├── cli.py
│   ├── feishu.py
│   ├── telegram.py
│   └── wechat.py
│
├── gateway/                 # Layer 4: 网关
│   ├── bus.py              # MessageBus
│   └── router.py           # 5-tier GatewayRouter
│
├── intelligence/            # Layer 5: 智能
│   ├── context.py          # ContextBuilder (8-layer prompt)
│   ├── memory.py           # MemoryStore + Dream
│   └── skills.py           # SkillsLoader
│
├── resilience/              # Layer 6: 韧性
│   ├── retry.py            # 3-layer retry onion
│   ├── delivery.py         # Write-ahead delivery queue
│   └── checkpoint.py       # Checkpoint 恢复
│
├── orchestration/           # Layer 7: 编排
│   ├── lanes.py            # Named Lanes
│   ├── heartbeat.py        # Heartbeat + Cron
│   └── subagent.py         # SubagentManager
│
├── providers/               # LLM 提供者
│   ├── base.py             # LLMProvider ABC
│   ├── anthropic.py
│   ├── openai_compat.py
│   └── factory.py          # ProviderFactory
│
├── config/                  # 配置
│   ├── schema.py           # Pydantic config
│   └── loader.py
│
├── workspace/               # Agent 人格/配置
│   ├── SOUL.md
│   ├── IDENTITY.md
│   ├── TOOLS.md
│   ├── MEMORY.md
│   ├── bindings.yaml       # 5-tier 路由配置
│   └── skills/
│
└── cli/                     # 入口
    └── main.py
```

---

## 12. 实施计划

### Phase 1：Core（核心可运行）
1. Core Layer：AgentLoop + AgentRunner + AgentHook
2. ToolRegistry + 3 个基础工具（read_file, exec, ask_user）
3. CLI Channel
4. Provider（Anthropic）
5. 基础 Session（内存）

**里程碑**：CLI 下可以和 agent 对话，agent 能调用工具

### Phase 2：Session + Intelligence（会话 + 智能）
6. JSONL 持久化 + SessionManager
7. 上下文溢出 3 层防御
8. ContextBuilder 8 层 prompt 组装
9. MemoryStore + SkillsLoader
10. 更多工具（write_file, edit_file, grep, glob, web_search, web_fetch）

**里程碑**：agent 有记忆、有技能、会话可持久化

### Phase 3：Gateway + Channels（网关 + 通道）
11. MessageBus
12. 5-tier GatewayRouter
13. ChannelManager + TelegramChannel
14. FeishuChannel + WeChatChannel

**里程碑**：多通道接入，多 agent 路由

### Phase 4：Resilience（韧性）
15. Checkpoint 恢复
16. 3-layer retry onion
17. Write-ahead delivery queue
18. 工具安全防护

**里程碑**：崩溃恢复、重试容错

### Phase 5：Orchestration（编排）
19. Named Lanes
20. Heartbeat + Cron
21. SubagentManager
22. Dream（自动记忆提取）

**里程碑**：主动 agent、子 agent 并行

---

## 13. 面试叙事线

### 开场（30秒）
> "Dragon Agent 是一个 AI Agent 框架，核心理念是 Agent = while + stop_reason，然后逐层叠加生产级能力：会话管理、多通道、上下文治理、并发控制、容错恢复。"

### 展开（按追问深入）
1. **Agent Loop** → Hook 生命周期 → Checkpoint → Injection
2. **上下文管理** → 3 层防御 → Microcompact vs Consolidator
3. **并发模型** → Semaphore + Lock → Named Lanes
4. **会话持久化** → JSONL → 崩溃恢复流程图
5. **Prompt 工程** → 8 层组装 → Memory + Dream
6. **网关路由** → 5-tier binding → 多 agent 隔离
7. **容错设计** → 3-layer retry → Write-ahead delivery
