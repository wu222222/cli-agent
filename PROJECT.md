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

### C. Docker 执行沙盒 (Docker Executor)
- **隔离机制**：所有的 Shell 指令均在独立的 Docker 容器中运行。
- **生命周期管理**：
  - 启动时创建临时容器（如基于 alpine 或 python:slim）。
  - 运行时通过 docker exec 传递指令。
  - 退出时强制销毁容器，确保"无迹寻踪"。
- **权限限制**：容器默认禁用 --privileged 模式，限制 CPU 与内存配额，且使用非 root 用户执行。

### D. 人机确认拦截层 (HITL - Human-in-the-loop)
- 作为"物理防火墙"，在 LLM 发出工具执行请求与实际调用 Docker API 之间建立拦截机制。
- 展示生成的代码/指令，等待用户显式授权。
- 实现了交互式的确认界面，确保用户对执行的命令有完全的控制权。

### E. 工具管理系统 (Tool Management)
- **工具注册**：支持动态注册和管理工具。
- **参数验证**：使用 Pydantic 模型进行参数验证，确保工具调用的正确性。
- **异步执行**：支持同步和异步工具执行。
- **默认工具**：
  - **EXECUTE_COMMAND**：在 Docker 容器中执行 Shell 命令。
  - **CALL_JUDGE**：调用 JudgeAgent 进行结果评审。
  - **QUERY_KNOWLEDGE**：查询知识库（可选）。
  - **REVIEW**：JudgeAgent 专用的评审工具。

## 3. 工作流逻辑 (Workflow)

1. **用户输入 (Input)**：用户在终端输入自然语言需求（例如："找出当前目录下最大的 5 个文件"）。
2. **推理 (Think)**：WorkerAgent 分析需求，决定调用 execute_command 工具，并生成对应的 Shell 脚本（如 `du -ah . | sort -rh | head -n 5`）。
3. **拦截 (Intercept)**：系统捕获到 Tool Call，解析参数并在控制台高亮显示，等待用户确认。
4. **执行 (Act)**：用户确认后，指令被发送至 Docker 容器执行。
5. **反馈 (Observe)**：捕获容器的标准输出 (stdout) 和错误输出 (stderr)，将其反馈给 LLM。
6. **评审 (Review)**：WorkerAgent 调用 JudgeAgent 对执行结果进行评审，确保结果的准确性和可靠性。
7. **总结 (Output)**：WorkerAgent 根据执行结果和评审意见生成人类可读的最终回答。

## 4. 技术栈 (Technical Stack)

| 模块 | 实现 |
|------|------|
| 语言 | Python 3.10+ |
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

- **多容器协同**：为不同的任务（如 Node.js 开发 vs. Python 数据分析）启动预装不同环境的容器镜像。
- **文件系统快照**：支持在执行危险操作前对容器进行快照，以便随时回滚。
- **知识库增强**：扩展 CuratorAgent 的能力，支持更复杂的知识管理和检索功能。
- **多Agent协作**：实现更复杂的多Agent协作模式，解决更复杂的任务。
- **Web界面**：为系统添加 Web 界面，提供更友好的用户交互体验。

## 7. 实现细节 (Implementation Details)

### 核心类结构

- **BaseAgent**：所有 Agent 的基类，定义了通用的接口和方法。
- **WorkerAgent**：工作代理，负责执行实际的任务。
- **JudgeAgent**：评审代理，负责检查 Worker 的任务完成质量。
- **CuratorAgent**：知识整理代理，负责管理知识库。
- **BaseStateMachine**：状态机基类，管理 Agent 的状态流转。
- **ContextManager**：上下文管理器，管理消息和状态追踪。
- **PromptManager**：提示词管理器，生成不同角色的系统提示词。
- **ToolRegistry**：工具注册表，管理和执行工具。

### 状态流转

1. **WorkerAgent**：Idle → Thinking → WaitingConfirmation → Executing → Thinking → CallJudge → Completed
2. **JudgeAgent**：Idle → Thinking → Completed
3. **CuratorAgent**：Idle → Thinking → Executing → Completed

### 工具执行流程

1. WorkerAgent 生成工具调用请求
2. 系统检查是否需要用户确认
3. 如果需要确认，显示确认界面等待用户输入
4. 用户确认后，调用对应的工具执行操作
5. 工具执行完成后，将结果返回给 WorkerAgent
6. WorkerAgent 根据执行结果决定下一步操作

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

### 运行步骤

1. 安装依赖：`pip install -r requirements.txt`
2. 配置环境变量：`cp .env.example .env` 并填写相关配置
3. 启动系统：`python main.py`
4. 在终端中输入自然语言指令，系统会自动处理并执行

## 9. 代码结构

```
src/
├── agent/            # Agent 相关代码
│   ├── __init__.py
│   ├── agent.py      # Agent 实现
│   ├── base.py       # 基类定义
│   ├── context.py    # 上下文管理
│   ├── prompt.py     # 提示词管理
│   ├── tools.py      # 工具管理
│   ├── statemachine.py # 状态机实现
│   └── types.py      # 类型定义
├── llm/              # LLM 相关代码
│   ├── __init__.py
│   └── client.py     # LLM 客户端
├── executor/         # Docker 执行器
│   ├── __init__.py
│   └── docker.py     # Docker 执行逻辑
├── logger/           # 日志系统
│   ├── __init__.py
│   └── logger.py     # 日志配置
└── main.py           # 主入口
```

## 10. 总结

Safe-CLI-Agent 是一个安全、可靠的命令行助手，通过 Docker 容器隔离和人机确认机制，确保 AI 在执行系统级指令时的安全性。系统采用多Agent架构，实现了任务执行、结果评审和知识管理等功能，为用户提供了一个智能、安全的命令行工具。