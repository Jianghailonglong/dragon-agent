# Dragon Agent 全层串联计划

> 目标：将 7 层架构中所有已实现但未接入的模块逐层串联，形成完整的生产级 Agent。

## 当前状态 ✅ 全部完成

```
✅ 已串联: Config → Channel(cli/web/telegram) → Core(runner/loop) → Session(持久化) → Tools → Provider
✅ 已串联: Intelligence (ContextBuilder + Memory + Skills + Dream)
✅ 已串联: Resilience (RetryOnion + DeliveryQueue + CheckpointManager)
✅ 已串联: Orchestration (HeartbeatService + CronScheduler + SubagentManager)
```

## 依赖关系

```
Phase 1: Intelligence (无外部依赖，影响最大)
Phase 2: Session 持久化 (Intelligence 需要读 MEMORY.md，Session 需要落盘)
Phase 3: Resilience (依赖 Provider 和 Session)
Phase 4: Gateway (依赖 Channel + Session)
Phase 5: Orchestration (依赖全部下层)
```

---

## Phase 1: Intelligence 层接入 ✅

**目标**：ContextBuilder 替代 build_system_prompt，Memory/Skills/Dream 生效

### 1.1 替换 system prompt 构建
- `cli/dragon.py`: `build_system_prompt()` → `ContextBuilder.build_system_prompt()`
- ContextBuilder 自动读取 IDENTITY.md / SOUL.md / TOOLS.md / MEMORY.md / SKILL.md
- `web/app.py` 同步替换

### 1.2 接入 SkillsLoader
- `cli/dragon.py`: 启动时扫描 `workspace/skills/` 目录
- 将 discovered skills 注入 ContextBuilder 第 4 层

### 1.3 接入 MemoryStore
- `cli/dragon.py`: 启动时加载 MemoryStore
- ContextBuilder 第 5 层自动读取 MEMORY.md

### 1.4 添加 memory_write 内置工具
- 新建 `tools/builtin/memory_write.py`
- 让 LLM 可以主动写入记忆：`memory_write(name, content, type)`
- 注册到 ToolRegistry

### 1.5 接入 Dream 自动记忆
- `core/loop.py`: 在 `_process_message` 结束后触发 `dream.run(messages)`
- 异步执行，不阻塞响应
- 阈值：消息数 >= 4 时触发

**验证**：对话后 MEMORY.md 自动更新，下次对话 system prompt 包含记忆

---

## Phase 2: Session 持久化 + Checkpoint ✅

**目标**：会话落盘，崩溃可恢复

### 2.1 SessionManager 磁盘持久化
- `cli/dragon.py`: `SessionManager(storage_dir="sessions")`
- JSONL 文件自动追加，重启后可恢复

### 2.2 CheckpointManager 接入
- `core/loop.py`: checkpoint_callback 中调用 `CheckpointManager.save_checkpoint()`
- 启动时扫描 interrupted sessions，提示用户恢复

### 2.3 crash recovery 流程
- `cmd_agent()` 启动时：`CheckpointManager.recover_all()`
- 发现 interrupted session → 提示用户选择恢复或放弃

**验证**：对话中途 kill 进程，重启后可恢复到上次工具执行点

---

## Phase 3: Resilience 层接入 ✅

**目标**：3 层重试洋葱 + 写前投递队列

### 3.1 RetryOnion 包裹 Provider
- `core/loop.py`: 创建 provider 时用 RetryOnion 包裹
- Layer 1: 工具自纠正（tool error → 喂回 LLM 重试）
- Layer 2: 紧急压缩（token overflow → compact 后重试）
- Layer 3: 密钥轮转 + 退避（rate limit → rotate key + backoff）

### 3.2 DeliveryQueue 包裹 Channel.send
- `core/loop.py`: `channel.send()` 前写入 DeliveryQueue
- 投递成功 → 确认；失败 → 持久化到磁盘，下次启动重试

### 3.3 Provider 配置支持多 key
- `config/schema.py`: `ProviderConfig.api_keys: list[str]` (可选)
- RetryOnion 的 key rotation 使用 key 列表

**验证**：模拟 API rate limit，自动重试并恢复

---

## Phase 4: Gateway 层接入 ✅

**目标**：MessageBus 统一消息入口，Router 支持多 agent 路由

### 4.1 MessageBus 替换直接 channel 调用
- `core/loop.py`: `run()` 从 `bus.consume_inbound()` 消费消息
- Channel 的 `receive()` 改为 `bus.publish_inbound(msg)`
- `channel.send()` 改为 `bus.publish_outbound(msg)`

### 4.2 GatewayRouter 路由
- `core/loop.py`: `_dispatch()` 前调用 `router.resolve(msg)` 获取 agent config
- 支持不同消息走不同 agent（不同 system prompt / tools / model）

### 4.3 bindings.yaml 配置
- `workspace/bindings.yaml`: 5 级路由规则
- peer > guild > account > channel > default

### 4.4 多通道接入 (telegram / feishu / wechat)
- `cli/dragon.py`: 新增 `dragon telegram` / `dragon feishu` / `dragon wechat` 命令
- 每个命令创建对应 Channel，接入 MessageBus

**验证**：telegram 和 cli 可同时对话，路由到不同 agent

---

## Phase 5: Orchestration 层接入 ✅

**目标**：优先级队列、心跳、定时任务、子 agent

### 5.1 LaneQueue 替换简单队列
- `core/loop.py`: MessageBus 的 inbound 改用 LaneQueue
- lanes: main (用户消息) > cron (定时) > heartbeat (心跳)
- 优先消费 main lane

### 5.2 HeartbeatService 后台运行
- `core/loop.py`: 启动 heartbeat 后台 task
- 定时检查 session 状态，触发 idle compaction

### 5.3 CronScheduler 后台运行
- `core/loop.py`: 启动 cron 后台 task
- 支持用户配置定时任务（如每日总结、定时提醒）

### 5.4 SubagentManager 作为工具
- 新建 `tools/builtin/subagent_spawn.py`
- LLM 可以调用 `subagent_spawn(task, context)` 创建并行子任务
- SubagentManager 管理并发限制

### 5.5 AgentHook 集成
- 创建 CompositeHook：logging + streaming + progress
- 注入到 AgentLoop，统一生命周期管理

**验证**：heartbeat 自动触发，cron 定时执行，subagent 并行处理

---

## 实施顺序

```
Phase 1 (Intelligence)  ← 当前最优先，影响用户体验最大
  ↓
Phase 2 (Session 持久化) ← Phase 1 的 Dream 需要 session 数据
  ↓
Phase 3 (Resilience)    ← 依赖 Provider 和 Session
  ↓
Phase 4 (Gateway)       ← 依赖 Channel + Session
  ↓
Phase 5 (Orchestration) ← 依赖全部下层
```

每个 Phase 完成后：
1. 运行全量测试 `py -m pytest tests/`
2. 手动验证端到端流程
3. 更新此文档标记完成状态
