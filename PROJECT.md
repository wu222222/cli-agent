# Safe-CLI-Agent 技术架构方案

## 1. 系统概述 (System Overview)

Safe-CLI-Agent 是一个具备 **自我推理 (Reasoning)** 与 **工具调用 (Tool Use)** 能力的智能命令行助手，以 **Electron 桌面端** 形式交付。核心特征：

- **Docker 沙盒隔离**：所有命令在容器中执行，与宿主机物理隔离
- **Electron 桌面端**：跨平台桌面应用（Windows/macOS/Linux），自定义无边框窗口
- **首次启动引导**：自动检测 Docker、API 配置状态，引导用户完成初始化
- **Session 持久化**：对话历史、上下文状态、工具配置均持久化到 JSON 文件
- **可扩展插件系统**：通过 YAML 配置文件动态加载插件，无需修改代码

## 2. 核心架构组件 (Core Components)

### A. 推理引擎 (Reasoning Engine)
- **模型需求**：兼容 OpenAI 格式的 LLM API（支持任意供应商）
- **逻辑框架**：采用 ReAct (Reason/Act) 循环
- **上下文管理**：维护动态对话内存，支持记忆衰减和智能摘要压缩
- **多 Agent 架构**：
  - **WorkerAgent**：执行实际任务（命令执行、搜索等）
  - **JudgeAgent**：评审 Worker 的任务完成质量
  - **CuratorAgent**：管理知识库，整理经验教训

### B. 状态管理系统 (State Management)
- **状态机**：每个 Agent 都有自己的状态机
- **状态流转**：Idle → Thinking → [WaitingConfirmation →] Executing → ... → Completed / Error
- **确认拦截**：`requires_confirmation` 为 true 的工具会暂停等待用户确认

### C. 插件容器系统 (Plugin Container System)
- **三层工具架构**：
  - **exec**：Docker 容器内执行命令（如 alpine_shell、search）
  - **command**：用户快捷命令（如 /summary 触发 CuratorAgent）
  - **local**：进程内函数调用（如 call_judge、context_compress）
- **生命周期管理**：容器默认不自动启动，用户在右侧栏工具 tab 或工具设置页手动启动
- **Compose 插件**：多容器协作（如 CTF 靶场），通过 docker-compose.yml 管理

### D. 上下文持久化 (Context Persistence)
- **ContextManager 序列化**：`to_dict()` / `from_dict()` 将消息列表和摘要序列化
- **Session 绑定**：上下文随 session 保存到 `sessions/session_{id}.json` 的 `context` 字段
- **自动保存**：Agent 每步执行后自动保存上下文到 session 文件
- **切换恢复**：resume session 时自动恢复上下文，切换时先清空再加载

### E. Session 管理 (Session Management)
- **SessionManager**：JSON 文件持久化，存储消息、工具配置、上下文
- **工具配置同步**：每个 session 独立保存工具列表，resume 时恢复到全局
- **自动创建**：首条消息时自动创建 session
- **动态计数**：消息数量通过 watcher 实时更新

## 3. 桌面端架构 (Desktop Architecture)

### Electron 主进程
- **PythonManager**：管理 Python 后端子进程的生命周期（启动/停止/健康检查）
- **无边框窗口**：`frame: false`，自定义 TitleBar 实现窗口控制
- **F12 开发者工具**：所有模式可用
- **关闭即退出**：关闭窗口直接终止进程

### 前端 UI 架构
```
┌─ TitleBar（标题栏：图标 + 页面导航 + 窗口控制）──────────────────┐
├─ HistoryPanel ─┬─ ChatMain ──────────────┬─ RightSidebar ────────┤
│  （左侧栏）     │  （聊天主区域）           │  （右侧栏）           │
│  对话记录列表   │  消息气泡 + 确认面板      │  📄 上下文 tab        │
│  双击重命名     │  悬浮输入框              │  🔧 工具 tab          │
│  折叠箭头       │  命令提示                │  图标栏始终可见        │
└────────────────┴────────────────────────┴────────────────────────┘
```

