# Safe-CLI-Agent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker Support](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://www.docker.com/)
[![Desktop](https://img.shields.io/badge/Desktop-Electron-blueviolet.svg)](#桌面端模式)

**Safe-CLI-Agent** 是一个基于多智能体架构的智能化命令行助手，以 Electron 桌面端交付。通过 Docker 容器化沙盒与人机交互拦截机制，确保 AI 执行系统级任务时的安全性。

---

## 核心特性

**多智能体协作**：WorkerAgent 执行任务 + JudgeAgent 评审结果 + CuratorAgent 管理知识库

**安全沙盒**：Docker 容器隔离，按工具配置网络/权限/超时，高危命令内嵌确认面板

**智能记忆**：上下文衰减（完整 -> 截断 -> 摘要 -> 遗忘），每 6 步自动压缩

**流式交互**：SSE 实时推送思考过程、工具执行结果、确认请求

**桌面端体验**：自定义无边框窗口、左右侧栏、首次启动引导、Session 持久化

---

## 快速开始

### 前置条件

- Python 3.10+（推荐 conda 管理）
- Node.js 18+
- Docker Desktop（确保已启动）
- 兼容 OpenAI 格式的 LLM API Key

### 桌面端模式（推荐）

```bash
# 1. 获取代码
git clone https://github.com/wu222222/cli-agent.git
cd cli-agent

# 2. 后端环境
conda create -n safe-cli-agent python=3.10
conda activate safe-cli-agent
pip install -r requirements.txt

# 3. 前端依赖
cd frontend && npm install && cd ..

# 4. 启动（首次自动构建，后续秒开）
.\start.bat
```

首次启动会进入引导页，配置 API Key / Base URL / 模型名称。

### 启动脚本

| 脚本 | 用途 |
|------|------|
| `start.bat` | 智能启动（dist 存在则跳过构建，秒开） |
| `build.bat` | 强制重新构建前端并启动 |
| `dev.bat` | 等同于 start.bat（向后兼容） |

### 浏览器模式

```bash
python -m src.api.main          # 后端 http://localhost:8000
cd frontend && npm run dev       # 前端 http://localhost:5173
```

---

## 桌面端功能

### 界面布局

```
┌─ TitleBar（标题栏 + 窗口控制）──────────────────────────┐
├─ HistoryPanel ─┬─ ChatMain ──────────────┬─ RightSidebar ┤
│  对话记录列表   │  消息气泡 + 确认面板      │  上下文 tab   │
│  双击重命名     │  悬浮输入框              │  工具 tab     │
│  折叠/展开      │  命令提示                │  图标栏常驻   │
└────────────────┴────────────────────────┴───────────────┘
```

### 标题栏
- 自定义无边框窗口，深色主题
- 左侧：应用图标 + 标题
- 右侧：连接状态指示 + 设置入口 + 窗口控制

### 左侧栏（HistoryPanel）
- 对话列表，双击重命名
- 显示每个会话的工具标签和消息条数
- AI 运行时禁用会话切换
- 折叠时只显示展开箭头

### 右侧栏（RightSidebar）
- 图标栏始终贴右，点击展开/收起
- **上下文 tab**：消息列表、衰减阶段可视化、摘要统计、一键清空
- **工具 tab**：简约版工具勾选列表 + 保存，支持跳转完整设置页
- 跟随 session 切换自动刷新
- 支持拖拽调整面板宽度

### 设置页（SetupView）
- **API 配置 tab**：环境检测（Docker / .env / API 状态）+ 配置表单
- **插件配置 tab**：plugins.yaml YAML 编辑器（等宽字体、格式验证）
- 标题栏齿轮图标随时进入，首次启动自动弹出

### 命令确认（InlineConfirm）
- 内嵌在聊天流中（非模态弹窗）
- 显示思考过程 + 即将执行的命令
- 支持拒绝 + 输入引导信息让 Agent 重新思考
- 可收缩/展开

---

## 安全策略

| 策略 | 说明 |
|------|------|
| 网络隔离 | 默认 `network_mode: "none"`，联网插件显式设 `"bridge"` |
| 路径受限 | `mount_dirs` 限制挂载目录 |
| 按工具确认 | 每个工具独立配置 `requires_confirmation` |
| 超时保护 | 默认 30s + streaming 外层 300s |
| 权限控制 | 默认 `privileged: false` |
| 上下文衰减 | 消息按年龄截断/遗忘，user/error 永不丢失 |

---

## 技术栈

| 模块 | 技术 |
|------|------|
| 桌面框架 | Electron 42 + electron-vite |
| 前端框架 | Vue 3 + TypeScript + Vite |
| UI 组件库 | Element Plus |
| 后端框架 | FastAPI + Uvicorn |
| LLM SDK | OpenAI 兼容（支持任意供应商） |
| 容器管理 | Docker SDK for Python |
| 会话存储 | JSON 文件持久化（sessions/） |
| 日志系统 | RotatingFileHandler + TTY 检测 |
| 流式通信 | SSE（thought / tool_start / tool_result / confirm / final） |

---

## 发布打包

```bash
# 构建 Windows 安装包（.exe）
npm run build:win

# 产物位于 release/ 目录
```

打包后的应用需要用户预装：
- Python 3.10+（conda 环境 `safe-cli-agent`）
- Docker Desktop

---

## 项目结构

```
cli-agent/
├── electron/                     # Electron 主进程
│   └── src/
│       ├── main.ts               # 窗口管理 + 生命周期
│       ├── python-manager.ts     # Python 子进程管理
│       ├── preload.ts            # IPC 桥接
│       └── tray.ts               # 系统托盘
├── src/                          # Python 后端
│   ├── agent/                    # Agent 核心（FSM + 工具体系）
│   ├── api/                      # FastAPI（routes + services + session）
│   ├── executor/                 # Docker 执行器
│   ├── llm/                      # LLM 客户端
│   └── logger/                   # 日志系统
├── frontend/                     # Vue 3 前端
│   └── src/
│       ├── components/           # TitleBar / HistoryPanel / RightSidebar / InlineConfirm
│       ├── views/                # ChatView / SetupView / ToolsView
│       ├── composables/          # useSSE
│       ├── stores/               # chat
│       ├── api/                  # agent / config
│       └── router/               # 路由 + 引导守卫
├── config/
│   ├── plugins.yaml              # 插件配置
│   └── context_policy.yaml       # 上下文策略
├── sessions/                     # Session 持久化
├── logs/                         # 日志文件（自动轮转）
├── start.bat                     # 智能启动
├── build.bat                     # 强制构建
├── electron-builder.yml          # 打包配置
├── requirements.txt              # Python 依赖
└── package.json                  # Electron 项目配置
```

---

## 开源协议

MIT License
