from typing import Dict, Any, Callable, Optional, List, Union, Awaitable, Type
from pydantic import BaseModel, Field, ValidationError
import json
import shlex
import inspect
import os
import logging

from .types import ActionType, ACTION_SCHEMA_MAP, ValidationError as PydanticValidationError

logger = logging.getLogger("tools")


# --- 执行模式枚举 ---

class ExecutionMode:
    LOCAL = "local"
    EXEC = "exec"
    NETWORK = "network"


# --- 工具基类 ---

class Tool(BaseModel):
    """工具基类 — 自描述"""
    name: str
    description: str
    execution_mode: str = ExecutionMode.LOCAL
    plugin_type: str = "exec"  # exec / command / network / local
    bound_action: ActionType  # 必填
    requires_confirmation: bool = False
    parameters: Dict[str, Any] = Field(default_factory=dict)
    required_params: List[str] = Field(default_factory=list)
    param_schema: Optional[Type[BaseModel]] = None

    class Config:
        arbitrary_types_allowed = True

    def to_dict(self) -> Dict[str, Any]:
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

    def validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.param_schema:
            return params
        try:
            validated = self.param_schema.model_validate(params)
            return validated.model_dump()
        except (ValidationError, PydanticValidationError) as e:
            logger.warning(f"工具 '{self.name}' 参数校验失败: {e}")
            return params

    def format_start(self, params: Dict[str, Any]) -> str:
        return f"正在执行: {self.name}"

    def format_result(self, raw_content: str) -> str:
        return raw_content

    async def run(self, **params) -> str:
        raise NotImplementedError("子类必须实现 run 方法")


# --- Type 1: 本地工具 ---

class LocalTool(Tool):
    execution_mode: str = ExecutionMode.LOCAL
    handler: Optional[Union[Callable[..., Any], Callable[..., Awaitable[Any]]]] = None

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
            return f"错误: 执行异常 - {str(e)}"


# --- Type 2: Exec 容器插件 ---

class ExecContainerPlugin(Tool):
    execution_mode: str = ExecutionMode.EXEC
    container_name: str = ""
    entrypoint_cmd: str = "sh -c"
    mount_dirs: List[str] = Field(default_factory=list)  # 挂载目录列表
    default_command: str = ""  # command 插件的默认命令
    command_trigger: str = ""  # command 插件的触发器（如 /ctf_status）
    _container: Any = None

    class Config:
        arbitrary_types_allowed = True

    def bind_container(self, container) -> None:
        self._container = container

    def format_start(self, params: Dict[str, Any]) -> str:
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
                    timeout=30,
                )
            except asyncio.TimeoutError:
                logger.warning(f"ExecContainerPlugin '{self.name}' 执行超时 (30s)")
                return f"错误: 命令执行超时 (30秒)。命令可能遍历了过大的文件系统。请缩小搜索范围。"

            stdout = output.decode('utf-8', errors='replace') if output else ""

            if exit_code != 0:
                logger.warning(f"插件 '{self.name}' 退出码: {exit_code}")
                return f"EXIT_CODE: {exit_code}\nSTDOUT: {stdout}\nSTDERR: "

            return stdout.strip()

        except Exception as e:
            logger.error(f"ExecContainerPlugin '{self.name}' 执行异常: {e}")
            return f"错误: 容器执行异常 - {str(e)}"


# --- Type 3: Network 容器插件（预留） ---

class NetworkContainerPlugin(Tool):
    execution_mode: str = ExecutionMode.NETWORK
    endpoint_url: str = ""
    port_bindings: Dict[int, int] = Field(default_factory=dict)

    def format_start(self, params: Dict[str, Any]) -> str:
        return f"正在调用网络服务: {self.name} ({self.endpoint_url})"

    async def run(self, **params) -> str:
        return f"错误: NetworkContainerPlugin 尚未实现"


# --- Compose 组插件 ---