### 核心组件
- **TitleBar**：统一标题栏，支持 slot 插槽（页面自定义内容 + 右侧操作区）
- **HistoryPanel**：左侧会话列表，支持折叠/展开、双击重命名、工具标签显示
- **RightSidebar**：右侧多 tab 栏，图标栏始终贴右，内容面板在左侧展开
  - **ContextTab**：上下文可视化（消息列表、衰减阶段、摘要统计）
  - **ToolsTab**：简约版工具配置（勾选列表 + 保存 + 跳转完整设置）
- **InlineConfirm**：内嵌确认面板（替代模态弹窗），支持展开/收起
- **SetupView**：首次启动引导 + 设置页（API 配置 tab + 插件 YAML 编辑器 tab）
- **MessageBubble**：消息气泡（支持 Markdown、代码块、工具卡片折叠）

### SSE 实时通信
- `thought`：Agent 思考过程
- `tool_start`：工具开始执行（前端显示当前工具名）
- `tool_result`：工具执行结果（含 command 和格式化内容）
- `confirm`：等待用户确认（内嵌面板展示）
- `final`：任务完成
- `error`：执行错误

## 4. 技术栈 (Technical Stack)

| 模块 | 实现 |
|------|------|
| 桌面框架 | Electron 42+ |
| 构建工具 | electron-vite 5+ |
| 打包工具 | electron-builder（NSIS .exe / DMG / AppImage） |
| 前端框架 | Vue 3 + TypeScript |
| UI 组件库 | Element Plus |
| 前端构建 | Vite |
| 后端框架 | Python FastAPI |
| LLM SDK | OpenAI 兼容（支持任意供应商） |
| Docker | docker-py（Docker SDK for Python） |
| 类型检查 | Pydantic V2 |
| 日志系统 | RotatingFileHandler + TTY 检测 + ANSI 颜色 |
| 状态管理 | 自定义状态机 + ContextManager |

## 5. 日志系统 (Logging System)

- **RotatingFileHandler**：5MB 自动轮转，保留 3 个备份，7 天以上旧日志自动清理
- **TTY 检测**：非 TTY 环境（Electron pipe）自动禁用 ANSI 颜色码
- **Electron 转发**：Python 子进程的 stdout/stderr 始终转发到 Electron 控制台（`[python]` / `[python:err]` 前缀）
- **结构化日志**：`log_structured()` 支持 JSON 格式的结构化日志输出

## 6. 安全策略 (Security Policy)

- **Docker 隔离**：默认 `network_mode: "none"`，`privileged: false`
- **超时控制**：默认 30 秒 + streaming 外层 300 秒双重超时
- **人机确认**：`requires_confirmation` 按工具独立配置
- **上下文衰减**：消息按年龄自动截断/摘要/遗忘，user 和 error 消息永不丢失
- **参数验证**：Pydantic 模型验证工具参数，LLM 返回 null 时自动容错

## 7. 首次启动引导 (Setup Wizard)

- **路由守卫**：未配置时自动跳转引导页
- **环境检测**：Docker 三级状态（未安装/未启动/运行中）+ .env 文件状态 + API 配置状态
- **环境变量支持**：系统环境变量有 API Key 时不要求重复填写，不写入 .env
- **插件配置**：YAML 编辑器（等宽字体、格式验证、重新加载/保存）
- **非强制**：可跳过直接进入主界面，标题栏齿轮图标随时回到设置页

## 8. 部署与运行

### 桌面端开发
```bash
# 智能启动（dist 存在则跳过构建）
start.bat

# 强制重新构建并启动
build.bat

# npm scripts
npm run dev              # electron-vite 开发模式
npm run build:frontend   # 仅构建前端
npm run build:win        # 构建 Windows 安装包
```

### 纯后端运行
```bash
pip install -r requirements.txt
python -m src.api.main   # http://localhost:8000
```

### 生产打包
```bash
npm run build:win    # 生成 release/ 目录下的 .exe 安装包
```

