import inspect
import json
import logging
import os
import shlex
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from .types import ActionType

logger = logging.getLogger("tools")


# --- 工具基类 ---

class Tool(BaseModel):
    """工具基类 — 自描述，一条 YAML 描述全部行为"""
    # === 身份 ===
    name: str
    description: str
    plugin_type: str = "exec"   # exec / command / compose / local / network（唯一类型标识）

    # === Agent 绑定 ===
    agent_type: str = "worker"  # 对应 AGENT_REGISTRY: worker / judge / curator / none

    # === FSM 路由 ===
    bound_action: ActionType  # 必填
    requires_confirmation: bool = False

    # === 工具 Schema（给 LLM 看） ===
    parameters: dict[str, Any] = Field(default_factory=dict)
    required_params: list[str] = Field(default_factory=list)
    param_schema: type[BaseModel] | None = None

    # === 前端展示（从 YAML 缓存） ===
    category: str = "other"
    icon: str = "default"
    command_trigger: str = ""           # 仅 command 类型使用
    display_name: str = ""              # 前端/SSE 显示名（如 call_judge 显示为 "JudgeAgent"）

    # === Docker 执行 ===
    container_name: str = ""
    entrypoint_cmd: str = "sh -c"
    mount_dirs: list[str] = Field(default_factory=list)
    network_mode: str = "none"          # "none"=断网（默认安全）, "bridge"=NAT联网
    privileged: bool = False            # True=特权模式（nmap等需要raw socket的工具）
    timeout_seconds: int = 30           # 命令执行超时（秒），nmap 等慢工具设为更大值

    # === 扩展钩子（方案 C 填充实现） ===
    _on_register: Callable | None = None     # async (tool, registry, manager) -> None
    _on_unregister: Callable | None = None   # async (tool, registry) -> None

    class Config:
        arbitrary_types_allowed = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required_params
                }
            }
        }

    @property
    def is_command_plugin(self) -> bool:
        """command 类型插件不暴露给 LLM function-calling"""
        return self.plugin_type == "command"

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        if not self.param_schema:
            return params
        try:
            validated = self.param_schema.model_validate(params)
            return validated.model_dump()
        except ValidationError as e:
            logger.warning(f"工具 '{self.name}' 参数校验失败: {e}")
            return params

    def format_start(self, params: dict[str, Any]) -> str:
        return f"正在执行: {self.name}"

    def format_result(self, raw_content: str) -> str:
        return raw_content

    async def run(self, **params) -> str:
        raise NotImplementedError("子类必须实现 run 方法")


# --- Type 1: 本地工具 ---

class LocalTool(Tool):
    plugin_type: str = "local"
    handler: Callable[..., Any] | Callable[..., Awaitable[Any]] | None = None

    async def run(self, **params) -> str:
        if not self.handler:
            return f"错误: 工具 '{self.name}' 未绑定 handler"
        try:
            if inspect.iscoroutinefunction(self.handler):
                result = await self.handler(**params)
            else:
                result = self.handler(**params)
            return str(result)
        except Exception as e:
            logger.error(f"LocalTool '{self.name}' 执行异常: {e}")
            return f"错误: 执行异常 - {e!s}"


# --- Type 2: Exec 容器插件 ---

