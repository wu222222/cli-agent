# Safe-CLI-Agent 技术架构方案

## 1. 系统概述 (System Overview)

本系统是一个具备 **自我推理 (Reasoning)** 与 **工具调用 (Tool Use)** 能力的命令行助手。其核心特征是通过 Docker 容器实现执行环境与宿主机的物理隔离，确保 AI 在执行系统级指令时的绝对安全性。

## 2. 核心架构组件 (Core Components)

### A. 推理引擎 (Reasoning Engine)
- **模型需求**：支持 Function Calling 的 LLM (如 千问,前期暂时只考虑国产模型)。
- **逻辑框架**：采用 ReAct (Reason/Act) 循环。
- **上下文管理**：维护一个动态的对话内存，记录用户的指令、Agent 的思考过程、工具调用参数以及沙盒返回的执行结果。
- **多Agent架构**：实现了三种类型的Agent：
  - **WorkerAgent**：负责执行实际的任务，如执行命令、查询知识库等。
  - **JudgeAgent**：负责评审 Worker 的任务完成质量，确保结果的准确性和可靠性。
  - **CuratorAgent**：负责管理知识库，整理和维护知识内容。

### B. 状态管理系统 (State Management)
- **状态机**：每个 Agent 都有自己的状态机，管理不同的执行状态。
- **状态流转**：实现了完整的状态流转逻辑，包括：
  - **IdleState**：空闲状态
  - **ThinkingState**：思考状态，调用 LLM 进行推理
  - **WaitingConfirmationState**：等待用户确认状态，确保安全执行
  - **ExecutingState**：执行状态，调用工具执行具体操作
  - **CompletedState**：完成状态
  - **ErrorState**：错误状态

### C. 插件容器系统 (Plugin Container System)
- **架构**：移除默认沙盒容器，改为插件化容器管理。用户通过工具设置页面按需启动/停止容器。
- **三层工具架构**：
  - **LocalTool**：本地函数调用（如 call_judge），在进程内执行。
  - **ExecContainerPlugin**：Docker 容器内执行命令（如 mylab、alpine_shell），通过 `docker exec` 运行。
  - **NetworkContainerPlugin**：网络服务调用（预留），通过 HTTP API 调用外部服务。
- **生命周期管理**：
  - 容器默认不自动启动，用户在工具设置页面手动启动。
  - 保存工具配置时自动启动已勾选的 exec 容器。
  - 支持挂载目录配置（mount_dirs），如 alpine 默认挂载 `./workspace:/workspace`。
- **权限限制**：容器默认禁用 --privileged 模式，限制 CPU 与内存配额，且使用 --network none 隔离。

### D. 人机确认拦截层 (HITL - Human-in-the-loop)
- 作为"物理防火墙"，在 LLM 发出工具执行请求与实际调用 Docker API 之间建立拦截机制。
- **按工具配置**：每个 exec 工具独立配置 `requires_confirmation`（在 plugins.yaml 中设置）。
- **确认对话框**：弹出 ConfirmDialog 组件，展示 Agent 的思考过程（thought）和待执行命令（command）。
- **拒绝机制**：用户可点"拒绝"终止命令，后端通过 `/agent/chat/reject` 端点清理挂起的 Agent。

### E. 工具管理系统 (Tool Management)
- **工具注册**：支持 YAML 配置文件（config/plugins.yaml）动态加载插件，也支持代码中注册 LocalTool。
- **自描述格式化**：每个工具实现 `format_start()` 和 `format_result()` 方法，SSE 事件自动格式化展示。
- **参数验证**：使用 Pydantic 模型进行参数验证，确保工具调用的正确性。
- **ActionType 路由**：三种 ActionType（EXECUTE_COMMAND、LOCAL_CALL、STOP）用于状态机路由，具体工具名（mylab、call_judge 等）通过 `tool_name` 字段指定。
- **内置工具**：
  - **call_judge**：调用 JudgeAgent 进行结果评审（LocalTool，绑定 LOCAL_CALL）。
- **插件工具**（通过 plugins.yaml 配置）：
  - **mylab**：自定义实验环境容器。
  - **alpine_shell**：Alpine Linux 轻量级 shell。
  - **grep_knowledge**：知识库查询容器。
  - **search**：SearXNG 搜索引擎容器。

## 3. 工作流逻辑 (Workflow)

1. **用户输入 (Input)**：用户在聊天界面输入自然语言需求（例如："找出当前目录下最大的 5 个文件"）。
2. **推理 (Think)**：WorkerAgent 调用 LLM 分析需求，决定调用哪个工具（如 mylab），生成命令参数。Thought 通过 SSE 实时推送到前端显示为 💭 气泡。
3. **拦截 (Intercept)**：如果工具的 `requires_confirmation` 为 true，系统弹出确认对话框，展示 Agent 思考过程和待执行命令。
4. **执行 (Act)**：用户确认后，指令被发送至对应容器执行。若用户拒绝，后端清理挂起的 Agent。
5. **反馈 (Observe)**：捕获容器的 stdout/stderr，通过 SSE `tool_result` 事件推送到前端，显示命令和输出。
6. **评审 (Review)**：WorkerAgent 调用 call_judge 工具，JudgeAgent 对结果进行评审，其思考过程附带在评审结果中返回。
7. **总结 (Output)**：WorkerAgent 根据执行结果和评审意见生成最终回答，通过 SSE `final` 事件推送。

