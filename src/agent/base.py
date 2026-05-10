from typing import Dict, Any, Optional, Type, NamedTuple
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
import json

from pydantic import ValidationError

from src.logger import get_logger
from src.agent.context import ContextManager
from src.agent.prompt import PromptManager
from src.agent.tools import ToolRegistry
from src.agent.types import *
from src.llm import LLMClient, LLMConfig

logger = get_logger(__name__)


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
        self.context_manager = context_manager or ContextManager()
        self.prompt_manager = prompt_manager or PromptManager()
        self.tools = tool_registry or ToolRegistry()
        
        self._setup_system_prompt()

        # 核心：每个子类可以有自己的状态机定义
        self.state_machine = self._create_state_machine()
        self.state_machine.set_agent(self)

        self.max_iterations = 15
        self.last_thought: str = ""

    @abstractmethod
    def _setup_system_prompt(self) -> None:
        """子类需实现：设置系统的提示"""
        pass

    @abstractmethod
    def _create_state_machine(self) -> 'BaseStateMachine':
        """子类需实现：返回该 Agent 专用的状态机"""
        pass

    @abstractmethod
    def _prepare_context(self,input:str | dict | Message = None) -> None:
        """上下文控制流"""
        pass

    async def step(self) -> StateTransition:
        """
        单步执行核心逻辑：执行 -> 获取建议状态 -> 转换
        """
        # 1. 检查是否已经结束
        if self.state_machine.is_in_state(AgentState.COMPLETED):
            return StateTransition(state=AgentState.COMPLETED)

        # 2. 调用当前状态的 execute，获取状态机的“建议”
        # 例如：ThinkingState 执行完后返回一个指向 WAITING_CONFIRMATION 的 transition
        transition = await self.state_machine.execute()
        
        # 3. 真正触发状态机的转换逻辑（执行 on_exit/on_enter）
        # 注意：这里的 transition.state 是建议的目标状态
        success = self.state_machine.transition(transition.state, transition.data)
        
        if not success:
            # 如果转换失败（比如 can_transition_to 校验没过），返回错误状态
            return StateTransition(
                state=AgentState.ERROR, 
                data=ErrorData(error_message=f"Illegal transition to {transition.state}")
            )

        # 4. 返回当前的 transition 对象，供 Orchestrator 或 API 层判断
        return transition

    async def run(self,input:str | dict | Message = None) -> str:
        """通用的 ReAct 循环调度逻辑"""
        self._prepare_context(input)
        # 统一从起始状态开始（假设子类状态机都有初始状态）
        self.state_machine.transition(AgentState.THINKING)

        try:
            for iteration in range(self.max_iterations):
                transition = await self.state_machine.execute()
                next_state = transition.state
                data = transition.data or {}

                if not self.state_machine.transition(next_state, data):
                    return f"[{self.name}] 状态转换错误"

                if self.state_machine.is_in_state(AgentState.COMPLETED):
                    return self._get_final_result()
                
                if self.state_machine.is_in_state(AgentState.ERROR):
                    return f"[{self.name}] 执行出错"

            return "达到最大迭代次数"
        except Exception as e:
            self.state_machine.transition(AgentState.ERROR, data=ErrorData(error_message=str(e)))
            return f"系统崩溃: {str(e)}"

    @abstractmethod
    async def _think(self) -> AgentResponse:
        """具体的 LLM 调用和解析逻辑"""
        pass

    def _parse_action(self, response_text: str) -> Optional[LLMOutput]:
        """从 LLM 原始响应中提取并校验 JSON 结构"""
        try:
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()

            data = json.loads(json_str)
            return LLMOutput.model_validate(data)
        except (json.JSONDecodeError, IndexError, ValidationError) as e:
            logger.warning(f"JSON 解析或结构校验失败: {e}")
            return None

    async def _execute_action(self, action_type: ActionType, action_params: Dict[str, Any], tool_name: Optional[str] = None) -> str:
        """执行action，优先使用 tool_name 调用具体工具"""
        exec_name = tool_name or action_type.value
        logger.info(f"执行工具: {exec_name} (action: {action_type}), 参数: {action_params}")
        result = await self.tools.run(exec_name, action_params)
        logger.info(f"工具执行结果: {result}")
        return result

    def _get_final_result(self) -> str:
        """默认从 context 拿结果，子类可重写"""
        return self.context_manager.get_final_answer()

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

    def is_in_state(self, state_enum: AgentState) -> bool:
        """检查当前状态是否为指定状态"""
        return self._current_state_enum == state_enum

    def transition(self, new_state_enum: AgentState, data: Optional[StateData] = None) -> bool:
        """通用的状态切换逻辑（包含你之前写的 context 记录逻辑）"""
        if new_state_enum not in self._states:
            return False
        
        # 统一的日志记录
        if self.agent and self.agent.context_manager:
            self.agent.context_manager.add_state_trace(
                agent_name=self.agent.name,
                from_state=self._current_state_enum.value,
                to_state=new_state_enum.value,
                data=data
            )

        self._current_state.on_exit(data)
        self._current_state_enum = new_state_enum
        self._current_state = self._states[new_state_enum]
        self._current_state.on_enter(data)
        return True

    async def execute(self, data: Optional[StateData] = None) -> StateTransition:
        return await self._current_state.execute(data)
