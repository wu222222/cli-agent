from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    message: str = ""
    confirmed: Optional[bool] = False


class ChatResponse(BaseModel):
    request_id: str
    content: str = ""
    thought: Optional[str] = ""
    type: str = "text"
    agent: str = "WorkerAgent"


class CuratorRequest(BaseModel):
    task: str


class HealthResponse(BaseModel):
    status: str = "healthy"


class PluginInfo(BaseModel):
    name: str
    description: str
    tool_type: str  # execution_mode: local / exec / network
    plugin_type: str = "exec"  # exec / command / local
    container_name: str = ""
    status: str = "unknown"
    bound_action: Optional[str] = None
    requires_confirmation: bool = False
    mount_dirs: List[str] = []
    parameters: Optional[Dict[str, Any]] = None
    required_params: Optional[List[str]] = None
    # 预设相关字段
    category: str = "other"
    icon: str = "default"
    # compose 子工具标识
    parent_compose: Optional[str] = None


class ComposePluginInfo(BaseModel):
    """Compose 组插件信息"""
    name: str
    description: str
    compose_file: str
    running: bool = False
    category: str = "other"
    icon: str = "default"
    children: List[PluginInfo] = []


class PluginActionResponse(BaseModel):
    success: bool
    message: str
