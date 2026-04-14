# Safe-CLI-Agent 技术架构方案

## 1. 系统概述 (System Overview)

本系统是一个具备 **自我推理 (Reasoning)** 与 **工具调用 (Tool Use)** 能力的命令行助手。其核心特征是通过 Docker 容器实现执行环境与宿主机的物理隔离，确保 AI 在执行系统级指令时的绝对安全性。

## 2. 核心架构组件 (Core Components)

### A. 推理引擎 (Reasoning Engine)
- **模型需求**：支持 Function Calling 的 LLM (如 千问,前期暂时只考虑国产模型)。
- **逻辑框架**：采用 ReAct (Reason/Act) 循环。
- **上下文管理**：维护一个动态的对话内存，记录用户的指令、Agent 的思考过程、工具调用参数以及沙盒返回的执行结果。

### B. Docker 执行沙盒 (Docker Executor)
- **隔离机制**：所有的 Shell 指令均在独立的 Docker 容器中运行。
- **生命周期管理**：
  - 启动时创建临时容器（如基于 alpine 或 python:slim）。
  - 运行时通过 docker exec 传递指令。
  - 退出时强制销毁容器，确保"无迹寻踪"。
- **权限限制**：容器默认禁用 --privileged 模式，限制 CPU 与内存配额，且使用非 root 用户执行。

### C. 人机确认拦截层 (HITL - Human-in-the-loop)
- 作为"物理防火墙"，在 LLM 发出工具执行请求与实际调用 Docker API 之间建立拦截机制。
- 展示生成的代码/指令，等待用户显式授权。

## 3. 工作流逻辑 (Workflow)

1. **用户输入 (Input)**：用户在终端输入自然语言需求（例如："找出当前目录下最大的 5 个文件"）。
2. **推理 (Think)**：LLM 分析需求，决定调用 execute_command 工具，并生成对应的 Shell 脚本（如 `du -ah . | sort -rh | head -n 5`）。
3. **拦截 (Intercept)**：宿主机程序捕获到 Tool Call，解析参数并在控制台高亮显示。
4. **执行 (Act)**：用户确认后，指令被发送至 Docker 容器。
5. **反馈 (Observe)**：捕获容器的标准输出 (stdout) 和错误输出 (stderr)，将其反馈给 LLM。
6. **总结 (Output)**：LLM 根据执行结果生成人类可读的最终回答。

## 4. 技术栈建议 (Technical Stack)

| 模块 | 推荐实现 |
|------|----------|
| 语言 | Python 3.10+ |
| LLM SDK | langchain-openai 或 anthropic SDK |
| Docker 通讯 | docker-py (Docker SDK for Python) |
| CLI 界面 | rich (用于优雅的终端表格、进度条和代码高亮) |
| 环境配置 | python-dotenv |

## 5. 安全策略 (Security Policy)

- **路径隔离**：仅允许挂载特定的 /workspace 目录，禁止访问宿主机根目录。
- **网络隔离**：默认启动容器时添加 --network none，防止 Agent 意外泄露 API Keys 或建立反弹 Shell。
- **超时控制**：为每个指令设置 timeout（如 30 秒），防止逻辑陷阱或死循环耗尽资源。
- **指令脱敏**：在反馈给 LLM 之前，自动过滤执行结果中可能包含的敏感环境变量。

## 6. 扩展方向 (Future Scaling)

- **多容器协同**：为不同的任务（如 Node.js 开发 vs. Python 数据分析）启动预装不同环境的容器镜像。
- **文件系统快照**：支持在执行危险操作前对容器进行快照，以便随时回滚。

## 7. 实现注意事项

> 在实现时，请优先编写 executor.py 以处理 docker.from_env() 的异常捕获，确保在 Docker 守护进程未启动时程序能优雅退出。