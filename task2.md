任务:请完善前端代码，要求能够跑通

要求:
1.尽可能理解项目中的相关代码再执行操作
2.可能涉及多个文件的代码
3.将你的结果描述写在该task2.md文件中
4.可以不需要太复杂的前端界面，只需要实现基本的交互功能即可。

描述:
1./src/agent/statemachine.py中的代码描述了Agent的状态机，包括状态的定义、转换条件、状态转换函数等。
2.之前的测试脚本/examples/safe_cli_agent_test.py 中包含了之前后端命令行的交互例子，你可以参考这个例子来完善前端代码。
3.相关脚本/src/agent/base.py /src/agent/types.py /src/agent/agent.py
4.前端代码/src/agent/frontend.py
5.前端与后端交互的接口在/src/agent/api.py中定义。

---

## 完成结果

### 前端架构说明

前端为 Vue 3 + TypeScript + Vite 项目，位于 `frontend/` 目录：
- `frontend/src/api/agent.ts` — API 客户端，通过 Vite proxy (`/api` → `http://localhost:8000`) 调用后端
- `frontend/src/views/ChatView.vue` — 聊天主界面
- `frontend/src/views/HistoryView.vue` — 历史记录页面
- `frontend/src/views/SettingsView.vue` — 设置页面
- `frontend/src/types/index.ts` — TypeScript 类型定义

### 修改的文件

#### 1. `frontend/src/types/index.ts` — 类型修正

`ApiResponse.type` 原定义包含 `'code'`，但后端实际只返回 `'text'` 和 `'confirm'`。修正类型定义以匹配后端 API。

#### 2. `frontend/src/views/ChatView.vue` — 确认流程完善

修改内容：
- 当 API 返回 `type: 'confirm'` 时，添加一条系统消息提示用户"Agent 需要执行以下命令，请确认"，让用户在聊天区看到反馈
- 移除 `type === 'code'` 的死代码判断（后端不返回 code 类型）
- 保留之前修复的 `confirmCommand` 变量覆盖 bug

#### 3. `frontend/src/views/HistoryView.vue` — 连接真实 API

原实现使用硬编码 mock 数据。改为：
- `onMounted` 时调用 `getHistory()` 从 `/agent/history` 获取真实数据
- "清空历史"按钮调用 `clearHistory()` 清空后端历史记录
- 移除未使用的 `loadHistory` 和 `deleteHistory` 交互（简化为只读展示）

### 前端与后端交互流程

```
用户输入 "ls -la"
    │
    ▼
前端 POST /api/agent/chat  { message: "ls -la", confirmed: false }
    │  (Vite proxy → http://localhost:8000/agent/chat)
    ▼
后端创建 WorkerAgent → 逐步执行状态机
    → THINKING → LLM 返回 execute_command
    → WAITING_CONFIRMATION → 返回 { type: "confirm", content: "是否允许执行: ls -la?" }
    │
    ▼
前端收到 type="confirm"
    → pendingCommand = "是否允许执行: ls -la?"
    → 显示确认面板（命令预览 + 确认/取消按钮）
    → 聊天区显示 "Agent 需要执行以下命令，请确认："
    │
    ▼ 用户点击"确认执行"
前端 POST /api/agent/chat  { message: "是否允许执行: ls -la?", confirmed: true }
    │
    ▼
后端取出暂存的 _pendingAgent → 注入 confirmed=True → 继续执行
    → EXECUTING → Docker 执行命令
    → THINKING → LLM 总结结果
    → COMPLETED → 返回 { type: "text", content: "文件列表..." }
    │
    ▼
前端收到 type="text" → 显示最终结果到聊天区
```

### 第二轮修复（调试运行时问题）

#### 1. `frontend/vite.config.ts` — Proxy 路径重写

Vite proxy 原配置将 `/api/health` 原样转发到 `http://localhost:8000/api/health`，但后端路由是 `/health`。添加 `rewrite` 规则去掉 `/api` 前缀。

#### 2. `src/agent/statemachine.py` — WaitingConfirmationState 确认逻辑修复

**根本 Bug**：`execute()` 方法检查的是传入的 `data` 参数（`step()` 调用时不传参数，永远为 `None`），而非 `on_enter()` 中存储的 `self.data`。导致 `incoming_confirmed` 永远是 `None`，状态永远卡在 `waiting_confirmation`。

