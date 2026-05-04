任务描述： 为前端增加新功能，将docker容器的config stragey config 都支持前端输入，刚启动网站弹出个初始化页面支持输入docker参数，可以在后端预定义好几个默认的image选项 （比如 my_lab_image ， alpine_image）

-- 请你实现功能后在下方更新内容，简述你的更新日志 --

### 更新日志

#### 后端

**`src/api/models.py`** — 新增模型
- `DockerPreset`: 预定义镜像选项（name, image, description）
- `DockerConfigRequest`: Docker 配置请求（image, container_name, network, memory_limit, timeout, use_host_workspace, use_knowledge_base, kb_mode）
- `DockerConfigResponse`: 包含 presets 列表和当前配置

**`src/api/services.py`** — 配置管理
- 新增 `DOCKER_PRESETS` 列表：Alpine Linux、Ubuntu、Debian、CentOS 四个预定义选项
- 新增 `_docker_config` 全局变量存储当前配置
- 新增 `get_docker_config()`, `get_presets()`, `update_docker_config()` 函数
- `update_docker_config()` 更新配置并重置组件，下次请求时用新配置重新初始化
- `_get_or_init_components()` 现在使用 `_docker_config` 创建 DockerConfig

**`src/api/routes.py`** — 新增端点
- `GET /config/docker` — 获取预定义选项和当前配置
- `POST /config/docker` — 更新 Docker 配置

#### 前端

**`frontend/src/views/SetupView.vue`** — 新建初始化页面
- 镜像选择：卡片式预设选择 + 自定义镜像输入
- 容器配置：容器名称、网络模式、内存限制、命令超时
- 存储配置：工作目录挂载、知识库挂载及权限
- 点击"开始使用"提交配置并跳转到聊天页面

**`frontend/src/api/config.ts`** — 新建配置 API
- `getDockerConfig()` — GET /config/docker
- `updateDockerConfig()` — POST /config/docker

**`frontend/src/types/index.ts`** — 新增类型
- `DockerPreset`, `DockerConfigForm`

**`frontend/src/router/index.ts`** — 新增路由
- `/setup` → SetupView

**`frontend/src/views/ChatView.vue`** — 聊天页 header 新增 "Docker" 按钮跳转到配置页

#### 验证
- TypeScript 检查通过
- 生产构建成功
- 后端导入正常
