from pydantic import BaseModel, Field, ValidationError
from typing import Dict, Any, Optional, Type, Literal, List, Tuple
from enum import Enum


class ActionType(Enum):
    """动作类型枚举 — 最小化、通用化，仅用于状态机路由

    - EXECUTE_COMMAND: exec/network 模式工具（容器执行）
    - LOCAL_CALL: local 模式工具（本地函数调用）
    - STOP: 停止并返回答案

    具体工具名（execute_command, call_judge, alpine_shell 等）通过 Tool.bound_action 映射到以上枚举。
    """
    EXECUTE_COMMAND = "execute_command"
    LOCAL_CALL = "local_call"
    STOP = "stop"

    @classmethod
    def from_raw(cls, raw_type: str) -> Tuple["ActionType", bool]:
        try:
            return cls(raw_type), True
        except ValueError:
            return cls.STOP, False


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING_CONFIRMATION = "waiting_confirmation"
    COMPLETED = "completed"
    ERROR = "error"


class LLMAction(BaseModel):
    """对应 Prompt 中的 action 部分"""
    type: str
    tool_name: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)


class LLMOutput(BaseModel):
    """对应 Prompt 中的整体 JSON 结构"""
    thought: str
    action: LLMAction


class AgentResponse(BaseModel):
    thought: str
    content: str
    action_type: ActionType
    action_params: Dict[str, Any]
    tool_name: str = ""

    class Config:
        arbitrary_types_allowed = True

    def validate_params(self, tool_param_schema=None):
        # 如果有工具的独立 schema，优先使用
        schema_class = tool_param_schema or ACTION_SCHEMA_MAP.get(self.action_type)
        if not schema_class:
            return None
        try:
            return schema_class.model_validate(self.action_params)
        except Exception:
            # 参数不匹配：跳过校验（工具参数各异，不强求）
            return None


class ExecuteCommandParams(BaseModel):
    command: str = Field(..., description="要执行的 shell 命令")


class StopParams(BaseModel):
    answer: str = Field(..., description="给用户的最终回答")


class LocalCallParams(BaseModel):
    final_answer: str = Field(description="最终结果")
    evidence_summary: str = Field(None, description="证据链")
    result: str = Field(None, description="评审结果: PASS 或 FAIL（仅 JudgeAgent 使用）")
    reason: str = Field(None, description="评审原因（仅 JudgeAgent 使用）")

    @property
    def is_passed(self) -> bool:
        return (self.result or "").upper() == "PASS"


ACTION_SCHEMA_MAP: Dict[ActionType, Type[BaseModel]] = {
    ActionType.EXECUTE_COMMAND: ExecuteCommandParams,
    ActionType.STOP: StopParams,
    ActionType.LOCAL_CALL: LocalCallParams,
}


class StateData(BaseModel):
    def format_for_log(self) -> str:
        return f"[{self.__class__.__name__}] {self.model_dump(exclude_none=True)}"


class ThinkingToExecutingData(StateData):
    response: AgentResponse
    confirmed: Optional[bool] = None
    confirmation_prompt: Optional[str] = ""
    user_guidance: Optional[str] = ""  # 用户引导消息

    def format_for_log(self) -> str:
        return f"[{self.__class__.__name__}] 动作: {self.response.action_type.value} | 工具: {self.response.tool_name}"


class ExecutionResultData(StateData):
    observation: str
    action_type: ActionType

    def format_for_log(self) -> str:
        obs_preview = (self.observation[:50] + '...') if len(self.observation) > 50 else self.observation
        return f"[{self.__class__.__name__}] 动作: {self.action_type.value} | 结果: {obs_preview}"


class ErrorData(StateData):
    error_message: str
    trace: Optional[str] = None


class StateTransition(BaseModel):
    state: AgentState
    data: Optional[StateData] = None

    class Config:
        arbitrary_types_allowed = True


class Message(BaseModel):
    role: Literal["user", "assistant", "system", "tool", "summary"] = Field(default="assistant")
    content: str
    sender: str
    receivers: List[str] = Field(default_factory=lambda: ["*"])
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    # === 记忆衰减 ===
    step_index: int = 0           # 在第几步产生（越小越老）
    importance: str = "normal"    # "critical"=永不遗忘, "normal"=正常衰减

    class Config:
        arbitrary_types_allowed = True


class ContextPolicy(BaseModel):
    """每种 Agent 的上下文管理策略"""
    tool_full_turns: int = 2         # 工具结果保留完整的轮数
    tool_truncate_turns: int = 5     # 截断保留的轮数
    tool_max_turns: int = 8          # 彻底删除的轮数
    truncate_head_lines: int = 50    # 截断保留前 N 行
    truncate_tail_lines: int = 10    # 截断保留后 N 行
    summary_enabled: bool = True     # 是否启用 LLM 摘要压缩
    summary_interval: int = 6        # 每 N 步触发一次摘要
    keep_user_messages: bool = True  # user 消息永远不丢
    keep_errors: bool = True         # error 消息永远不丢


class StateTrace(BaseModel):
    agent_name: str
    from_state: str
    to_state: str
    data: Optional[StateData] = None


