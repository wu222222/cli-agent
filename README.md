# Safe-CLI-Agent 🛡️

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker Support](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://www.docker.com/)

**Safe-CLI-Agent** 是一个基于多智能体（Multi-Agent）架构的智能化命令行助手。它不仅能理解你的自然语言指令并转化为 Shell 操作，更通过 **Docker 容器化沙盒** 与 **人机交互拦截（HITL）** 机制，确保 AI 在执行系统级任务时的绝对安全。

> "让 AI 拥有操作系统的能力，同时将其关进安全的笼子里。"

---

## ✨ 核心特性

- 🤖 **多智能体协作 (Multi-Agent)**: 
  - **Worker**: 负责任务推理与执行。
  - **Judge**: 负责对执行结果进行二次审计与质量把控。
  - **Curator**: 自动总结成功经验，维护动态知识库。
- 🔒 **物理隔离沙盒**: 所有命令默认在 Docker 容器内运行，支持网络隔离与资源限制，宿主机零风险。
- ⚙️ **确定性状态机 (FSM)**: 基于状态机管理 Agent 行为，逻辑清晰可追踪，拒绝“幻觉”导致的死循环。
- 🛡️ **安全拦截层**: 每一条危险指令执行前，都会交由人类用户显式授权。
- 🧠 **本地知识沉淀**: 自动从历史成功案例中提取经验，支持 Markdown 格式知识库更新。

---

## 🏗️ 系统架构

系统采用分层设计，确保推理逻辑与执行环境解耦：

1. **推理层**: 支持 Function Calling 的大模型（如 Qwen, GPT-4 等）。
2. **控制层**: 维护状态流转、上下文压缩与人机交互逻辑。
3. **执行层**: 动态销毁的 Docker 容器沙盒。

---

## 🚀 快速开始

### 前置条件

- Python 3.10+
- Docker Engine (确保 Docker 进程已启动)
- LLM API Key (支持国内主流模型)

### 安装

1. **获取代码**

```bash
git clone [https://github.com/your-username/safe-cli-agent.git](https://github.com/your-username/safe-cli-agent.git)
cd safe-cli-agent
```

2. **环境配置(推荐使用conda/mamba)**

```bash
mamba env create -f environment.yml
mamba activate safe-cli-agent
# 或者使用 pip
# pip install -r requirements.txt
```

3. **配置密钥**

```bash
cp .env.example .env
# 编辑 .env 文件，填写你的 API_KEY 和 BASE_URL
```

4. **运行系统**

```bash
# example包含测试脚本
python -m examples.safe_cli_agent_test
```

## 🛡️ 安全策略 (Security)

- 网络隔离: 启动容器时默认添加 --network none，防止敏感数据外泄。
- 路径受限: 仅允许挂载指定的 ./workspace 目录，Agent 无法触碰宿主机系统文件。
- 资源限制: 严格限制容器的内存 (Memory Limit) 和 CPU 配额。
- 超时保护: 强制设置命令执行超时 (Timeout)，防止恶意脚本耗尽资源。

## 🛠️ 技术栈 (Technical Stack)

| 模块 | 技术实现 |
|------|----------|
| LLM 交互 | 自定义异步 LLMClient |
| 沙盒执行 | Docker SDK for Python |
| 状态管理 | Pythonic Finite State Machine (FSM) |
| 数据校验 | Pydantic V2 |
| 终端展示 | Rich (实现高亮显示与交互界面) |

## 📄 开源协议

本项目采用 MIT License 协议。