修复：改为检查 `self.data.confirmed`（由 API 层在调用 `step()` 前设置）。

#### 3. `src/api/main.py` — Judge Handler + 步骤追踪 + 超时保护

- 注入 `call_judge` handler（参考 `orchestrator._setup_worker_handlers`），解决 "工具未绑定 handler" 错误
- 添加 `_collect_steps()` 函数，从 ContextManager 消息历史中提取步骤信息（thinking、tool_result）
- API 响应新增 `agent` 和 `steps` 字段，前端可据此展示完整的推理过程
- 添加 `asyncio.wait_for` 120 秒超时保护，防止 LLM 调用卡死

#### 4. `frontend/src/views/ChatView.vue` — 展示步骤详情和 Agent 区分

- 新增 `steps` 渲染区域：左侧彩色边框 + 标签（thinking/tool_result）+ 内容
- 不同 Agent 通过 `step.agent` 字段区分（WorkerAgent / JudgeAgent）
- 工具执行结果用 `<pre>` 标签展示，限制最大高度 200px 可滚动

#### 5. `frontend/src/types/index.ts` — 新增 StepInfo 类型

### 第三轮修复（SSE 流式输出 + Agent 名称修正）

#### 1. `src/api/main.py` — StreamingWorkerAgent + SSE 端点

**问题**：所有消息在 Agent 执行完成后一次性返回，前端无法实时看到工具执行过程。

解决方案：
- 新增 `StreamingWorkerAgent` 子类，覆写 `_execute_action`，每次工具执行完成后触发 `on_tool_result` 回调
- 使用 `asyncio.Queue` 为每个请求维护事件队列
- `POST /agent/chat` 立即返回 `request_id`，Agent 在后台通过 `asyncio.create_task` 异步运行
- 新增 `GET /agent/chat/stream?request_id=...` SSE 端点，前端通过 EventSource 实时接收事件
- 新增 `POST /agent/chat/confirm` 端点，用于确认后继续执行（创建新的 request_id 和 SSE 流）

事件类型：
- `tool_result` — 工具执行完成，实时推送（包含正确的 `agent` 名称）
- `confirm` — Agent 等待用户确认
- `final` — 任务完成或出错

#### 2. `frontend/src/api/agent.ts` — EventSource 客户端

新增 `connectStream(requestId, handlers)` 函数：
- 创建 EventSource 连接到 `/api/agent/chat/stream?request_id=...`
- 监听 `tool_result`、`confirm`、`final`、`error` 四种事件
- 每个事件触发对应的回调函数

#### 3. `frontend/src/views/ChatView.vue` — 实时流式显示

- `sendMessage()` 调用 API 获取 `request_id` 后，立即调用 `listenStream()` 建立 SSE 连接
- `onToolResult` 回调：每次工具执行完成，立即添加一条新消息到聊天区（type='code'）
- `onConfirm` 回调：显示确认面板，停止 thinking 动画
- `onFinal` 回调：显示最终结果，关闭 SSE 连接
- `confirmCommand()` 调用 `/agent/chat/confirm` 获取新的 `request_id`，重新建立 SSE 连接

#### 4. `frontend/src/api/agent.ts` — 类型修复

修复 `addEventListener('error', ...)` 中 `Event` 类型没有 `data` 属性的 TypeScript 错误，通过类型断言 `as MessageEvent` 解决。

### 第四轮修复（确认后 tool_result 丢失 + 多行输出截断）

#### 1. `src/api/main.py` — 确认端点回调更新

**根本 Bug**：`POST /agent/chat` 创建 Agent 时，`on_tool_result` 回调闭包捕获了原始 `request_id`。用户确认后，`POST /agent/chat/confirm` 创建新的 `request_id`，但 Agent 的回调仍指向旧队列，导致 `tool_result` 事件发往无人监听的旧队列。

修复：在 `confirm_command` 端点中，为复用的 Agent 重新绑定 `on_tool_result` 回调，使用新的 `request_id`。

#### 2. `src/api/main.py` — `_format_tool_result` 多行输出修复

**Bug**：Docker 命令的 stdout 是多行的，但 `_format_tool_result` 逐行匹配 `STDOUT:` 前缀，导致只有 stdout 的第一行被保留，后续行全部丢失。

修复：使用 `in_stdout` 标志跟踪多行 stdout 区域，将 stdout 的所有行都包含在输出中。

#### 3. `src/api/main.py` — `call_judge` 结果展示

