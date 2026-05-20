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
- **权限配置**：每个插件可独立配置 `network_mode`（`"none"` 安全隔离 / `"bridge"` 联网）、`privileged`（nmap 等需要 raw socket）、`timeout_seconds`（慢工具设更大值）。默认安全。

### D. 人机确认拦截层 (HITL - Human-in-the-loop)
- 作为"物理防火墙"，在 LLM 发出工具执行请求与实际调用 Docker API 之间建立拦截机制。
- **按工具配置**：每个 exec 工具独立配置 `requires_confirmation`（在 plugins.yaml 中设置）。
- **确认对话框**：弹出 ConfirmDialog 组件，展示 Agent 的思考过程（thought）和待执行命令（command）。
- **拒绝机制**：用户可点"拒绝"终止命令，后端通过 `/agent/chat/reject` 端点清理挂起的 Agent。

### E. 工具管理系统 (Tool Management)
- **工具注册**：支持 YAML 配置文件（config/plugins.yaml）动态加载插件，也支持代码中注册 LocalTool。
- **自描述格式化**：每个工具实现 `format_start()` 和 `format_result()` 方法，SSE 事件自动格式化展示。
- **参数验证**：使用 Pydantic 模型进行参数验证，确保工具调用的正确性。
- **ActionType 路由**：三种 ActionType（EXECUTE_COMMAND、LOCAL_CALL、STOP）用于状态机路由，具体工具名通过 `tool_name` 字段指定。
- **AgentRegistry**：Agent 类型注册表，新增 Agent 类型只需 `register_agent(AgentConfig(...))`。当前注册：worker / judge / curator。
- **插件工具**（通过 plugins.yaml 配置，共 9 个）：
  - exec: `alpine_shell`、`mylab`、`grep_knowledge`、`search`、`cpp_python_dev`、`kali`
  - command: `curator`（`/summary` 触发）
  - local: `call_judge`（评审）、`context_compress`（上下文压缩）
  - compose: `ctf_lab`（含 ctf_shell + ctf_status + aux 靶机）

## 3. 工作流逻辑 (Workflow)

1. **用户输入 (Input)**：用户在聊天界面输入自然语言需求（例如："找出当前目录下最大的 5 个文件"）。
2. **推理 (Think)**：WorkerAgent 调用 LLM 分析需求，决定调用哪个工具（如 mylab），生成命令参数。Thought 通过 SSE 实时推送到前端显示为 💭 气泡。
3. **拦截 (Intercept)**：如果工具的 `requires_confirmation` 为 true，系统弹出确认对话框，展示 Agent 思考过程和待执行命令。
4. **执行 (Act)**：用户确认后，指令被发送至对应容器执行。若用户拒绝，后端清理挂起的 Agent。
5. **反馈 (Observe)**：捕获容器的 stdout/stderr，通过 SSE `tool_result` 事件推送到前端，显示命令和输出。长输出自动折叠（>10 行），JSON 自动格式化。
6. **评审 (Review)**：WorkerAgent 调用 call_judge 工具，JudgeAgent 对结果进行评审。
7. **压缩 (Compress)**：每 6 步自动触发 `context_compress`，将过期消息压缩为摘要，节省 token。
8. **总结 (Output)**：WorkerAgent 根据执行结果生成最终回答，通过 SSE `final` 事件推送。

### SSE 事件类型
- `thought`：Agent 思考过程
- `tool_start`：工具开始执行（含 agent、tool_name、tool_type）
- `tool_result`：工具执行结果（含 tool_name、command、formatted content）
- `confirm`：等待用户确认（含 thought、command、tool_name、agent）
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
- **网络隔离**：默认 `network_mode: "none"`，需要联网的插件（如 kali）显式设 `"bridge"`。
- **超时控制**：默认 30 秒，可通过 `timeout_seconds` 按插件配置。docker exec 内层 + streaming 外层双重超时。
- **权限控制**：默认 `privileged: false`，需要 raw socket 的工具（如 nmap）显式开启。
- **上下文衰减**：消息按年龄自动截断/摘要/遗忘，user 和 error 消息永不丢失。每 6 步自动压缩。
- **指令脱敏**：在反馈给 LLM 之前，自动过滤执行结果中可能包含的敏感环境变量。
- **人机确认**：所有命令执行前都需要用户显式确认，确保用户对执行的操作有完全的控制权。

## 6. 扩展方向 (Future Scaling)

- **多容器协同**：已通过 plugins.yaml compose 类型实现。
- **Hook 系统**：Tool 级 `on_register`/`on_unregister` 钩子，local 插件零代码绑定。
- **NetworkContainerPlugin**：完善网络服务调用工具类型。
- **容器引用计数**：共享容器（如 kb_container）的生命周期管理。
- **YAML 热加载**：修改配置后无需重启服务。
- **Plugin 市场**：社区贡献的插件 Dockerfile + YAML 模板库。

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
│   │   ├── agent.py          # Worker/Judge/Curator Agent + AGENT_POLICIES
│   │   ├── base.py           # Agent 基类（含 step/auto_compress）
│   │   ├── context.py        # 上下文管理器（含记忆衰减/智能摘要）
│   │   ├── prompt.py         # Prompt 管理器（动态条件化生成）
│   │   ├── tools.py          # 工具体系（5 种类型 + ComposePlugin + ToolRegistry）
│   │   ├── statemachine.py   # 状态机实现
│   │   ├── types.py          # 类型定义（含 ContextPolicy）
│   │   └── registry.py       # Agent 类型注册表
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
│   ├── plugins.yaml          # 插件配置 v2（9 个插件）
│   └── context_policy.yaml   # Agent 上下文策略（worker/judge/curator）
├── frontend/                 # Vue 3 前端应用
│   ├── src/
│   │   ├── views/            # 页面视图
│   │   │   ├── ChatView.vue          # 聊天页（命令提示/确认/上下文面板/清空）
│   │   │   └── ToolsView.vue         # 工具设置页（插件启停/compose管理）
│   │   ├── composables/      # 组合式函数
│   │   │   └── useSSE.ts             # SSE 事件处理（thought/tool_result/confirm/final）
│   │   ├── stores/           # 状态管理
│   │   │   ├── chat.ts               # 聊天状态（messages/pending）
│   │   │   └── plugin.ts             # 插件状态
│   │   ├── api/              # API 客户端
│   │   │   ├── agent.ts              # Agent API（chat/stream/curator）
│   │   │   └── config.ts             # 插件 API（plugins/start/stop）
│   │   └── types/            # TypeScript 类型定义
│   └── package.json
├── knowledge_base/           # 知识库目录
├── workspace/                # 工作目录（默认挂载）
├── labs/                     # 实验室环境
│   ├── ctf_lab/              # CTF 靶场（docker-compose）
│   └── kali/                 # Kali 渗透测试（Dockerfile）
├── code_task_prompt/         # 任务文档（task1-18.md）
├── .env.example              # 环境变量示例
└── environment.yml           # Conda 环境配置
```

## 10. 总结

Safe-CLI-Agent 是一个安全、可靠的 CLI 助手。核心设计理念：
- **配置驱动**：新增插件只需编辑 `plugins.yaml`，不改代码
- **Docker 隔离**：可配网络/特权/超时，默认安全
- **多 Agent 协作**：Worker 执行 + Judge 评审 + Curator 整理
- **记忆衰减**：上下文自动截断/摘要/遗忘，长任务不爆 token