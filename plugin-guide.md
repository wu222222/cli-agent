# Safe-CLI-Agent 插件配置指南

> 加一个新插件 = 创建一个目录 + 一份 YAML 配置。不需要写 Python，不需要改 Vue。

---

## 目录

1. [快速开始：我该选哪种插件类型？](#快速开始)
2. [插件目录规范](#插件目录规范)
3. [插件类型一览](#插件类型一览)
4. [配置 exec 插件（Agent 工具）](#一配置-exec-插件)
5. [配置 command 插件（用户快捷命令）](#二配置-command-插件)
6. [配置 compose 插件（多容器组）](#三配置-compose-插件)
7. [配置 local 插件（进程内函数）](#四配置-local-插件)
8. [导入与管理插件](#五导入与管理插件)
9. [完整字段参考](#六完整字段参考)
10. [常见问题](#七常见问题)

---

## 快速开始

**问自己三个问题：**

| 问题 | 你的答案 | 选这种类型 |
|------|---------|-----------|
| 这个插件需要 Agent（AI）自动调用吗？ | 是 → | **exec** |
| 这个插件是用户在聊天框输入 `/xxx` 手动触发的吗？ | 是 → | **command** |
| 这个插件需要同时跑多个 Docker 容器吗？ | 是 → | **compose** |
| 这个插件只是一个 Python 函数，不需要容器？ | 是 → | **local** |

**然后**：在 `config/plugins/` 下创建插件目录，放入 `plugin.yaml` → 重启服务 → 完成。

---

## 插件目录规范

每个插件是 `config/plugins/` 下的一个自包含文件夹：

```
config/plugins/
  my_tool/
    plugin.yaml                    ← 必填：插件定义
  ctf_lab/
    plugin.yaml                    ← 插件定义
    docker-compose.yml             ← compose 插件需要
    Dockerfile                     ← 可选：自定义镜像
    volumes/                       ← 可选：脚本、证书等资源
  my_translator/
    plugin.yaml
    handler.py                     ← local 插件的 Python handler
```

### plugin.yaml 格式

与主配置 `plugins.yaml` 完全一致，`compose_file` 路径**相对于插件目录**：

```yaml
plugins:
  - name: "ctf_lab"
    type: "compose"
    compose_file: "docker-compose.yml"    ← 相对于 plugin.yaml 所在目录
    ...
```

### 加载优先级

1. `config/plugins.yaml` — 主配置（最先加载）
2. `config/plugins/*/plugin.yaml` — 插件目录（按目录名字母序加载）

所有插件自动合并到 ToolRegistry，名称冲突时后加载的覆盖先加载的。

---

## 插件类型一览

```
plugin.yaml
  └── plugins:
        ├── exec      → Agent 工具，LLM 自动选择调用
        ├── command   → 用户 /xxx 触发，不暴露给 Agent
        ├── compose   → 多容器组，子服务按 type 注册
        │   └── services:
        │       ├── type: exec    → 注册为 Agent 工具
        │       ├── type: command → 注册为用户命令
        │       └── type: aux    → 辅助容器（不注册）
        ├── local     → Python 函数，进程内执行
        └── network   → HTTP 服务（尚未实现）
```

---

## 一、配置 exec 插件

**适用场景**：你想给 Agent 一个"在容器里执行命令"的能力。比如给 Agent 一个 Linux shell、一个数据库查询工具、一个扫描器。

### 最小配置

创建 `config/plugins/my_tool/plugin.yaml`：

```yaml
plugins:
  - name: "my_tool"                          # 工具名（Agent 调用时用这个名字）
    type: "exec"                             # 插件类型
    agent_type: "worker"                     # 绑定到 WorkerAgent
    bound_action: "execute_command"          # FSM 路由动作
    requires_confirmation: true              # 是否需要用户点"确认"
    description: "我的自定义工具"
    container_name: "my_container"           # Docker 容器名
    image: "ubuntu:latest"                   # 首次启动时自动拉取的镜像
    entrypoint_cmd: "bash -c"               # 容器内执行命令的入口
    category: "shell"                        # 前端 ToolsView 显示分类
    icon: "terminal"                         # 前端图标
    parameters:
      command:
        type: "string"
        description: "要执行的命令"
    required_params: ["command"]
```

### 完整示例：添加一个 nmap 扫描工具

```yaml
plugins:
  - name: "nmap_scanner"
    type: "exec"
    agent_type: "worker"
    bound_action: "execute_command"
    requires_confirmation: true
    description: "Nmap 网络扫描器 — 用于端口扫描和服务发现"
    container_name: "nmap_scanner"
    image: "instrumentisto/nmap:latest"
    entrypoint_cmd: "sh -c"
    mount_dirs: []
    category: "shell"
    icon: "target"
    parameters:
      command:
        type: "string"
        description: "要执行的 nmap 命令，如 'nmap -sV 192.168.1.1'"
    required_params: ["command"]
```

### 如何验证

1. 启动服务后打开 ToolsView → 在对应 category 下看到 `nmap_scanner` 卡片
2. 点击"启动" → 容器运行
3. 在聊天框输入"扫描 127.0.0.1 的端口" → Agent 调用 `nmap_scanner`

---

## 二、配置 command 插件

**适用场景**：你想让用户在聊天框输入 `/xxx` 快速执行某个操作。这个操作不经过 Agent 推理，直接执行。

### 最小配置

```yaml
plugins:
  - name: "my_command"
    type: "command"
    agent_type: "none"                       # none = 不经过 Agent，直接执行
    command_trigger: "/mycmd"                # 用户在聊天框输入这个触发
    bound_action: "execute_command"
    requires_confirmation: false
    description: "我的快捷命令"
    container_name: "my_container"
    image: "alpine:latest"
    entrypoint_cmd: "sh -c"
    category: "command"
    icon: "command"
    parameters:
      command:
        type: "string"
        description: "要执行的命令"
    required_params: ["command"]
```

### agent_type 的选择

| agent_type | 效果 |
|-----------|------|
| `"none"` | 直接 docker exec 执行，最常用 |
| `"curator"` | 触发 CuratorAgent（知识库管理），如 `/summary` |
| `"worker"` | 触发 WorkerAgent 推理（command 插件一般不用这个） |

---

## 三、配置 compose 插件

**适用场景**：你需要一个多容器的实验环境（如 CTF 靶场、网络攻防演练、微服务调试环境）。

### 文件结构

```
config/plugins/my_lab/
├── plugin.yaml              ← 插件定义
├── docker-compose.yml       ← 必填：定义所有容器
├── Dockerfile.attacker      ← 可选：自定义攻击机镜像
├── Dockerfile.target        ← 可选：自定义靶机镜像
└── shared/                  ← 可选：共享文件（挂载到容器）
```

### plugin.yaml 配置

```yaml
plugins:
  - name: "my_lab"
    type: "compose"
    description: |
      我的实验环境
      攻击机可访问靶机内网，通过 /lab_status 查看状态
    compose_file: "docker-compose.yml"       ← 相对于插件目录
    category: "lab"
    icon: "target"
    services:
      # Agent 工具 — 攻击机 shell
      - service_name: "attacker"
        type: "exec"
        agent_type: "worker"
        name: "my_lab_shell"
        description: "实验攻击机 — 可执行任意命令"
        requires_confirmation: true
        entrypoint_cmd: "sh -c"
        bound_action: "execute_command"
        parameters:
          command:
            type: "string"
            description: "要执行的命令"
        required_params: ["command"]

      # 用户命令 — 状态查询
      - service_name: "attacker"
        type: "command"
        agent_type: "none"
        name: "lab_status"
        command_trigger: "/lab_status"
        description: "查看实验环境状态"
        default_command: "echo '实验环境运行中' && ip addr"
        requires_confirmation: false
        entrypoint_cmd: "sh -c"
        parameters:
          command:
            type: "string"
            description: "要执行的命令"
        required_params: ["command"]

      # 辅助容器 — 靶机，不暴露给 Agent
      - service_name: "target1"
        type: "aux"
        description: "靶机 1 — 存放第一关 flag"
```

### type 字段说明（compose 子服务）

| type | 行为 | 前端展示 |
|------|------|---------|
| `exec` | 注册为 Agent 工具，WorkerAgent 可调用 | ToolsView 可见，可启动/停止 |
| `command` | 注册为用户命令，`/xxx` 触发 | ToolsView 可见，聊天框可触发 |
| `aux` | **不注册**，仅作为辅助容器运行 | 前端不可见，纯后台运行 |

---

## 四、配置 local 插件

**适用场景**：你需要一个纯 Python 函数作为 Agent 工具，不需要 Docker 容器。比如调用外部 API、读写本地文件、触发工作流。

### 方式 A：声明式绑定（推荐）

在插件目录中放 handler 文件 + YAML 中声明路径，**零代码修改**：

```
config/plugins/my_translator/
├── plugin.yaml
└── handler.py
```

**handler.py**：
```python
async def translate_handler(text: str, target_lang: str = "en", **kwargs) -> str:
    """调用翻译 API"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.example.com/translate", json={
            "text": text,
            "target": target_lang,
        }) as resp:
            data = await resp.json()
            return data.get("translated", text)
```

**plugin.yaml**：
```yaml
plugins:
  - name: "translate"
    type: "local"
    agent_type: "worker"
    bound_action: "local_call"
    requires_confirmation: false
    handler: "config.plugins.my_translator.handler:translate_handler"  ← 声明式绑定
    description: "翻译工具 — 调用外部翻译 API"
    display_name: "Translator"
    category: "ai"
    icon: "translate"
    parameters:
      text:
        type: "string"
        description: "要翻译的文本"
      target_lang:
        type: "string"
        description: "目标语言代码，默认 en"
    required_params: ["text"]
```

> `handler` 字段格式：`"模块路径:函数名"`，模块路径用 `.` 分隔，函数名在冒号后面。

### 方式 B：手动绑定（兼容旧方式）

在 `src/api/services.py` 的 `_get_or_init_components()` 函数末尾加：

```python
import my_module.handlers
translate_tool = _tool_registry.get_tool("translate")
if translate_tool:
    translate_tool.handler = my_module.handlers.translate_handler
```

---

## 五、导入与管理插件

### 方式 1：手动放置

将插件目录放入 `config/plugins/`，重启服务即可。

### 方式 2：ZIP 导入

在设置页 → 插件配置 tab → 点击"导入插件 (.zip)"按钮。

ZIP 包结构要求：
```
my_plugin.zip
  └── my_plugin/              ← 或直接是 plugin.yaml 在根目录
      ├── plugin.yaml
      ├── docker-compose.yml  ← compose 插件需要
      └── ...
```

导入后自动解压到 `config/plugins/<name>/`，需重启服务生效。

### 方式 3：插件市场（规划中）

从 GitHub 插件市场下载 ZIP 包，通过前端导入。每个插件仓库包含 `plugin.yaml` + 所有依赖文件。

### 管理已安装插件

- **查看**：设置页 → 插件配置 tab → 已安装插件列表
- **删除**：点击插件右侧 × 按钮，确认后删除目录，重启生效

---

## 六、完整字段参考

### 通用字段（所有类型）

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `name` | ✅ | string | 工具名，全局唯一。Agent 用这个名字调用工具 |
| `type` | ✅ | string | `exec` / `command` / `compose` / `local` / `network` |
| `agent_type` | 否 | string | `worker` / `judge` / `curator` / `none`。默认 `worker` |
| `description` | ✅ | string | 工具描述。对 exec 类型，这会被 LLM 看到，影响调用决策 |
| `bound_action` | ✅ | string | FSM 路由：`execute_command` / `local_call` / `stop` |
| `requires_confirmation` | 否 | bool | 是否弹出确认框。默认 `false` |
| `category` | 否 | string | 前端分类：`shell` / `search` / `ai` / `command` / `lab` / `other` |
| `icon` | 否 | string | 前端图标标识 |
| `display_name` | 否 | string | 前端/SSE 显示名。如 `"JudgeAgent"` |

### exec / command 专用字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `container_name` | ✅ | Docker 容器名，全局唯一 |
| `image` | 否 | 首次启动时自动拉取的镜像 |
| `entrypoint_cmd` | ✅ | 容器内入口，通常 `"sh -c"` 或 `"bash -c"` |
| `mount_dirs` | 否 | 挂载目录列表，格式 `["/host:/container:rw"]` |
| `network_mode` | 否 | 网络模式：`"none"`=断网（默认），`"bridge"`=NAT 联网 |
| `privileged` | 否 | 特权模式：`true`=开启（nmap 等需要），默认 `false` |
| `timeout_seconds` | 否 | 命令超时秒数，默认 30（nmap 等慢工具设 120+） |
| `parameters` | ✅ | 工具参数 schema（给 LLM 看） |
| `required_params` | ✅ | 必填参数列表 |

### command 专用字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `command_trigger` | ✅ | 触发词，如 `"/summary"`。用户输入这个触发命令 |
| `default_command` | 否 | 默认命令。用户不传参时执行这个 |

### compose 专用字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `compose_file` | ✅ | docker-compose.yml 的相对路径（相对于插件目录） |
| `services` | ✅ | 子服务列表，每个 service 有 `service_name`、`type`、`name` 等 |

### local 专用字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `handler` | 否 | 声明式绑定：`"模块路径:函数名"`，如 `"config.plugins.my_plugin.handler:my_func"` |
| `param_schema` | 否 | Pydantic 模型路径，如 `"src.agent.types:LocalCallParams"` |

---

## 七、常见问题

### Q：加了 exec 插件但 Agent 不调用它？

检查三个地方：
1. **ToolsView** → 插件是否已启动（status = running）？
2. **Agent 工具配置** → `GET /agent/tools` 检查 `tool_names` 是否包含你的插件名
3. **description 写得够不够清楚** → LLM 根据 description 决定用不用这个工具

### Q：command 插件的 `/xxx` 触发不了？

检查：
1. `command_trigger` 字段必须以 `/` 开头
2. 插件容器必须在运行中（status = running）
3. 点击 ToolsView 的"启动"按钮确保容器运行

### Q：compose 启动后子工具看不到？

检查：
1. `docker compose ps` → 确认所有容器都在运行
2. `type: aux` 的容器不会出现在工具列表（这是预期行为）
3. `service_name` 必须与 docker-compose.yml 中的 service 名完全一致

### Q：可以在一个 plugin.yaml 里定义多个插件共享一个容器吗？

可以。多个 `exec`/`command` 配置指向同一个 `container_name`。例如 `grep_knowledge` 和 `curator` 共享 `kb_container`。

注意：停止其中一个插件会停止共享容器，影响另一个。

### Q：改了 YAML 后需要重启吗？

需要。修改 `plugin.yaml` 或 `plugins.yaml` 后需要重启后端服务。

### Q：如何删除一个插件？

- **插件目录插件**：在设置页 → 插件配置 → 点击 × 删除，或手动删除 `config/plugins/<name>/` 目录
- **主配置插件**：从 `plugins.yaml` 中移除对应配置
- 如果是 compose 插件，先确保容器已停止（`docker compose down`）

### Q：插件需要自定义 Docker 镜像怎么办？

1. 写好 Dockerfile
2. `docker build -t my_image:latest .`
3. 在 YAML 中设置 `image: "my_image:latest"`
4. 对于 compose 插件，在 docker-compose.yml 中用 `build:` 指令

### Q：Kali / 渗透工具无法联网？

添加 `network_mode: "bridge"` 字段（默认是 `"none"` 断网）。

### Q：nmap 报 "Operation not permitted"？

添加 `privileged: true` 字段。nmap 需要 raw socket 权限。

### Q：命令经常超时？

设置 `timeout_seconds` 字段（默认 30 秒）。nmap 等慢工具设为 120 或更高。

### Q：local 插件的 handler 怎么绑定？

**推荐方式**：在 plugin.yaml 中声明 `handler: "模块路径:函数名"`，系统自动导入绑定，无需改代码。

**旧方式**：在 `src/api/services.py` 中手动绑定（仍然兼容）。

### Q：如何导入插件包？

在设置页 → 插件配置 → 点击"导入插件 (.zip)"，选择 ZIP 文件上传。ZIP 中需包含 `plugin.yaml`。导入后重启服务生效。

### Q：如何查看上下文状态？

聊天页 header 点击"上下文"按钮，展开面板查看每条消息的衰减阶段（完整/截断/一行摘要/遗忘）。
