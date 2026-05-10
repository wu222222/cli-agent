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

            exit_code, output = self._container.exec_run(
                ["sh", "-c", full_cmd],
                detach=False,
                stdout=True,
                stderr=True,
            )

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