class ComposePlugin:
    """管理一个 docker compose 项目，子容器可注册为 ExecContainerPlugin"""

    def __init__(
        self,
        name: str,
        description: str,
        compose_file: str,
        children_config: List[Dict[str, Any]],
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
        self._registered_children: Dict[str, Tool] = {}  # tool_name -> Tool

    async def up(self) -> tuple[bool, str]:
        """docker compose up -d --build"""
        import subprocess, os
        abs_path = os.path.abspath(self.compose_file).replace("\\", "/")
        if not os.path.exists(abs_path):
            return False, f"compose 文件不存在: {abs_path}"
        try:
            result = subprocess.run(
                ["docker", "compose", "-p", self.name, "-f", abs_path, "up", "-d", "--build"],
                capture_output=True, text=True, timeout=120,
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
        import subprocess, os
        abs_path = os.path.abspath(self.compose_file).replace("\\", "/")
        cmd = ["docker", "compose", "-p", self.name, "-f", abs_path, "down"]
        if volumes:
            cmd.append("-v")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
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

    def bind_children(self, docker_client, tool_registry: 'ToolRegistry') -> List[str]:
        """将子容器绑定为 Tool 并注册到 ToolRegistry，返回注册的工具名列表"""
        import docker.errors
        registered = []
        for child_cfg in self.children_config:
            child_type = child_cfg.get('type', 'exec')
            if child_type not in ('exec', 'command'):
                continue
            # exec 类型默认注册，除非 register: false
            # command 类型始终注册（用户命令插件）
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
                execution_mode=ExecutionMode.EXEC,
                plugin_type=child_type,
                bound_action=ActionType.EXECUTE_COMMAND,
                requires_confirmation=child_cfg.get('requires_confirmation', False),
                container_name=container_name,
                entrypoint_cmd=child_cfg.get('entrypoint_cmd', 'sh -c'),
                parameters=child_cfg.get('parameters', {}),
                required_params=child_cfg.get('required_params', []),
                mount_dirs=child_cfg.get('mount_dirs', []),
                default_command=child_cfg.get('default_command', ''),
                command_trigger=child_cfg.get('command_trigger', ''),
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


# --- 内置工具 ---

class CallJudgeTool(LocalTool):
    """call_judge 工具 — 绑定到 LOCAL_CALL"""
    bound_action: ActionType = ActionType.LOCAL_CALL

    def __init__(self, **data):
        super().__init__(**data)
        from .types import LocalCallParams
        self.param_schema = LocalCallParams

    def format_start(self, params: Dict[str, Any]) -> str:
        answer = params.get('final_answer', '')
        evidence = params.get('evidence_summary', '')
        lines = ["正在调用 JudgeAgent 进行评审..."]
        if answer:
            lines.append(f"待评审答案: {answer}")
        if evidence:
            lines.append(f"证据摘要: {evidence}")
        return "\n".join(lines)

    def format_result(self, raw_content: str) -> str:
        import re
        obs_match = re.search(r"observation='(.*?)'", raw_content)
        action_match = re.search(r"action_type='(.*?)'", raw_content)
        if obs_match:
            obs = obs_match.group(1)
            action = action_match.group(1) if action_match else ""
            return f"评审意见: {obs}" + (f"\n处理方式: {action}" if action else "")
        return raw_content


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
        self._tools: Dict[str, Tool] = {}
        self._compose_plugins: Dict[str, ComposePlugin] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        self.register(CallJudgeTool(
            name="call_judge",
            description="调用 JudgeAgent 评审结果合理性",
            bound_action=ActionType.LOCAL_CALL,
            parameters={
                "final_answer": {"type": "string", "description": "最终准备给用户的判断结果"},
                "evidence_summary": {"type": "string", "description": "简述你得出此结论的证据链（可选）"}
            },
            required_params=["final_answer"],
        ))

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get_tool(self, name: str) -> Optional[Tool]:
        # 大小写不敏感查找
        tool = self._tools.get(name)
        if tool:
            return tool
        return self._tools.get(name.lower())

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def get_all_tools(self) -> List[Dict[str, Any]]:
        return [tool.to_dict() for tool in self._tools.values()]

    def resolve_action(self, tool_name: str) -> Optional[ActionType]:
        tool = self.get_tool(tool_name)
        if tool:
            return tool.bound_action
        return None

    def get_tools_by_mode(self, mode: str) -> List[Tool]:
        return [t for t in self._tools.values() if t.execution_mode == mode]

    def register_compose(self, compose: 'ComposePlugin') -> None:
        self._compose_plugins[compose.name] = compose

    def get_compose(self, name: str) -> Optional['ComposePlugin']:
        return self._compose_plugins.get(name)

    def list_compose(self) -> List[str]:
        return list(self._compose_plugins.keys())

    def load_from_yaml(self, path: str, docker_client=None) -> None:
        if not os.path.exists(path):
            logger.warning(f"插件配置文件不存在: {path}")
            return

        try:
            import yaml
        except ImportError:
            logger.error("需要安装 pyyaml: pip install pyyaml")
            return

        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        for plugin_cfg in config.get('plugins', []):
            self._load_plugin(plugin_cfg, docker_client)

    def _load_plugin(self, cfg: Dict[str, Any], docker_client=None) -> None:
        plugin_type = cfg.get('type', 'local')
        name = cfg.get('name', '')
        description = cfg.get('description', '')
        parameters = cfg.get('parameters', {})
        required_params = cfg.get('required_params', [])
        requires_confirmation = cfg.get('requires_confirmation', False)
        bound_action_str = cfg.get('bound_action', 'execute_command')
        mount_dirs = cfg.get('mount_dirs', [])

        bound_action = ActionType.EXECUTE_COMMAND
        try:
            bound_action = ActionType(bound_action_str)
        except ValueError:
            logger.warning(f"插件 '{name}' 的 bound_action '{bound_action_str}' 无效，使用默认 EXECUTE_COMMAND")

        if plugin_type in ('exec', 'command'):
            container_name = cfg.get('container_name', '')
            entrypoint_cmd = cfg.get('entrypoint_cmd', 'sh -c')

            plugin = ExecContainerPlugin(
                name=name,
                description=description,
                parameters=parameters,
                required_params=required_params,
                requires_confirmation=requires_confirmation,
                bound_action=bound_action,
                container_name=container_name,
                entrypoint_cmd=entrypoint_cmd,
                mount_dirs=mount_dirs,
            )
            plugin.plugin_type = plugin_type
            if plugin_type == 'command':
                plugin.default_command = cfg.get('default_command', '')
                plugin.command_trigger = cfg.get('command_trigger', '')

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
                parameters=parameters,
                required_params=required_params,
                requires_confirmation=requires_confirmation,
                bound_action=bound_action,
                endpoint_url=endpoint_url,
                port_bindings=port_bindings,
            )
            self.register(plugin)
            logger.info(f"已注册 network 插件: {name}")

        elif plugin_type == 'compose':
            compose_file = cfg.get('compose_file', '')
            children = cfg.get('plugins', [])
            compose = ComposePlugin(
                name=name,
                description=description,
                compose_file=compose_file,
                children_config=children,
                category=cfg.get('category', 'other'),
                icon=cfg.get('icon', 'default'),
            )
            self.register_compose(compose)
            logger.info(f"已注册 compose 插件: {name} (子工具: {len(children)} 个)")

        elif plugin_type == 'local':
            logger.info(f"跳过 local 插件（需代码中注册）: {name}")

        else:
            logger.warning(f"未知插件类型: {plugin_type} ({name})")

    async def run(self, name: str, params: Dict[str, Any]) -> str:
        tool = self.get_tool(name)
        if not tool:
            return f"错误: 未找到工具 '{name}'"

        params = tool.validate_params(params)
        return await tool.run(**params)
