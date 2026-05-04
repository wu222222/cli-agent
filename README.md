# Safe-CLI-Agent 🛡️

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker Support](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://www.docker.com/)

**Safe-CLI-Agent** 是一个基于多智能体（Multi-Agent）架构的智能化命令行助手。它不仅能理解你的自然语言指令并转化为 Shell 操作，更通过 **Docker 容器化沙盒** 与 **人机交互拦截（HITL）** 机制，确保 AI 在执行系统级任务时的绝对安全。

> "让 AI 拥有操作系统的能力，同时将其关进安全的笼子里。"

![前端效果](code_task_prompt/demonstration_picture/放在开头.png)

---

## ✨ 核心特性

- 🤖 **多智能体协作 (Multi-Agent)**: 
  - **Worker**: 负责任务推理与执行。
  - **Judge**: 负责对执行结果进行二次审计与质量把控。
  - **Curator**: 自动总结成功经验，维护动态知识库。
- 🔒 **物理隔离沙盒**: 所有命令默认在 Docker 容器内运行，支持网络隔离与资源限制，宿主机零风险。
- ⚙️ **确定性状态机 (FSM)**: 基于状态机管理 Agent 行为，逻辑清晰可追踪，拒绝"幻觉"导致的死循环。
- 🛡️ **安全拦截层**: 每一条危险指令执行前，都会交由人类用户显式授权。
- 🧠 **本地知识沉淀**: 自动从历史成功案例中提取经验，支持 Markdown 格式知识库更新。
- 🌐 **Web 前端界面**: 提供直观的聊天式交互界面，支持实时流式输出、命令确认、Docker 配置等功能。

---

## 🏗️ 系统架构

系统采用分层设计，确保推理逻辑与执行环境解耦：

```
┌─────────────────────────────────────────────┐
│              Frontend (Vue 3)               │
│    ChatView / SetupView / HistoryView       │
└──────────────────┬──────────────────────────┘
                   │ HTTP + SSE
┌──────────────────▼──────────────────────────┐
│            API Layer (FastAPI)              │
│    routes.py / services.py / streaming.py   │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│           Agent Layer (FSM)                 │
│  WorkerAgent / JudgeAgent / CuratorAgent    │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│         Execution Layer (Docker)            │
│        DockerExecutor (Sandbox)             │
└─────────────────────────────────────────────┘
```

1. **前端层**: Vue 3 + TypeScript，提供聊天交互、Docker 配置、历史记录等功能。
2. **API 层**: FastAPI，处理 HTTP 请求、SSE 流式推送、组件管理。
3. **推理层**: 支持 Function Calling 的大模型（如 Qwen, GPT-4 等）。
4. **控制层**: 维护状态流转、上下文压缩与人机交互逻辑。
5. **执行层**: 动态销毁的 Docker 容器沙盒。

---

## 🚀 快速开始

### 前置条件

- Python 3.10+
- Node.js 18+ (前端构建)
- Docker Engine (确保 Docker 进程已启动)
- LLM API Key (支持国内主流模型)

### 1. 获取代码

```bash
git clone https://github.com/wu222222/cli-agent.git
cd cli-agent
```

### 2. 后端环境配置 (推荐使用 conda/mamba)

```bash
mamba env create -f environment.yml
mamba activate safe-cli-agent
# 或者使用 pip
# pip install -r requirements.txt
```

### 3. 配置密钥

```bash
cp .env.example .env
# 编辑 .env 文件，填写你的 API_KEY 和 BASE_URL
```

### 4. 启动后端

```bash
python -m src.api.main
# 后端运行在 http://localhost:8000
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
# 前端运行在 http://localhost:5173
```

### 6. 访问应用

打开浏览器访问 `http://localhost:5173`，首次访问会进入 Docker 配置页面。

---

## 🖥️ 前端功能

### Docker 配置页面 (`/setup`)

首次访问时会进入 Docker 配置页面，支持：
- **镜像选择**: 预设 Alpine Linux、Ubuntu、Debian、MyLab 等选项，也支持自定义镜像
- **容器配置**: 容器名称、网络模式、内存限制、命令超时
- **存储配置**: 工作目录挂载、知识库挂载及读写权限

![Docker 配置页面](code_task_prompt/demonstration_picture/docker设置.png)

### 聊天交互页面 (`/`)

主聊天界面支持：
- **自然语言输入**: 输入任意问题或指令，Agent 会自动分析并执行
- **命令确认**: 执行命令前会显示 Agent 的思考过程和待执行命令，用户确认后才执行
- **实时流式输出**: 工具执行结果、JudgeAgent 评审结果实时推送显示
- **多 Agent 展示**: 区分 WorkerAgent、JudgeAgent 的输出，带不同标识
- **Curator 命令**: 输入 `/summary` 可触发 CuratorAgent 整理对话历史

![命令确认](code_task_prompt/demonstration_picture/命令确认.png)

### 完整效果

![完整效果图](code_task_prompt/demonstration_picture/完整效果图.png)

---

## 🛡️ 安全策略 (Security)

- **网络隔离**: 启动容器时默认添加 `--network none`，防止敏感数据外泄。
- **路径受限**: 仅允许挂载指定的 `./workspace` 目录，Agent 无法触碰宿主机系统文件。
- **资源限制**: 严格限制容器的内存 (Memory Limit) 和 CPU 配额。
- **超时保护**: 强制设置命令执行超时 (Timeout)，防止恶意脚本耗尽资源。
- **人工确认**: 危险命令执行前必须经过用户确认。

---

## 🛠️ 技术栈 (Technical Stack)

| 模块 | 技术实现 |
|------|----------|
| 前端框架 | Vue 3 + TypeScript + Vite |
| API 服务 | FastAPI + Uvicorn |
| LLM 交互 | 自定义异步 LLMClient |
| 沙盒执行 | Docker SDK for Python |
| 状态管理 | Pythonic Finite State Machine (FSM) |
| 数据校验 | Pydantic V2 |
| 流式通信 | Server-Sent Events (SSE) |

---

## 📁 项目结构

```
cli-agent/
├── src/
│   ├── api/                # FastAPI 后端
│   │   ├── main.py         # App 入口
│   │   ├── models.py       # 请求/响应模型
│   │   ├── routes.py       # 路由处理器
│   │   ├── services.py     # 业务逻辑、组件管理
│   │   └── streaming.py    # SSE 流式 Agent
│   ├── agent/              # Agent 核心逻辑
│   │   ├── agent.py        # Worker/Judge/Curator Agent
│   │   ├── base.py         # Agent 基类
│   │   ├── statemachine.py # 状态机实现
│   │   ├── context.py      # 上下文管理
│   │   └── prompt.py       # Prompt 管理
│   ├── executor/           # Docker 执行器
│   └── llm/                # LLM 客户端
├── frontend/               # Vue 3 前端
│   ├── src/
│   │   ├── views/          # 页面组件
│   │   ├── api/            # API 客户端
│   │   ├── router/         # 路由配置
│   │   └── types/          # TypeScript 类型
│   └── package.json
├── knowledge_base/         # 知识库目录
├── workspace/              # 工作目录
└── environment.yml         # Conda 环境配置
```

---

## 📄 开源协议

本项目采用 MIT License 协议。
