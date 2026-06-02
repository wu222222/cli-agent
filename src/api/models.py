from typing import Any

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str = ""
    confirmed: bool | None = False
    session_id: str | None = None


class ChatResponse(BaseModel):
    request_id: str
    content: str = ""
    thought: str | None = ""
    type: str = "text"
    agent: str = "WorkerAgent"


class CuratorRequest(BaseModel):
    task: str


class HealthResponse(BaseModel):
    status: str = "healthy"


class PluginInfo(BaseModel):
    name: str
    description: str
    plugin_type: str = "exec"  # exec / command / compose / local / network（唯一类型标识）
    agent_type: str = "worker"  # worker / judge / curator / none
    container_name: str = ""
    status: str = "unknown"
    bound_action: str | None = None
    requires_confirmation: bool = False
    mount_dirs: list[str] = []
    parameters: dict[str, Any] | None = None
    required_params: list[str] | None = None
    # 前端展示（直接从 Tool 对象读取，不再重读 YAML）
    category: str = "other"
    icon: str = "default"
    command_trigger: str = ""
    display_name: str = ""
    # compose 子工具标识
    parent_compose: str | None = None


class ComposePluginInfo(BaseModel):
    """Compose 组插件信息"""
    name: str
    description: str
    compose_file: str
    running: bool = False
    category: str = "other"
    icon: str = "default"
    children: list[PluginInfo] = []
    has_regenerate: bool = False


class PluginActionResponse(BaseModel):
    success: bool
    message: str
