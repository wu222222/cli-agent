"""Agent 类型注册表 — 集中管理所有 Agent 类型的元数据。

加新 Agent 类型只需:
1. 写 Agent 类 + StateMachine + PromptManager 方法
2. 在 agent.py 底部加一行 register_agent(AgentConfig(...))
3. 在 plugins.yaml 里把对应工具的 agent_type 设为新类型名
"""
from dataclasses import dataclass
from typing import Type, Optional, Dict


@dataclass
class AgentConfig:
    """描述一种 Agent 类型的全部元数据"""

    agent_type: str                           # "worker" | "curator" | "judge"

    # 类引用（延迟绑定，注册时可为 None，运行时注入）
    base_class: Optional[Type] = None         # WorkerAgent / CuratorAgent / JudgeAgent
    streaming_wrapper: Optional[Type] = None  # StreamingWorkerAgent 等

    # 状态机 & Prompt
    state_machine_class: Optional[Type] = None
    prompt_method: str = ""                   # PromptManager 上的方法名

    # 工具策略
    tool_filter: str = "config"               # "config" = 外部配置 / "all_matching" = agent_type 匹配 / "fixed"
    fixed_tool_names: Optional[list] = None   # tool_filter="fixed" 时使用

    # 生命周期
    auto_start_containers: bool = False       # 创建前自动启动匹配工具的容器

    # 前端路由
    route_api: str = "/agent/chat"            # ChatView 调哪个 API（/agent/chat | /agent/curator）


# 全局注册表
AGENT_REGISTRY: Dict[str, AgentConfig] = {}


def register_agent(config: AgentConfig):
    """注册一个 Agent 类型"""
    AGENT_REGISTRY[config.agent_type] = config


def get_agent_config(agent_type: str) -> Optional[AgentConfig]:
    """根据 agent_type 字符串获取 AgentConfig"""
    return AGENT_REGISTRY.get(agent_type)


def list_agent_types() -> list:
    """列出所有已注册的 agent_type"""
    return list(AGENT_REGISTRY.keys())
