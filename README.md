# Safe-CLI-Agent 🛡️

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker Support](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://www.docker.com/)

**Safe-CLI-Agent** 是一个基于多智能体（Multi-Agent）架构的智能化命令行助手。它不仅能理解你的自然语言指令并转化为 Shell 操作，更通过 **Docker 容器化沙盒** 与 **人机交互拦截（HITL）** 机制，确保 AI 在执行系统级任务时的绝对安全。

> "让 AI 拥有操作系统的能力，同时将其关进安全的笼子里。"

![前端效果](docs/demonstration_picture/放在开头.png)

---

## ✨ 核心特性

- 🤖 **多智能体协作 (Multi-Agent)**: 
  - **Worker**: 负责任务推理与执行，思考过程实时可见。
  - **Judge**: 负责对执行结果进行二次审计与质量把控（PASS/FAIL），思考过程附带在评审结果中。
  - **Curator**: 自动总结成功经验，维护动态知识库。
- 🔒 **插件化容器隔离**: 无默认沙盒，用户按需启动容器插件（mylab、alpine_shell 等），支持网络隔离与资源限制。
- ⚙️ **确定性状态机 (FSM)**: 基于状态机管理 Agent 行为，逻辑清晰可追踪，拒绝"幻觉"导致的死循环。
- 🛡️ **按工具安全拦截**: 每个 exec 工具独立配置 `requires_confirmation`，弹出确认对话框展示思考过程和命令。
- 💭 **实时流式展示**: 通过 SSE 推送 Agent 思考过程（thought）、工具执行结果（tool_result）、确认请求（confirm）。
- 🧠 **本地知识沉淀**: 自动从历史成功案例中提取经验，支持 Markdown 格式知识库更新。
- 🌐 **Web 前端界面**: 提供直观的聊天式交互界面，支持工具设置（勾选工具、启停容器、配置挂载路径）。

---

## 🏗️ 系统架构

系统采用分层设计，确保推理逻辑与执行环境解耦：

```
┌─────────────────────────────────────────────┐
│              Frontend (Vue 3)               │
│  ChatView / ToolsView / HistoryView         │
│  💭 thought  ⚙ tool_result  ⚠ confirm      │
└──────────────────┬──────────────────────────┘
                   │ HTTP + SSE
┌──────────────────▼──────────────────────────┐
│            API Layer (FastAPI)              │
│  routes.py / services.py / streaming.py     │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│           Agent Layer (FSM)                 │
│  WorkerAgent / JudgeAgent / CuratorAgent    │
│  StreamingWorkerAgent (SSE callbacks)       │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│         Plugin Container Layer              │
│  ExecContainerPlugin (mylab, alpine...)     │
│  PluginContainerManager (lifecycle)         │
└─────────────────────────────────────────────┘
```

1. **前端层**: Vue 3 + TypeScript，提供聊天交互（thought/tool_result 气泡）、工具设置（启停容器）、历史记录。
2. **API 层**: FastAPI，处理 HTTP 请求、SSE 流式推送（6 种事件类型）、组件管理。
3. **推理层**: 支持 Function Calling 的大模型（如 Qwen, GPT-4 等）。
4. **控制层**: 维护状态流转、上下文管理、人机确认拦截、Agent thought 存储。
5. **执行层**: 插件化 Docker 容器，按需启动/停止，支持挂载目录配置。

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

打开浏览器访问 `http://localhost:5173`，进入聊天界面。点击"工具设置"可配置可用工具和启动容器。

---

## 🖥️ 前端功能

![完整效果图](docs/demonstration_picture/完整效果图.png)

### 工具设置页面 (`/tools`)

![工具设置页面](docs/demonstration_picture/工具设置.png)

工具管理页面，支持：
- **工具勾选**: 为 WorkerAgent 配置可用工具列表（如 call_judge + mylab）
- **容器启停**: 每个 exec 工具显示容器状态（运行中/已停止），支持一键启动/停止
- **保存即生效**: 保存配置时自动启动已勾选的 exec 容器
- **挂载路径显示**: 展示每个工具的 mount_dirs 配置

### 命令确认页面 (`/confirm`)

![命令确认页面](docs/demonstration_picture/命令确认.png)

命令确认页面，支持：
- **确认执行**: 确认执行待执行命令
- **拒绝执行**: 拒绝执行待执行命令，后端自动清理挂起的 Agent 状态
- **引导agent**: 用户键入信息，引导 Agent 执行任务

### 聊天交互页面 (`/`)

主聊天界面支持：
- **自然语言输入**: 输入任意问题或指令，Agent 会自动分析并执行
- **💭 思考气泡**: Agent 的推理过程以独立气泡实时展示
- **⚙ 工具结果气泡**: 工具执行结果带命令参数和输出内容展示
- **命令确认**: exec 工具执行前弹出确认对话框，展示思考过程和待执行命令，支持拒绝
- **JudgeAgent 评审**: 评审结果中附带 JudgeAgent 的思考过程
- **最终回答**: Agent 的完整回答以独立气泡展示
- **Curator 命令**: 输入 `/summary` 可触发 CuratorAgent 整理对话历史

---

## 🛡️ 安全策略 (Security)

- **网络隔离**: 启动容器时默认添加 `--network none`，防止敏感数据外泄。
- **路径受限**: 通过 mount_dirs 配置挂载目录（如 `./workspace:/workspace`），Agent 无法触碰宿主机系统文件。
- **按工具确认**: 每个 exec 工具独立配置 `requires_confirmation`，弹出确认对话框展示 Agent 思考过程和待执行命令。
- **拒绝机制**: 用户可随时拒绝命令执行，后端自动清理挂起的 Agent 状态。
- **资源限制**: 严格限制容器的内存 (Memory Limit) 和 CPU 配额。
- **超时保护**: 强制设置命令执行超时 (Timeout)，防止恶意脚本耗尽资源。

---

## 🛠️ 技术栈 (Technical Stack)

| 模块 | 技术实现 |
|------|----------|
| 前端框架 | Vue 3 + TypeScript + Vite |
| UI 组件库 | Element Plus |
| API 服务 | FastAPI + Uvicorn |
| LLM 交互 | 自定义异步 LLMClient |
| 容器管理 | Docker SDK for Python（PluginContainerManager） |
| 工具体系 | 三层架构（LocalTool / ExecContainerPlugin / NetworkContainerPlugin） |
| 状态管理 | Pythonic Finite State Machine (FSM) |
| 数据校验 | Pydantic V2 |
| 流式通信 | Server-Sent Events (SSE) — thought / tool_start / tool_result / confirm / final |
| 插件配置 | YAML 动态加载（config/plugins.yaml） |

---

## 📁 项目结构

```
cli-agent/
├── src/
│   ├── api/                  # FastAPI 后端
│   │   ├── main.py           # App 入口
│   │   ├── models.py         # 请求/响应模型
│   │   ├── routes.py         # 路由处理器（chat/plugins/agent/tools/reject）
│   │   ├── services.py       # 业务逻辑、组件初始化
│   │   └── streaming.py      # SSE 流式 Agent（emit_thought/tool_start/tool_result）
│   ├── agent/                # Agent 核心逻辑
│   │   ├── agent.py          # Worker/Judge/Curator Agent
│   │   ├── base.py           # Agent 基类（含 last_thought）
│   │   ├── statemachine.py   # 状态机实现
│   │   ├── context.py        # 上下文管理
│   │   ├── prompt.py         # Prompt 管理（动态工具文档生成）
│   │   ├── tools.py          # 工具体系（Tool/LocalTool/ExecContainerPlugin/ToolRegistry）
│   │   └── types.py          # 类型定义
│   ├── executor/             # Docker 执行器
│   │   ├── docker.py         # DockerExecutor + PluginContainerManager
│   │   └── client.py         # DockerClientFactory
│   └── llm/                  # LLM 客户端
├── config/
│   └── plugins.yaml          # 插件容器配置
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── views/            # 页面（ChatView / ToolsView / HistoryView）
│   │   ├── components/       # 组件（MessageBubble / ConfirmDialog / ToolCard）
│   │   ├── composables/      # 组合式函数（useSSE）
│   │   ├── stores/           # 状态管理（chat / plugin）
│   │   ├── api/              # API 客户端（agent / config）
│   │   └── types/            # TypeScript 类型
│   └── package.json
├── knowledge_base/           # 知识库目录
├── workspace/                # 工作目录（alpine_shell 默认挂载）
└── environment.yml           # Conda 环境配置
```

---

## 📄 开源协议

本项目采用 MIT License 协议。