class ExecContainerPlugin(Tool):
    plugin_type: str = "exec"
    container_name: str = ""
    entrypoint_cmd: str = "sh -c"
    mount_dirs: list[str] = Field(default_factory=list)  # 挂载目录列表
    default_command: str = ""  # command 插件的默认命令
    _container: Any = None

    class Config:
        arbitrary_types_allowed = True

    def bind_container(self, container) -> None:
        self._container = container

    def format_start(self, params: dict[str, Any]) -> str:
        cmd = params.get('command', '')
        if cmd:
            return f"正在执行命令: {cmd}"
        return f"正在调用插件: {self.name}"

    def format_result(self, raw_content: str) -> str:
        return _format_shell_output(raw_content)

    async def run(self, **params) -> str:
        if not self._container:
            return (
                f"错误: 工具 '{self.name}' 的容器 '{self.container_name}' 未绑定或未运行。"
                f"请在工具设置页面启动对应容器。"
            )
        try:
            cmd = params.get("command", "")
            if cmd:
                full_cmd = f"{self.entrypoint_cmd} {shlex.quote(cmd)}"
            else:
                json_data = json.dumps(params, ensure_ascii=False)
                safe_json = shlex.quote(json_data)
                full_cmd = f"{self.entrypoint_cmd} --json-data {safe_json}"

            logger.info(f"ExecContainerPlugin '{self.name}' 执行: {full_cmd[:100]}...")

            import asyncio
            loop = asyncio.get_running_loop()
            try:
                exit_code, output = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self._container.exec_run(
                            ["sh", "-c", full_cmd],
                            detach=False,
                            stdout=True,
                            stderr=True,
                        )
                    ),
                    timeout=self.timeout_seconds,
                )
            except asyncio.TimeoutError:
                logger.warning(f"ExecContainerPlugin '{self.name}' 执行超时 ({self.timeout_seconds}s)")
                return f"错误: 命令执行超时 ({self.timeout_seconds}秒)。"

            stdout = output.decode('utf-8', errors='replace') if output else ""

            if exit_code != 0:
                logger.warning(f"插件 '{self.name}' 退出码: {exit_code}")
                return f"EXIT_CODE: {exit_code}\nSTDOUT: {stdout}\nSTDERR: "

            return stdout.strip()

        except Exception as e:
            logger.error(f"ExecContainerPlugin '{self.name}' 执行异常: {e}")
            return f"错误: 容器执行异常 - {e!s}"


# --- Type 3: Network 容器插件（预留） ---

class NetworkContainerPlugin(Tool):
    plugin_type: str = "network"
    endpoint_url: str = ""
    port_bindings: dict[int, int] = Field(default_factory=dict)

    def format_start(self, params: dict[str, Any]) -> str:
        return f"正在调用网络服务: {self.name} ({self.endpoint_url})"

    async def run(self, **params) -> str:
        return "错误: NetworkContainerPlugin 尚未实现"


# --- Compose 组插件 ---

