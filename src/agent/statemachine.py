from enum import Enum
from typing import Dict, Any, Callable, Optional, Type, TYPE_CHECKING,NamedTuple
from abc import ABC, abstractmethod
from .base import AgentResponse, AgentState

if TYPE_CHECKING:
    from agent import Agent

class StateTransition(NamedTuple):
    """状态转换"""
    state: AgentState
    data: Optional[Dict[str, Any]] = None

class State(ABC):
    """状态基类，定义状态的钩子函数"""
    
    def __init__(self, state_machine: 'AgentStateMachine'):
        self.state_machine = state_machine
        self.state = None  # 子类需要设置具体的状态
        self.agent: Optional[Agent] = None  # 由状态机设置
    
    @abstractmethod
    def on_enter(self, **kwargs):
        """进入状态时调用"""
        pass
    
    @abstractmethod
    def on_exit(self, **kwargs):
        """退出状态时调用"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> StateTransition:
        """执行状态逻辑并返回下一个状态"""
        pass
    
    def can_transition_to(self, new_state: AgentState, **kwargs) -> bool:
        """检查是否可以转换到新状态"""
        return True


class IdleState(State):
    """空闲状态"""
    
    def __init__(self, state_machine: 'AgentStateMachine'):
        super().__init__(state_machine)
        self.state = AgentState.IDLE
    
    def on_enter(self, **kwargs):
        pass
    
    def on_exit(self, **kwargs):
        pass
    
    async def execute(self, **kwargs) -> StateTransition:
        """执行空闲状态逻辑"""
        return StateTransition(state=AgentState.THINKING)
    
    def can_transition_to(self, new_state: AgentState, **kwargs) -> bool:
        return new_state == AgentState.THINKING


class ThinkingState(State):
    """思考状态"""
    
    def __init__(self, state_machine: 'AgentStateMachine'):
        super().__init__(state_machine)
        self.state = AgentState.THINKING
        self.response:Optional[AgentResponse] = None
    
    def on_enter(self, **kwargs):
        pass
    
    def on_exit(self, **kwargs):
        pass
    
    async def execute(self, **kwargs) -> AgentState:
        """执行思考状态逻辑"""
        self.response = await self.agent._think()
        
        # 根据响应决定下一个状态
        if self.response and self.response.action_type == "stop":
            # 保存最终回答
            self.agent.context.add_assistant_message(self.response.content)
            # 保存最终回答到上下文
            if "answer" in self.response.action_params:
                self.agent.context.set_final_answer(self.response.action_params["answer"])
            else:
                self.agent.context.set_final_answer(self.response.content)
            return StateTransition(state=AgentState.COMPLETED)

        elif self.response and self.response.requires_confirmation:
            # 需要确认，保存响应供后续使用
            self.state_machine._current_response = self.response
            return StateTransition(state=AgentState.WAITING_CONFIRMATION)
        elif self.response and self.response.action_type:
            # 直接执行
            self.state_machine._current_response = self.response
            return StateTransition(state=AgentState.EXECUTING, data={'response': self.response})
        else:
            # 没有action，视为完成
            if self.response:
                self.agent.context.add_assistant_message(self.response.content)
                self.agent.context.set_final_answer(self.response.content)
            return StateTransition(state=AgentState.COMPLETED)

    def get_response(self) -> Optional[AgentResponse]:
        return self.response
    
    def can_transition_to(self, new_state: AgentState, **kwargs) -> bool:
        return new_state in [
            AgentState.WAITING_CONFIRMATION,
            AgentState.EXECUTING,
            AgentState.COMPLETED,
            AgentState.ERROR
        ]


class ExecutingState(State):
    """执行状态"""
    
    def __init__(self, state_machine: 'AgentStateMachine'):
        super().__init__(state_machine)
        self.state = AgentState.EXECUTING
        self.response:Optional[AgentResponse] = None
    
    def on_enter(self, **kwargs):
        self.response = None
        self.response = kwargs.get("response", None)
        pass
    
    def on_exit(self, **kwargs):
        pass
    
    async def execute(self, **kwargs) -> StateTransition:
        """执行执行状态逻辑"""
        # 获取之前保存的响应
        if not self.response:
            logger.error("执行状态未提供响应")
            return StateTransition(state=AgentState.ERROR)
        
        if self.response and self.response.action_type:
            if hasattr(self.agent, '_execute_action'):
                try:
                    observation = await self.agent._execute_action(self.response.action_type, self.response.action_params)
                    
                    # 添加assistant消息和工具结果到上下文
                    self.agent.context.add_assistant_message(self.response.content)
                    self.agent.context.add_tool_result(
                        self.response.action_type,
                        observation
                    )
                    return StateTransition(state=AgentState.THINKING)
                except Exception as e:
                    if hasattr(self.agent, 'context'):
                        self.agent.context.set_final_answer(f"执行错误: {str(e)}")
                    return StateTransition(state=AgentState.ERROR)
        return StateTransition(state=AgentState.ERROR)
    
    def can_transition_to(self, new_state: AgentState, **kwargs) -> bool:
        return new_state in [
            AgentState.THINKING,
            AgentState.COMPLETED,
            AgentState.ERROR
        ]


class WaitingConfirmationState(State):
    """等待确认状态"""
    
    def __init__(self, state_machine: 'AgentStateMachine'):
        super().__init__(state_machine)
        self.state = AgentState.WAITING_CONFIRMATION
    
    def on_enter(self, **kwargs):
        pass
    
    def on_exit(self, **kwargs):
        pass
    
    async def execute(self, **kwargs) -> AgentState:
        """执行等待确认状态逻辑"""
        # 获取之前保存的响应
        response = getattr(self.state_machine, '_current_response', None)
        
        if response and response.requires_confirmation:
            confirmation_prompt = response.confirmation_prompt
            if hasattr(self.agent, '_confirmation_handler') and self.agent._confirmation_handler:
                confirmed = self.agent._confirmation_handler(confirmation_prompt)
                if confirmed:
                    return AgentState.EXECUTING
                else:
                    if hasattr(self.agent, 'context'):
                        self.agent.context.set_final_answer("操作已取消")
                    return AgentState.COMPLETED
            else:
                # 没有确认处理器，默认取消
                if hasattr(self.agent, 'context'):
                    self.agent.context.set_final_answer("操作已取消")
                return AgentState.COMPLETED
        return AgentState.ERROR
    
    def can_transition_to(self, new_state: AgentState, **kwargs) -> bool:
        if new_state == AgentState.EXECUTING:
            return True
        elif new_state in [AgentState.COMPLETED, AgentState.ERROR]:
            return True
        return False


class CompletedState(State):
    """完成状态"""
    
    def __init__(self, state_machine: 'AgentStateMachine'):
        super().__init__(state_machine)
        self.state = AgentState.COMPLETED
    
    def on_enter(self, **kwargs):
        pass
    
    def on_exit(self, **kwargs):
        pass
    
    async def execute(self, **kwargs) -> AgentState:
        """执行完成状态逻辑"""
        return AgentState.COMPLETED  # 保持在完成状态
    
    def can_transition_to(self, new_state: AgentState, **kwargs) -> bool:
        return new_state == AgentState.IDLE


class ErrorState(State):
    """错误状态"""
    
    def __init__(self, state_machine: 'AgentStateMachine'):
        super().__init__(state_machine)
        self.state = AgentState.ERROR
    
    def on_enter(self, **kwargs):
        pass
    
    def on_exit(self, **kwargs):
        pass
    
    async def execute(self, **kwargs) -> AgentState:
        """执行错误状态逻辑"""
        return AgentState.ERROR  # 保持在错误状态
    
    def can_transition_to(self, new_state: AgentState, **kwargs) -> bool:
        return new_state == AgentState.IDLE


class AgentStateMachine:
    def __init__(self, initial_state: AgentState = AgentState.IDLE):
        self._current_state_enum = initial_state
        self._states: Dict[AgentState, State] = {}
        self._setup_states()
        self._current_state = self._states[initial_state]
        self.agent: Optional[Agent] = None  # 关联的Agent实例
    
    def set_agent(self, agent: Agent):
        """设置关联的Agent实例"""
        self.agent = agent
        for state in self._states.values():
            state.agent = agent
    
    def _setup_states(self):
        """设置所有状态"""
        state_classes: Dict[AgentState, Type[State]] = {
            AgentState.IDLE: IdleState,
            AgentState.THINKING: ThinkingState,
            AgentState.EXECUTING: ExecutingState,
            AgentState.WAITING_CONFIRMATION: WaitingConfirmationState,
            AgentState.COMPLETED: CompletedState,
            AgentState.ERROR: ErrorState
        }
        
        for state_enum, state_class in state_classes.items():
            self._states[state_enum] = state_class(self)
    
    async def execute(self, **kwargs) -> StateTransition:
        """执行当前状态的逻辑并返回下一个状态"""
        transition = await self._current_state.execute(**kwargs)
        return transition
    
    def transition(self, new_state: AgentState, **kwargs) -> bool:
        """执行状态转换
        
        Args:
            new_state: 新状态
            **kwargs: 转换参数
            
        Returns:
            bool: 是否转换成功
        """
        # 检查状态是否存在
        if new_state not in self._states:
            return False
        
        # 检查转换条件
        if not self._current_state.can_transition_to(new_state, **kwargs):
            return False
        
        # 退出当前状态
        self._current_state.on_exit(**kwargs)
        old_state = self._current_state_enum
        
        # 转换到新状态
        self._current_state_enum = new_state
        self._current_state = self._states[new_state]
        
        # 进入新状态
        self._current_state.on_enter(**kwargs)
        
        return True
    
    def get_state(self) -> AgentState:
        """获取当前状态"""
        return self._current_state_enum
    
    def get_current_state_object(self) -> State:
        """获取当前状态对象"""
        return self._current_state
    
    def is_in_state(self, state: AgentState) -> bool:
        """检查是否在指定状态"""
        return self._current_state_enum == state
    
    def reset(self) -> None:
        """重置状态机"""
        self.transition(AgentState.IDLE)
