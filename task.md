任务:请优化/src/api/main.py中的代码

要求:
1.尽可能理解项目中的相关代码再执行操作
2.可能涉及多个文件的代码
3.将你的结果描述写在该task.md文件中

描述:
1./src/agent/statemachine.py中的代码描述了Agent的状态机，包括状态的定义、转换条件、状态转换函数等。
2.当前任务总目标是搭建一个前端界面，但是遇到了非阻塞交互问题，见statemachine.py中的waitingconfirmationState.
3.相关脚本/src/agent/base.py /src/agent/types.py /src/agent/agent.py

---

## 优化结果

### 问题分析

1. **`main.py` 是 mock 实现**：原 `/agent/chat` 端点返回硬编码的模拟响应，未真正驱动 Agent 运行。
2. **阻塞 vs 非阻塞**：Agent 的 `run()` 方法（`base.py:80`）是一个同步阻塞循环，在 `WAITING_CONFIRMATION` 状态时原设计通过 `input()` 阻塞等待用户输入。HTTP 请求-响应模式无法使用阻塞等待。
3. **确认流程断裂**：前端期望的流程是——第一次请求返回 `{type: "confirm", content: "命令"}`，用户点击确认后发第二次请求（`confirmed=True`）恢复执行。原代码中 `orchestrator.resume_with_action()` 方法不存在。

### 解决方案

利用 `base.py:54` 中的 `step()` 方法，将 Agent 驱动方式从"阻塞循环"改为"逐步执行"：

- **第一步**：用户发消息 → API 创建 WorkerAgent，从 THINKING 状态开始，调用 `step()` 逐步执行
- **循环执行**：每次 `step()` 推进一个状态转换（THINKING → EXECUTING → THINKING → ...）
- **遇到确认**：当 Agent 进入 `WAITING_CONFIRMATION` 状态时，暂存 Agent 实例到全局变量 `_pending_agent`，返回 `{type: "confirm"}` 给前端
- **用户确认**：前端再次请求（`confirmed=True`），API 取出暂存的 Agent，注入 `confirmed=True` 到 `WaitingConfirmationState.data`，继续调用 `step()` 恢复执行

### 修改的文件

#### 1. `/src/api/main.py` — 完整重写

主要变更：
- **延迟初始化**：Docker 连接、LLM 客户端等在首次请求时才初始化，避免启动时阻塞
- **`_run_agent_steps()` 函数**：核心调度逻辑，循环调用 `agent.step()` 驱动状态机，根据状态返回不同类型的响应
- **`/agent/chat` 端点**：
  - `confirmed=True`：从 `_pending_agent` 恢复 Agent，注入确认状态，继续执行
  - `confirmed=False`：创建新 Agent，从头开始执行
- **全局状态 `_pending_agent`**：暂存等待确认的 Agent 实例，保持其状态机上下文不丢失

#### 2. `/frontend/src/views/ChatView.vue` — Bug 修复

修复 `confirmCommand` 函数中的变量覆盖 bug：
```js
// 修复前：pendingCommand.value 在发送前被清空
pendingCommand.value = ''
const response = await apiSendMessage(pendingCommand.value, true) // 发送空字符串！

// 修复后：先保存再清空
const confirmedMessage = pendingCommand.value
pendingCommand.value = ''
const response = await apiSendMessage(confirmedMessage, true)
```

### 状态流转示意

```
用户发消息 "列出当前目录文件"
  │
  ▼
API: 创建 WorkerAgent → transition(THINKING)
  │
  ▼ step()
WorkerThinkingState.execute()
  → LLM 返回 {action: execute_command, command: "ls -la"}
  → return StateTransition(WAITING_CONFIRMATION, data)
  │
  ▼ step() [自动转换到 WAITING_CONFIRMATION]
WaitingConfirmationState.on_enter(data) — 存储 data
  │
  ▼ 检测到 WAITING_CONFIRMATION → 返回 {type: "confirm", content: "是否允许执行: ls -la?"}
  │
  ▼ 前端显示确认按钮，用户点击"确认执行"
  │
API: confirmed=True → 注入 data.confirmed = True → _run_agent_steps()
  │
  ▼ step()
WaitingConfirmationState.execute()
  → data.confirmed is True → return StateTransition(EXECUTING)
  │
  ▼ step() [自动转换到 EXECUTING]
ExecutingState.execute()
  → 调用 Docker 执行 "ls -la"
  → return StateTransition(THINKING, result)
  │
  ▼ step() [自动转换到 THINKING]
WorkerThinkingState.execute()
  → LLM 返回 {action: stop, answer: "当前目录包含以下文件..."}
  → return StateTransition(COMPLETED)
  │
  ▼ 检测到 COMPLETED → 返回最终结果给前端
```