class ComposePlugin:
    """管理一个 docker compose 项目，子容器可注册为 ExecContainerPlugin"""

    def __init__(
        self,
        name: str,
        description: str,
        compose_file: str,
        children_config: list[dict[str, Any]],
        category: str = "other",
        icon: str = "default",
    ):
        self.name = name
        self.description = description
        self.compose_file = compose_file
        self.children_config = children_config  # 子插件配置列表
        self.category = category
        self.icon = icon
        self.running: bool = False
        self._registered_children: dict[str, Tool] = {}  # tool_name -> Tool

    async def up(self) -> tuple[bool, str]:
        """docker compose up -d --build"""
        import os
        import subprocess
        compose_dir = os.path.dirname(os.path.abspath(self.compose_file))
        compose_file = os.path.join(compose_dir, os.path.basename(self.compose_file))
        if not os.path.exists(compose_file):
            return False, f"compose file not found: {compose_file}"
        try:
            result = subprocess.run(
                ["docker", "compose", "-p", self.name, "-f", compose_file, "up", "-d", "--build"],
                capture_output=True, text=True, timeout=180,
                cwd=compose_dir,
            )
            if result.returncode == 0:
                self.running = True
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)

    async def down(self, volumes: bool = False) -> tuple[bool, str]:
        """docker compose down [-v]"""
        import os
        import subprocess
        compose_dir = os.path.dirname(os.path.abspath(self.compose_file))
        compose_file = os.path.join(compose_dir, os.path.basename(self.compose_file))
        cmd = ["docker", "compose", "-p", self.name, "-f", compose_file, "down"]
        if volumes:
            cmd.append("-v")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
                cwd=compose_dir,
            )
            if result.returncode == 0:
                self.running = False
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)

    async def reset(self) -> tuple[bool, str]:
        """down -v + up"""
        ok, msg = await self.down(volumes=True)
        if not ok:
            return False, f"down 失败: {msg}"
        return await self.up()

    def bind_children(self, docker_client, tool_registry: 'ToolRegistry') -> list[str]:
        """将子容器绑定为 Tool 并注册到 ToolRegistry，返回注册的工具名列表"""
        import docker.errors
        registered = []
        for child_cfg in self.children_config:
            # type 字段 (与顶层插件同构): exec / command / aux
            child_type = child_cfg.get('type', None)
            if child_type is None:
                # 旧版兼容: role 字段
                child_type = child_cfg.get('role', 'exec')
            if child_type == 'aux':
                logger.info(f"Compose aux container '{child_cfg.get('service_name')}' skipped (type=aux)")
                continue
            if child_type not in ('exec', 'command'):
                continue
            # 旧版 register: false 兼容
            if child_type == 'exec' and not child_cfg.get('register', True):
                continue

            service_name = child_cfg.get('service_name', '')
            if not service_name:
                continue

            # compose 容器名格式: {project}_{service}_{index} 或 {project}-{service}-{index}
            container_name_v1 = f"{self.name}_{service_name}_1"
            container_name_v2 = f"{self.name}-{service_name}-1"
            container = None
            for cname in (container_name_v1, container_name_v2):
                try:
                    container = docker_client.containers.get(cname)
                    container_name = cname
                    break
                except docker.errors.NotFound:
                    continue
            if not container:
                logger.warning(f"Compose 子容器未找到: {container_name_v1} 或 {container_name_v2}")
                continue

            child_tool = ExecContainerPlugin(
                name=child_cfg['name'],
                description=child_cfg.get('description', ''),
                plugin_type=child_type,
                agent_type=child_cfg.get('agent_type', 'none' if child_type == 'command' else 'worker'),
                bound_action=ActionType.EXECUTE_COMMAND,
                requires_confirmation=child_cfg.get('requires_confirmation', False),
                container_name=container_name,
                entrypoint_cmd=child_cfg.get('entrypoint_cmd', 'sh -c'),
                parameters=child_cfg.get('parameters', {}),
                required_params=child_cfg.get('required_params', []),
                mount_dirs=child_cfg.get('mount_dirs', []),
                default_command=child_cfg.get('default_command', ''),
                command_trigger=child_cfg.get('command_trigger', ''),
                category=child_cfg.get('category', 'other'),
                icon=child_cfg.get('icon', 'default'),
                display_name=child_cfg.get('display_name', ''),
                network_mode=child_cfg.get('network_mode', 'none'),
                privileged=child_cfg.get('privileged', False),
                timeout_seconds=child_cfg.get('timeout_seconds', 30),
            )
            child_tool.bind_container(container)
            child_tool._parent_compose = self.name
            tool_registry.register(child_tool)
            self._registered_children[child_tool.name] = child_tool
            registered.append(child_tool.name)
            logger.info(f"Compose 子工具已注册: {child_tool.name} -> {container_name}")
        return registered

    def unbind_children(self, tool_registry: 'ToolRegistry'):
        """从 ToolRegistry 注销所有子工具"""
        for name in self._registered_children:
            tool_registry.unregister(name)
            logger.info(f"Compose 子工具已注销: {name}")
        self._registered_children.clear()


# --- 通用辅助 ---

def _import_class(path: str):
    """动态导入类，格式: 'module.path:ClassName'"""
    module_path, class_name = path.rsplit(':', 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)

# --- 通用格式化辅助 ---

def _format_shell_output(raw_content: str) -> str:
    lines = []
    in_stdout = False
    for line in raw_content.split("\n"):
        if line.startswith("EXIT_CODE:"):
            lines.append(line)
            in_stdout = False
        elif line.startswith("STDOUT:"):
            lines.append("输出:")
            stdout = line[len("STDOUT:"):].strip()
            if stdout:
                lines.append(stdout)
            in_stdout = True
        elif line.startswith("STDERR:"):
            stderr = line[len("STDERR:"):].strip()
            if stderr:
                lines.append(f"错误: {stderr}")
            in_stdout = False
        elif in_stdout:
            lines.append(line)
    return "\n".join(lines) if lines else raw_content


