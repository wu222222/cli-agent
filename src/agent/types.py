from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Type, Literal,List
from enum import Enum


class ActionType(Enum):
    # 核心动作
    EXECUTE_COMMAND = "execute_command"
    STOP = "stop"
    CALL_JUDGE = "call_judge"
    # 知识库查询
    QUERY_KNOWLEDGE = "query_knowledge"

    # Judge 专用的动作
    REVIEW = "review"

    # Curator 专用的动作
    CURATE = "curate"

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

    # 允许 Pydantic 处理可能存在的 dataclass 遗留
    class Config:
        arbitrary_types_allowed = True

    def validate_params(self):
        """
        验证 action_params 是否符合对应的 schema 规范
        """
        schema_class = ACTION_SCHEMA_MAP.get(self.action_type)
        if not schema_class:
            # 如果没有定义 schema，返回原始字典或抛出异常
            raise ValueError(f"未定义的 Action 类型 Schema: {self.action_type}")
            
        # 返回的是具体的模型实例（如 ExecuteCommandParams 实例）
        return schema_class.model_validate(self.action_params)


class ExecuteCommandParams(BaseModel):
    command: str = Field(...,description="要执行的 shell 命令")

class StopParams(BaseModel):
    answer: str = Field(...,description="给用户的最终回答")

class ReviewParams(BaseModel):
    is_passed: bool = Field(description="任务是否真正完成且符合预期")
    reason: str = Field(description="判定通过或失败的理由")
    suggestions: Optional[str] = Field(None, description="如果失败，给 Worker 的改进建议")

class CallJudgeParams(BaseModel):
    final_answer: str = Field(description="你准备给用户的最终结果")
    evidence_summary: str = Field(None,description="简述你得出此结论的证据链（可选）")


ACTION_SCHEMA_MAP: Dict[ActionType, Type[BaseModel]] = {
    ActionType.EXECUTE_COMMAND: ExecuteCommandParams,
    ActionType.STOP: StopParams,
    ActionType.REVIEW: ReviewParams,
    ActionType.CALL_JUDGE: CallJudgeParams,
}

class StateData(BaseModel):
    """所有状态传递数据的基类"""
    def format_for_log(self) -> str:
        # 默认实现：只输出类名和精简字典
        return f"[{self.__class__.__name__}] {self.model_dump(exclude_none=True)}"

class ThinkingToExecutingData(StateData):
    """从思考跳转到执行/确认时需要的数据"""
    response: AgentResponse
    # 将控制流属性移动到这里
    requires_confirmation: bool = False
    confirmed: Optional[bool] = None
    confirmation_prompt: Optional[str] = ""

    def format_for_log(self) -> str:
        # 核心优化：只显示 action 类型和确认状态，隐藏冗长的 thought 内容
        action_name = self.response.action_type.value
        confirm_str = f" | 需要确认: {self.requires_confirmation}" if self.requires_confirmation else ""
        return f"[{self.__class__.__name__}] 动作: {action_name}{confirm_str}"

class ExecutionResultData(StateData):
    """执行完成后返回给思考状态的数据"""
    observation: str
    action_type: str

    def format_for_log(self) -> str:
        # 核心优化：截断过长的执行结果，防止撑爆日志
        obs_preview = (self.observation[:50] + '...') if len(self.observation) > 50 else self.observation
        return f"[{self.__class__.__name__}] 动作: {self.action_type} | 结果预览: {obs_preview}"

class ErrorData(StateData):
    """跳转到错误状态时需要的数据"""
    error_message: str
    trace: Optional[str] = None

class StateTransition(BaseModel):
    """状态转换"""
    state: AgentState
    data: Optional[StateData] = None

    # 允许在初始化时直接传对象
    class Config:
        arbitrary_types_allowed = True

class Message(BaseModel):
    role: Literal["user", "assistant", "system", "tool"] = Field(default="assistant")  # # user, assistant, system, tool
    content: str
    sender: str  # 发送方标识：如 "user", "system", "WorkerAgent", "JudgeAgent"
    # 接收方列表：如果是 ["*"] 表示广播给所有人，或者指定具体 Agent 列表 ["JudgeAgent"] 暂时不需要使用
    receivers: List[str] = Field(default_factory=lambda: ["*"])
    
    # 扩展字段：用于工具调用
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

class StateTrace(BaseModel):
    agent_name: str
    from_state: str
    to_state: str
    data: Optional[StateData] = None

class TaskPolicy(BaseModel):
    allow_kb_search: bool = True   # 是否允许 Worker 使用 query_knowledge 工具
    allow_curation: bool = True    # 任务结束后是否启动 Curator 总结
    read_only_kb: bool = True      # 强制知识库对 Worker 只读（默认应为 True）