### SSE 事件类型
- `thought`：Agent 思考过程（含 agent 名称和 thought 内容）
- `tool_start`：工具开始执行（含 tool_name、tool_type、params）
- `tool_result`：工具执行结果（含 tool_name、command、formatted content）
- `confirm`：等待用户确认（含 thought、command、agent）
- `final`：任务完成（含最终回答）
- `error`：执行错误

## 4. 技术栈 (Technical Stack)

| 模块 | 实现 |
|------|------|
| 后端语言 | Python 3.10+ |
| 前端语言 | TypeScript |
| 前端框架 | Vue 3 |
| UI 组件库 | Element Plus |
| 构建工具 | Vite |
| 后端框架 | FastAPI |
| LLM SDK | 自定义 LLMClient (支持国产模型) |
| Docker 通讯 | docker-py (Docker SDK for Python) |
| 类型检查 | Pydantic V2 |
| 日志系统 | 自定义 logger |
| 状态管理 | 自定义状态机 |
| 上下文管理 | 自定义 ContextManager |

## 5. 安全策略 (Security Policy)

- **路径隔离**：仅允许挂载特定的 /workspace 目录，禁止访问宿主机根目录。
- **网络隔离**：默认启动容器时添加 --network none，防止 Agent 意外泄露 API Keys 或建立反弹 Shell。
- **超时控制**：为每个指令设置 timeout（如 30 秒），防止逻辑陷阱或死循环耗尽资源。
- **指令脱敏**：在反馈给 LLM 之前，自动过滤执行结果中可能包含的敏感环境变量。
- **人机确认**：所有命令执行前都需要用户显式确认，确保用户对执行的操作有完全的控制权。

## 6. 扩展方向 (Future Scaling)

- **多容器协同**：为不同的任务启动预装不同环境的容器镜像（已通过 plugins.yaml 实现）。
- **文件系统快照**：支持在执行危险操作前对容器进行快照，以便随时回滚。
- **知识库增强**：扩展 CuratorAgent 的能力，支持更复杂的知识管理和检索功能。
- **多Agent协作**：实现更复杂的多Agent协作模式，解决更复杂的任务。
- **实时流式推送**：已通过 SSE 实现 thought/tool_result/confirm/final 事件的实时推送。
- **用户权限管理**：添加用户认证和权限控制功能。
- **NetworkContainerPlugin**：完善网络服务调用工具类型，支持 HTTP API 插件。

## 7. 实现细节 (Implementation Details)

### 核心类结构

- **BaseAgent**：所有 Agent 的基类，定义了通用接口（含 `last_thought` 存储思考过程）。
- **WorkerAgent**：工作代理，负责执行实际的任务，支持 `tool_names` 配置可用工具列表。
- **JudgeAgent**：评审代理，负责检查 Worker 的任务完成质量，输出 PASS/FAIL 及原因。
- **CuratorAgent**：知识整理代理，负责管理知识库。
- **StreamingWorkerAgent / StreamingCuratorAgent**：支持 SSE 实时回调的 Agent 子类，发送 thought/tool_start/tool_result 事件。
- **BaseStateMachine**：状态机基类，管理 Agent 的状态流转。
- **ContextManager**：上下文管理器，管理消息和状态追踪。
- **PromptManager**：提示词管理器，动态生成不同角色的系统提示词（含工具文档和 Schema）。
- **Tool / LocalTool / ExecContainerPlugin**：三层工具体系，支持自描述格式化和参数验证。
- **ToolRegistry**：工具注册表，支持 YAML 加载、按名称查找（大小写不敏感）、ActionType 解析。

### 状态流转

1. **WorkerAgent**：Idle → Thinking → [WaitingConfirmation →] Executing → Thinking → ... → Completed
2. **JudgeAgent**：Idle → Thinking → Completed
3. **CuratorAgent**：Idle → Thinking → [WaitingConfirmation →] Executing → Thinking → ... → Completed

### 工具执行流程

1. WorkerAgent 调用 LLM 生成工具调用请求（type + tool_name + parameters）
2. 状态机根据 ActionType 路由：EXECUTE_COMMAND → 查找 exec 工具，LOCAL_CALL → 查找 local 工具
3. StreamingAgent 在执行前发送 `thought` SSE 事件（展示 Agent 思考过程）
4. 系统检查工具的 `requires_confirmation`，如需确认则进入 WaitingConfirmation 状态
5. 用户确认后，调用工具的 `run()` 方法执行
6. 工具执行结果通过 `tool_result` SSE 事件推送（含 command 参数）
7. WorkerAgent 根据执行结果继续推理或调用 call_judge 评审