## 9. 代码结构

```
├── electron/                    # Electron 主进程
│   └── src/
│       ├── main.ts              # 主进程入口（窗口/IPC/生命周期）
│       ├── python-manager.ts    # Python 子进程管理
│       ├── preload.ts           # 预加载脚本（contextBridge）
│       ├── tray.ts              # 系统托盘
│       ├── updater.ts           # 自动更新
│       └── utils.ts             # 工具函数（端口检测/conda/Python 路径）
├── src/                         # Python 后端
│   ├── agent/                   # Agent 核心逻辑
│   │   ├── agent.py             # Worker/Judge/Curator Agent
│   │   ├── base.py              # Agent 基类
│   │   ├── context.py           # 上下文管理器（含持久化序列化）
│   │   ├── prompt.py            # Prompt 管理器
│   │   ├── tools.py             # 工具体系（exec/command/local/compose）
│   │   ├── statemachine.py      # 状态机
│   │   ├── types.py             # 类型定义
│   │   └── registry.py          # Agent 类型注册表
│   ├── api/                     # FastAPI 后端
│   │   ├── main.py              # App 入口
│   │   ├── models.py            # 请求/响应模型
│   │   ├── routes.py            # 路由（chat/setup/plugins/session）
│   │   ├── services.py          # 业务逻辑 + 组件初始化
│   │   ├── streaming.py         # SSE 流式 Agent
│   │   └── session_manager.py   # Session 持久化管理
│   ├── executor/                # Docker 执行器
│   ├── llm/                     # LLM 客户端
│   └── logger/                  # 日志系统（RotatingFileHandler + TTY 检测）
├── frontend/                    # Vue 3 前端
│   └── src/
│       ├── views/
│       │   ├── ChatView.vue     # 聊天主界面
│       │   ├── SetupView.vue    # 设置/引导页（API + 插件 YAML）
│       │   ├── ToolsView.vue    # 工具详细设置页
│       │   └── SettingsView.vue # 系统设置
│       ├── components/
│       │   ├── TitleBar.vue     # 统一标题栏（slot 架构）
│       │   ├── HistoryPanel.vue # 左侧会话列表
│       │   ├── RightSidebar.vue # 右侧多 tab 容器
│       │   ├── ContextTab.vue   # 上下文 tab
│       │   ├── ToolsTab.vue     # 简约工具 tab
│       │   ├── InlineConfirm.vue# 内嵌确认面板
│       │   ├── MessageBubble.vue# 消息气泡
│       │   └── ToolCard.vue     # 工具结果卡片
│       ├── composables/
│       │   └── useSSE.ts        # SSE 事件处理
│       ├── stores/
│       │   └── chat.ts          # 聊天状态管理
│       ├── api/
│       │   ├── agent.ts         # Agent API + SSE 连接
│       │   └── config.ts        # 插件/Session API
│       └── router/
│           └── index.ts         # 路由 + 引导守卫
├── config/
│   ├── plugins.yaml             # 插件配置
│   └── context_policy.yaml      # 上下文策略
├── sessions/                    # Session 持久化目录
├── logs/                        # 日志文件目录
├── start.bat                    # 智能启动
├── build.bat                    # 强制构建并启动
├── electron-builder.yml         # 打包配置
└── .env.example                 # 环境变量模板
```

## 10. 总结

Safe-CLI-Agent 是一个安全、可扩展的桌面端 CLI 助手。核心设计理念：

- **配置驱动**：新增插件只需编辑 `plugins.yaml`，不改代码
- **Docker 隔离**：可配网络/特权/超时，默认安全
- **多 Agent 协作**：Worker 执行 + Judge 评审 + Curator 整理
- **记忆衰减**：上下文自动截断/摘要/遗忘，长任务不爆 token
- **Session 持久化**：对话历史、上下文、工具配置全部持久化
- **桌面端体验**：Electron 无边框窗口 + 自定义标题栏 + 右侧多 tab 栏
