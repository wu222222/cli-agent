from typing import Dict, Any, Optional, Type, NamedTuple
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field

from src.llm import LLMClient, LLMConfig
from .context import ContextManager
from .prompt import PromptManager
from .tools import ToolRegistry, Tool

class ActionType(Enum):
    # 核心动作
    EXECUTE_COMMAND = "execute_command"
    STOP = "stop"
    
    # 未来可以轻松扩展 Judge 专用的动作
    REVIEW = "review"

class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING_CONFIRMATION = "waiting_confirmation"
    COMPLETED = "completed"
    ERROR = "error"

class ExecuteCommandParams(BaseModel):
    command: str = Field(...,description="要执行的 shell 命令")

class StopParams(BaseModel):
    answer: str = Field(...,description="给用户的最终回答")


ACTION_SCHEMA_MAP: Dict[ActionType, Type[BaseModel]] = {
    ActionType.EXECUTE_COMMAND: ExecuteCommandParams,
    ActionType.STOP: StopParams,
}

class StateData(BaseModel):
    """所有状态传递数据的基类"""
    pass

class ThinkingToExecutingData(StateData):
    """从思考跳转到执行/确认时需要的数据"""
    response: AgentResponse
    # 将控制流属性移动到这里
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = ""

class ExecutionResultData(StateData):
    """执行完成后返回给思考状态的数据"""
    observation: str
    action_type: str

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

@dataclass
class Message:
    role: str  # user, assistant, system, tool
    content: str
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None

@dataclass
class StateTrace:
    from_state: str
    to_state: str
    params: Dict[str, Any] = None

class BaseAgent(ABC):
    def __init__(
        self,
        name: str,
        llm_client: Optional[LLMClient] = None,
        context_manager: Optional[ContextManager] = None,
        prompt_manager: Optional[PromptManager] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.name = name
        self.llm_client = llm_client or LLMClient()
        self.context = context_manager or ContextManager()
        self.prompts = prompt_manager or PromptManager()
        self.tools = tool_registry or ToolRegistry()
        
        # 核心：每个子类可以有自己的状态机定义
        self.state_machine = self._create_state_machine()
        self.state_machine.set_agent(self)
        
        self.max_iterations = 10
        self._setup_system_prompt()

    @abstractmethod
    def _create_state_machine(self) -> 'BaseStateMachine':
        """子类需实现：返回该 Agent 专用的状态机"""
        pass

    def _setup_system_prompt(self) -> None:
        # 子类可以通过 prompt_manager 获取不同的角色定义
        system_prompt = self.prompts.get_system_prompt(self.name)
        self.context.set_system_prompt(system_prompt)

    async def run(self, user_input: str) -> str:
        """通用的 ReAct 循环调度逻辑"""
        self.context.add_user_message(user_input)
        # 统一从起始状态开始（假设子类状态机都有初始状态）
        self.state_machine.transition(AgentState.THINKING)

        try:
            for iteration in range(self.max_iterations):
                transition = await self.state_machine.execute()
                next_state = transition.state
                data = transition.data or {}

                if not self.state_machine.transition(next_state, **data):
                    return f"[{self.name}] 状态转换错误"

                if self.state_machine.is_in_state(AgentState.COMPLETED):
                    return self._get_final_result()
                
                if self.state_machine.is_in_state(AgentState.ERROR):
                    return f"[{self.name}] 执行出错"

            return "达到最大迭代次数"
        except Exception as e:
            self.state_machine.transition(AgentState.ERROR, error=str(e))
            return f"系统崩溃: {str(e)}"

    @abstractmethod
    async def _think(self) -> AgentResponse:
        """具体的 LLM 调用和解析逻辑"""
        pass

    @abstractmethod
    async def _execute_action(self, action_type: str, action_params: Dict[str, Any]) -> str:
        """执行具体的动作，并返回结果"""
        pass

    def _get_final_result(self) -> str:
        """默认从 context 拿结果，子类可重写"""
        return self.context.get_final_answer()

class State(ABC):
    """状态基类，定义状态的钩子函数"""
    
    def __init__(self, state_machine: 'BaseStateMachine'):
        self.state_machine = state_machine
        self.state = None  # 子类需要设置具体的状态
        self.agent: Optional[BaseAgent] = None  # 由状态机设置
    
    @abstractmethod
    def on_enter(self, data: Optional[StateData] = None):
        """进入状态时调用"""
        pass
    
    @abstractmethod
    def on_exit(self, data: Optional[StateData] = None):
        """退出状态时调用"""
        pass
    
    @abstractmethod
    async def execute(self, data: Optional[StateData] = None) -> StateTransition:
        """执行状态逻辑并返回下一个状态"""
        pass
    
    def can_transition_to(self, new_state: AgentState) -> bool:
        """检查是否可以转换到新状态"""
        return True

class BaseStateMachine(ABC):
    def __init__(self, initial_state: AgentState):
        self._current_state_enum = initial_state
        self._states: Dict[AgentState, State] = {}
        self._current_state: Optional[State] = None
        self.agent: Optional['BaseAgent'] = None

    def set_agent(self, agent: 'BaseAgent'):
        self.agent = agent
        for state in self._states.values():
            state.agent = agent

    @abstractmethod
    def _setup_states(self):
        """子类需实现：配置该状态机特有的状态类映射"""
        pass

    def transition(self, new_state_enum: AgentState, data: Optional[StateData] = None) -> bool:
        """通用的状态切换逻辑（包含你之前写的 context 记录逻辑）"""
        if new_state_enum not in self._states:
            return False
        
        # 统一的日志记录
        if self.agent and self.agent.context:
            self.agent.context.add_state_trace(
                from_state=self._current_state_enum.value,
                to_state=new_state_enum.value,
                params=data
            )

        self._current_state.on_exit(data)
        self._current_state_enum = new_state_enum
        self._current_state = self._states[new_state_enum]
        self._current_state.on_enter(data)
        return True

    async def execute(self, data: Optional[StateData] = None) -> StateTransition:
        return await self._current_state.execute(data)