原来 `call_judge` 的返回值被 `_format_tool_result` 过滤为空字符串，前端不显示。改为直接返回原始内容，让 JudgeAgent 的评审结果也能在前端展示。

#### 4. `src/api/main.py` — JudgeAgent 名称修正

**Bug**：`StreamingWorkerAgent._execute_action` 中 `self.name` 始终为 "WorkerAgent"，即使调用的是 `call_judge`（由 JudgeAgent 执行），前端也显示为 "WorkerAgent"。

修复：检测 `action_type == ActionType.CALL_JUDGE` 时，使用 "JudgeAgent" 作为 agent 名称。

#### 5. `src/api/main.py` — `call_judge` 结果格式化

原始返回值格式为 Python repr（`observation='...' action_type='...'`），可读性差。使用正则提取 `observation` 和 `action_type`，格式化为更易读的形式。

### 第五轮修复（确认面板显示思考过程）

#### `src/agent/statemachine.py` — 确认提示添加思考过程

原来的确认提示仅为 `是否允许执行: {command}?`，用户不知道 Agent 为什么想执行这个命令。

修改为包含思考过程的格式：
```
[思考] {thought}

[命令] {command}

是否允许执行以上命令?
```

这样用户可以在确认面板中看到 Agent 的推理过程，做出更明智的决定。

### 关于上下文持久化

`_context_manager` 是全局共享的，消息在请求之间持久化。Agent 的 `_think()` 方法通过 `get_agent_messages()` 获取所有可见消息，包括之前对话的内容。LLM 能看到之前的上下文，但不一定在每次回复中显式引用。

### 第六轮修复（执行动作详情展示 + 确认端点回调补全）

#### 1. `src/api/main.py` — `_format_action_start` 增强

原来 `call_judge` 只显示"正在调用 JudgeAgent 进行评审..."，不包含 `final_answer` 和 `evidence_summary`。

修改后显示：
```
正在调用 JudgeAgent 进行评审...
待评审答案: {final_answer}
证据摘要: {evidence_summary}
```

#### 2. `src/api/main.py` — 确认端点 `on_tool_start` 回调补全

**Bug**：`confirm_command` 端点只更新了 `on_tool_result` 回调，没有更新 `on_tool_start`。导致确认后执行的动作（如 `call_judge`）的 `tool_start` 事件仍然发往旧队列。

修复：在确认端点中同时更新 `on_tool_start` 和 `on_tool_result` 回调。

### 第七轮功能（CuratorAgent + /summary 命令）

#### 1. `src/api/main.py` — CuratorAgent API 端点

新增 `StreamingCuratorAgent` 子类（继承 `CuratorAgent`），覆写 `_execute_action` 添加 `on_tool_start` 和 `on_tool_result` 回调，实现 SSE 流式推送。

新增 `POST /agent/curator` 端点：
- 接收 `{ "task": "..." }` 请求
- 创建 `StreamingCuratorAgent`，调用 `_prepare_context(task)` 设置任务
- 使用 `asyncio.create_task` 异步运行，复用 `_run_agent_with_streaming` 驱动状态机
- CuratorAgent 使用 `get_all_messages()` 获取完整上下文（包括其他 Agent 的消息）

#### 2. `frontend/src/api/agent.ts` — Curator API 客户端

新增 `sendCuratorTask(task: string)` 函数，POST 到 `/agent/curator`，返回 `{ request_id }`。

#### 3. `frontend/src/views/ChatView.vue` — 命令路由

在 `sendMessage()` 中检测输入是否以 `/` 开头的命令：
- 支持的命令：`/summary`, `/curator`, `/总结`, `/整理`
- 命令后的文字作为 CuratorAgent 的任务描述
- 如果没有附加文字，使用默认任务："分析之前的对话历史，提取关键信息并整理到知识库中。"
- CuratorAgent 消息通过 SSE 流式推送，使用 `agent: 'CuratorAgent'` 标识

### 验证结果

- TypeScript 类型检查通过（`vue-tsc --noEmit` 无错误）
- 生产构建成功（`vite build` 6.2s 完成）

### 启动方式

```bash
# 1. 启动后端（端口 8000）
cd F:\PY\cli-agent
python -m src.api.main

# 2. 启动前端（端口 5173，自动代理 /api 到后端）
cd F:\PY\cli-agent\frontend
npm run dev
```
