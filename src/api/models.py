from pydantic import BaseModel
from typing import Optional, List


class ChatRequest(BaseModel):
    message: str
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


class DockerPreset(BaseModel):
    name: str
    image: str
    description: str


class DockerConfigRequest(BaseModel):
    image: str = "alpine:latest"
    container_name: str = "cli_agent_sandbox"
    network: str = "none"
    memory_limit: str = "512m"
    timeout: int = 30
    use_host_workspace: bool = False
    use_knowledge_base: bool = True
    kb_mode: str = "ro"


class DockerConfigResponse(BaseModel):
    presets: List[DockerPreset]
    current: DockerConfigRequest