# --- 工具注册表 ---

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._compose_plugins: dict[str, ComposePlugin] = {}
        self._tool_to_compose: dict[str, str] = {}  # 子工具名 -> compose 插件名

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get_tool(self, name: str) -> Tool | None:
        # 大小写不敏感查找
        tool = self._tools.get(name)
        if tool:
            return tool
        return self._tools.get(name.lower())

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_all_tools(self) -> list[dict[str, Any]]:
        return [tool.to_dict() for tool in self._tools.values()]

    def resolve_action(self, tool_name: str) -> ActionType | None:
        tool = self.get_tool(tool_name)
        if tool:
            return tool.bound_action
        return None

    def get_tools_by_type(self, plugin_type: str) -> list[Tool]:
        return [t for t in self._tools.values() if getattr(t, 'plugin_type', '') == plugin_type]

    def register_compose(self, compose: 'ComposePlugin') -> None:
        self._compose_plugins[compose.name] = compose

    def get_compose(self, name: str) -> Optional['ComposePlugin']:
        return self._compose_plugins.get(name)

    def list_compose(self) -> list[str]:
        return list(self._compose_plugins.keys())

    def get_compose_for_tool(self, tool_name: str) -> str | None:
        """获取工具对应的 compose 插件名（从配置映射中查找）"""
        return self._tool_to_compose.get(tool_name)

    def load_from_yaml(self, path: str, docker_client=None, base_dir: str = None) -> None:
        if not os.path.exists(path):
            logger.warning(f"插件配置文件不存在: {path}")
            return

        try:
            import yaml
        except ImportError:
            logger.error("需要安装 pyyaml: pip install pyyaml")
            return

        with open(path, encoding='utf-8') as f:
            config = yaml.safe_load(f)

        for plugin_cfg in config.get('plugins', []):
            # compose_file 路径修正：相对于 plugin.yaml 所在目录
            if base_dir and plugin_cfg.get('compose_file'):
                plugin_cfg = dict(plugin_cfg)
                plugin_cfg['compose_file'] = os.path.join(base_dir, plugin_cfg['compose_file'])
            self._load_plugin(plugin_cfg, docker_client)

    def load_from_directory(self, plugins_dir: str, docker_client=None) -> int:
        """扫描 plugins/ 目录，加载所有子目录中的 plugin.yaml"""
        if not os.path.isdir(plugins_dir):
            return 0

        loaded = 0
        for entry in sorted(os.listdir(plugins_dir)):
            entry_path = os.path.join(plugins_dir, entry)
            if not os.path.isdir(entry_path):
                continue
            plugin_yaml = os.path.join(entry_path, "plugin.yaml")
            if os.path.isfile(plugin_yaml):
                self.load_from_yaml(plugin_yaml, docker_client=docker_client, base_dir=entry_path)
                loaded += 1
                logger.info(f"从目录加载插件: {entry}")
        return loaded

    def _load_plugin(self, cfg: dict[str, Any], docker_client=None) -> None:
        plugin_type = cfg.get('type', 'local')
        name = cfg.get('name', '')
        description = cfg.get('description', '')
        parameters = cfg.get('parameters', {})
        required_params = cfg.get('required_params', [])
        requires_confirmation = cfg.get('requires_confirmation', False)
        bound_action_str = cfg.get('bound_action', 'execute_command')
        mount_dirs = cfg.get('mount_dirs', [])

        # === YAML 元数据缓存 ===
        agent_type = cfg.get('agent_type', 'worker')
        category = cfg.get('category', 'other')
        icon = cfg.get('icon', 'default')
        command_trigger = cfg.get('command_trigger', '')
        display_name = cfg.get('display_name', '')

        bound_action = ActionType.EXECUTE_COMMAND
        try:
            bound_action = ActionType(bound_action_str)
        except ValueError:
            logger.warning(f"插件 '{name}' 的 bound_action '{bound_action_str}' 无效，使用默认 EXECUTE_COMMAND")

        if plugin_type in ('exec', 'command'):
            container_name = cfg.get('container_name', '')
            entrypoint_cmd = cfg.get('entrypoint_cmd', 'sh -c')

            network_mode = cfg.get('network_mode', 'none')
            privileged = cfg.get('privileged', False)

            plugin = ExecContainerPlugin(
                name=name,
                description=description,
                plugin_type=plugin_type,
                agent_type=agent_type,
                bound_action=bound_action,
                requires_confirmation=requires_confirmation,
                parameters=parameters,
                required_params=required_params,
                container_name=container_name,
                entrypoint_cmd=entrypoint_cmd,
                mount_dirs=mount_dirs,
                network_mode=network_mode,
                privileged=privileged,
                timeout_seconds=cfg.get('timeout_seconds', 30),
                category=category,
                icon=icon,
                command_trigger=command_trigger,
                display_name=display_name,
            )
            if plugin_type == 'command':
                plugin.default_command = cfg.get('default_command', '')

            if docker_client:
                try:
                    container = docker_client.containers.get(container_name)
                    if container.status == 'running':
                        plugin.bind_container(container)
                        logger.info(f"插件 '{name}' 已绑定容器: {container_name}")
                    else:
                        logger.warning(f"插件 '{name}' 容器未运行: {container_name}")
                except Exception as e:
                    logger.warning(f"插件 '{name}' 容器未找到: {container_name} ({e})")

            self.register(plugin)
            logger.info(f"已注册 {plugin_type} 插件: {name} -> {container_name}")

        elif plugin_type == 'network':
            endpoint_url = cfg.get('endpoint_url', '')
            port_bindings = cfg.get('port_bindings', {})
            plugin = NetworkContainerPlugin(
                name=name,
                description=description,
                plugin_type="network",
                agent_type=agent_type,
                bound_action=bound_action,
                requires_confirmation=requires_confirmation,
                parameters=parameters,
                required_params=required_params,
                endpoint_url=endpoint_url,
                port_bindings=port_bindings,
                category=category,
                icon=icon,
            )
            self.register(plugin)
            logger.info(f"已注册 network 插件: {name}")

        elif plugin_type == 'compose':
            compose_file = cfg.get('compose_file', '')
            # 兼容新旧字段名: services（新）优先，plugins（旧）fallback
            children = cfg.get('services')
            if children is None:
                children = cfg.get('plugins', [])
                if children:
                    logger.info(f"Compose '{name}' 使用旧字段 'plugins:'，建议迁移到 'services:'")
            compose = ComposePlugin(
                name=name,
                description=description,
                compose_file=compose_file,
                children_config=children,
                category=cfg.get('category', 'other'),
                icon=cfg.get('icon', 'default'),
            )
            self.register_compose(compose)
            # 建立子工具名到 compose 名的映射
            for child in children:
                child_name = child.get('name', '')
                if child_name:
                    self._tool_to_compose[child_name] = name
            logger.info(f"已注册 compose 插件: {name} (子服务: {len(children)} 个)")

        elif plugin_type == 'local':
            # 从 YAML 加载 local 插件（不再需要代码中注册）
            param_schema_cls = None
            param_schema_path = cfg.get('param_schema', '')
            if param_schema_path:
                try:
                    param_schema_cls = _import_class(param_schema_path)
                except Exception as e:
                    logger.warning(f"local 插件 '{name}' 无法加载 param_schema '{param_schema_path}': {e}")

            plugin = LocalTool(
                name=name,
                description=description,
                plugin_type="local",
                agent_type=agent_type,
                bound_action=bound_action,
                requires_confirmation=requires_confirmation,
                parameters=parameters,
                required_params=required_params,
                param_schema=param_schema_cls,
                category=category,
                icon=icon,
                display_name=display_name or name,
            )
            # 声明式 handler 绑定：handler: "module.path:func_name"
            handler_path = cfg.get('handler', '')
            if handler_path:
                try:
                    module_path, func_name = handler_path.rsplit(':', 1)
                    import importlib
                    mod = importlib.import_module(module_path)
                    plugin.handler = getattr(mod, func_name)
                    logger.info(f"local 插件 '{name}' handler 已绑定: {handler_path}")
                except Exception as e:
                    logger.warning(f"local 插件 '{name}' handler 绑定失败 '{handler_path}': {e}")
            self.register(plugin)
            logger.info(f"已注册 local 插件: {name} (agent_type={agent_type})")

        else:
            logger.warning(f"未知插件类型: {plugin_type} ({name})")

    async def run(self, name: str, params: dict[str, Any]) -> str:
        tool = self.get_tool(name)
        if not tool:
            return f"错误: 未找到工具 '{name}'"

        params = tool.validate_params(params)
        return await tool.run(**params)