### 安全机制

1. **Docker 隔离**：所有命令在 Docker 容器中执行，与宿主机隔离。
2. **用户确认**：所有命令执行前需要用户显式确认。
3. **参数验证**：使用 Pydantic 模型对工具参数进行验证，确保参数的正确性。
4. **错误处理**：完善的错误处理机制，确保系统的稳定性。

## 8. 部署与运行

### 前置条件

- Python 3.10+
- Docker 环境
- 配置好的 LLM API 密钥
- Node.js 18+ (前端开发)
- npm 或 yarn (前端包管理)

### 后端运行步骤

1. 安装依赖：`pip install -r requirements.txt`
2. 配置环境变量：`cp .env.example .env` 并填写相关配置
3. 启动 API 服务：`python src/api/main.py`
4. 服务默认运行在 http://localhost:8000

### 前端运行步骤

1. 进入前端目录：`cd frontend`
2. 安装依赖：`npm install`
3. 启动开发服务器：`npm run dev`
4. 前端默认运行在 http://localhost:5173

### 生产部署

1. 前端构建：`cd frontend && npm run build`
2. 后端使用 uvicorn 启动：`uvicorn src.api.main:app --host 0.0.0.0 --port 8000`
3. 使用 Nginx 或 Caddy 代理前端静态文件和后端 API

## 9. 代码结构

```
├── src/
│   ├── agent/                # Agent 核心逻辑
│   │   ├── agent.py          # Worker/Judge/Curator Agent 实现
│   │   ├── base.py           # Agent 基类（含 last_thought）
│   │   ├── context.py        # 上下文管理器
│   │   ├── prompt.py         # Prompt 管理器（动态 Schema 生成）
│   │   ├── tools.py          # 工具体系（Tool/LocalTool/ExecContainerPlugin/ToolRegistry）
│   │   ├── statemachine.py   # 状态机实现（Worker/Judge/Curator）
│   │   └── types.py          # 类型定义（ActionType/AgentState/AgentResponse 等）
│   ├── api/                  # FastAPI 后端 API
│   │   ├── main.py           # App 入口
│   │   ├── models.py         # Pydantic 请求/响应模型
│   │   ├── routes.py         # 路由处理器（chat/plugins/agent/tools）
│   │   ├── services.py       # 业务逻辑、组件初始化
│   │   └── streaming.py      # SSE 流式 Agent（StreamingWorkerAgent/StreamingCuratorAgent）
│   ├── executor/             # Docker 执行器
│   │   ├── docker.py         # DockerExecutor + PluginContainerManager
│   │   └── client.py         # DockerClientFactory
│   ├── llm/                  # LLM 客户端
│   │   └── client.py         # 异步 LLMClient
│   └── logger/               # 日志系统
├── config/
│   └── plugins.yaml          # 插件容器配置（mylab/alpine_shell/grep_knowledge/search）
├── frontend/                 # Vue 3 前端应用
│   ├── src/
│   │   ├── views/            # 页面视图
│   │   │   ├── ChatView.vue          # 聊天页面（含确认对话框）
│   │   │   ├── ToolsView.vue         # 工具设置页面（勾选工具、启停容器）
│   │   │   ├── HistoryView.vue       # 历史记录页面
│   │   │   └── SettingsView.vue      # 设置页面
│   │   ├── components/       # 组件
│   │   │   ├── MessageBubble.vue     # 消息气泡（text/thought/tool_result）
│   │   │   ├── ConfirmDialog.vue     # 命令确认对话框
│   │   │   └── ToolCard.vue          # 工具卡片组件
│   │   ├── composables/      # 组合式函数
│   │   │   └── useSSE.ts             # SSE 事件处理（简洁模式）
│   │   ├── stores/           # 状态管理
│   │   │   ├── chat.ts               # 聊天状态（messages/pending）
│   │   │   └── plugin.ts             # 插件状态
│   │   ├── api/              # API 客户端
│   │   │   ├── agent.ts              # Agent API（chat/stream/curator）
│   │   │   └── config.ts             # 插件 API（plugins/start/stop）
│   │   └── types/            # TypeScript 类型定义
│   └── package.json
├── knowledge_base/           # 知识库目录
├── workspace/                # 工作目录（alpine_shell 默认挂载）
├── .env.example              # 环境变量示例
└── environment.yml           # Conda 环境配置
```

## 10. 总结

Safe-CLI-Agent 是一个安全、可靠的命令行助手，通过 Docker 容器隔离和人机确认机制，确保 AI 在执行系统级指令时的安全性。系统采用多Agent架构，实现了任务执行、结果评审和知识管理等功能，为用户提供了一个智能、安全的命令行工具。