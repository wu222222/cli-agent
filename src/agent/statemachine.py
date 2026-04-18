from enum import Enum
from typing import Dict, Any, Callable, Optional, Type, TYPE_CHECKING,NamedTuple
from abc import ABC, abstractmethod
from .base import AgentResponse, AgentState,BaseStateMachine,BaseAgent,ActionType,State,StateData,ThinkingToExecutingData,ExecutionResultData,ErrorData,StateTransition
from src.logger import get_logger

logger = get_logger(__name__)


class IdleState(State):
    """空闲状态"""
    
    def __init__(self, state_machine: BaseStateMachine):
        super().__init__(state_machine)
        self.state = AgentState.IDLE
    
    def on_enter(self, data: Optional[StateData] = None):
        pass
    
    def on_exit(self, data: Optional[StateData] = None):
        pass
    
    async def execute(self, data: Optional[StateData] = None) -> StateTransition:
        """执行空闲状态逻辑"""
        return StateTransition(state=AgentState.THINKING)
    
    def can_transition_to(self, new_state: AgentState, data: Optional[StateData] = None) -> bool:
        return new_state == AgentState.THINKING


class ThinkingState(State):
    """思考状态"""
    
    def __init__(self, state_machine: BaseStateMachine):
        super().__init__(state_machine)
        self.state = AgentState.THINKING
        self.response:Optional[AgentResponse] = None
    
    def on_enter(self, data: Optional[StateData] = None):
        pass
    
    def on_exit(self, data: Optional[StateData] = None):
        pass
    
    async def execute(self, data: Optional[StateData] = None) -> StateTransition:
        """执行思考状态逻辑"""
        self.response = await self.agent._think()
        
        logger.debug(f"状态{self.state},response:{self.response}")

        # 这里决定了“数据包”的封装
        needs_confirm = False
        prompt = ""
        # 根据响应决定下一个状态
        if self.response and self.response.action_type == ActionType.STOP:
            # 这里可以使用我们在 base.py 里规范化的方法
            answer = self.response.action_params.get("answer", self.response.content)
            self.agent.context.add_assistant_message(self.response.content)
            self.agent.context.set_final_answer(answer)
            return StateTransition(state=AgentState.COMPLETED)

        # 2. 处理确认逻辑
        if self.response.action_type == ActionType.EXECUTE_COMMAND:
            needs_confirm = True
            prompt = f"是否允许执行: {self.response.action_params.get('command')}?"
        
        # 组装“协议头”
        data = ThinkingToExecutingData(
            response=resp,
            requires_confirmation=needs_confirm,
            confirmation_prompt=prompt
        )

        if needs_confirm:
            return StateTransition(
                state=AgentState.WAITING_CONFIRMATION, 
                data=data
            )

        # 3. 处理执行逻辑 (通用动作)
        return StateTransition(
            state=AgentState.EXECUTING, 
            data=data
        )


    def get_response(self) -> Optional[AgentResponse]:
        return self.response
    
    def can_transition_to(self, new_state: AgentState, data: Optional[StateData] = None) -> bool:
        return new_state in [
            AgentState.WAITING_CONFIRMATION,
            AgentState.EXECUTING,
            AgentState.COMPLETED,
            AgentState.ERROR
        ]


class ExecutingState(State):
    """执行状态"""
    
    def __init__(self, state_machine: BaseStateMachine):
        super().__init__(state_machine)
        self.state = AgentState.EXECUTING
        self.response:Optional[AgentResponse] = None
    
    def on_enter(self, data: Optional[StateData] = None):
        self.response = None
        if isinstance(data, ThinkingToExecutingData):
            self.response = data.response
            logger.debug(f"response:{self.response}")
        else:
            # 如果类型不对，可以提前预警或处理
            logger.error(f"ExecutingState 期待 ThinkingToExecutingData, 但收到 {type(data)}")
    
    def on_exit(self, data: Optional[StateData] = None):
        pass
    
    async def execute(self, data: Optional[StateData] = None) -> StateTransition:
        """执行执行状态逻辑"""
        if self.response and self.response.action_type:
            try:
                observation = await self.agent._execute_action(self.response.action_type, self.response.action_params)
                
                # 添加assistant消息和工具结果到上下文
                self.agent.context.add_assistant_message(self.response.content)
                self.agent.context.add_tool_result(
                    self.response.action_type,
                    observation
                )
                return StateTransition(state=AgentState.THINKING, data=ExecutionResultData(observation=observation, action_type=self.response.action_type))
            except Exception as e:
                if hasattr(self.agent, 'context'):
                    self.agent.context.set_final_answer(f"执行错误: {str(e)}")
                return StateTransition(state=AgentState.ERROR, data=ErrorData(error_message=f"执行错误: {str(e)}"))
        return StateTransition(state=AgentState.ERROR, data=ErrorData(error_message="执行状态未提供响应"))
        
    def can_transition_to(self, new_state: AgentState, data: Optional[StateData] = None) -> bool:
        return new_state in [
            AgentState.THINKING,
            AgentState.COMPLETED,
            AgentState.ERROR
        ]


class WaitingConfirmationState(State):
    """等待确认状态"""
    
    def __init__(self, state_machine: BaseStateMachine):
        super().__init__(state_machine)
        self.state = AgentState.WAITING_CONFIRMATION
        self.response:Optional[AgentResponse] = None
    
    def on_enter(self, data: Optional[StateData] = None):
        self.response = None
        if isinstance(data, ThinkingToExecutingData):
            self.response = data.response
        else:
            logger.error(f"WaitingConfirmationState 期待 ThinkingToExecutingData, 但收到 {type(data)}")
        pass
    
    def on_exit(self, data: Optional[StateData] = None):
        pass

    async def execute(self, data: Optional[StateData] = None) -> StateTransition:
        """执行等待确认状态逻辑"""
        # 获取之前保存的响应
        if self.response is None:
            logger.error("等待确认状态未提供响应")
            return StateTransition(state=AgentState.ERROR, data=ErrorData(error_message="等待确认状态未提供响应"))
        
        if self.response and self.response.requires_confirmation:
            confirmation_prompt = self.response.confirmation_prompt 
            confirmed = self.confirmation_handler(confirmation_prompt)
            if confirmed:
                return StateTransition(state=AgentState.EXECUTING, data={'response': self.response})
            else:
                self.agent.context.set_final_answer("操作已取消")
                return StateTransition(state=AgentState.COMPLETED)
           
        return StateTransition(state=AgentState.ERROR, data=ErrorData(error_message="操作已取消"))
    
    def can_transition_to(self, new_state: AgentState, data: Optional[StateData] = None) -> bool:
        if new_state == AgentState.EXECUTING:
            return True
        elif new_state in [AgentState.COMPLETED, AgentState.ERROR]:
            return True
        return False

    def confirmation_handler(self, prompt: str) -> bool:
        """人机确认处理器"""
        print("\n" + "=" * 60)
        print("🔐 安全确认")
        print("=" * 60)
        print(f"⚠️  {prompt}")
        print("\n该命令将在隔离的 Docker 容器中执行，不会影响宿主机。")
        
        # 等待用户确认
        while True:
            confirm = input("\n是否确认执行？(y/n): ").lower().strip()
            if confirm == 'y':
                return True
            elif confirm == 'n':
                return False
            else:
                print("请输入 'y' 或 'n'")


class CompletedState(State):
    """完成状态"""
    
    def __init__(self, state_machine: BaseStateMachine):
        super().__init__(state_machine)
        self.state = AgentState.COMPLETED
    
    def on_enter(self, data: Optional[StateData] = None):
        pass
    
    def on_exit(self, data: Optional[StateData] = None):
        pass
    
    async def execute(self, data: Optional[StateData] = None) -> StateTransition:
        """执行完成状态逻辑"""
        return StateTransition(state=AgentState.COMPLETED)  # 保持在完成状态
    
    def can_transition_to(self, new_state: AgentState, data: Optional[StateData] = None) -> bool:
        return new_state == AgentState.IDLE


class ErrorState(State):
    """错误状态"""
    
    def __init__(self, state_machine: BaseStateMachine):
        super().__init__(state_machine)
        self.state = AgentState.ERROR
    
    def on_enter(self, data: Optional[StateData] = None):
        pass
    
    def on_exit(self, data: Optional[StateData] = None):
        pass
    
    async def execute(self, data: Optional[StateData] = None) -> StateTransition:
        """执行错误状态逻辑"""
        return StateTransition(state=AgentState.ERROR, data=ErrorData(error_message="操作已取消"))  # 保持在错误状态
    
    def can_transition_to(self, new_state: AgentState, data: Optional[StateData] = None) -> bool:
        return new_state == AgentState.IDLE

class WorkerStateMachine(BaseStateMachine):
    def __init__(self):
        super().__init__(AgentState.IDLE)
        self._setup_states()

    def _setup_states(self):
        # 包含执行和确认状态
        self._states = {
            AgentState.IDLE: IdleState(self),
            AgentState.THINKING: ThinkingState(self),
            AgentState.EXECUTING: ExecutingState(self),
            AgentState.WAITING_CONFIRMATION: WaitingConfirmationState(self),
            AgentState.COMPLETED: CompletedState(self)
        }
        self._current_state = self._states[AgentState.IDLE]

# class AgentStateMachine:
#     def __init__(self, initial_state: AgentState = AgentState.IDLE):
#         self._current_state_enum = initial_state
#         self._states: Dict[AgentState, State] = {}
#         self._setup_states()
#         self._current_state = self._states[initial_state]
#         self.agent: Optional['Agent'] = None  # 关联的Agent实例
    
#     def set_agent(self, agent: 'Agent'):
#         """设置关联的Agent实例"""
#         self.agent = agent
#         for state in self._states.values():
#             state.agent = agent
    
#     def _setup_states(self):
#         """设置所有状态"""
#         state_classes: Dict[AgentState, Type[State]] = {
#             AgentState.IDLE: IdleState,
#             AgentState.THINKING: ThinkingState,
#             AgentState.EXECUTING: ExecutingState,
#             AgentState.WAITING_CONFIRMATION: WaitingConfirmationState,
#             AgentState.COMPLETED: CompletedState,
#             AgentState.ERROR: ErrorState
#         }
        
#         for state_enum, state_class in state_classes.items():
#             self._states[state_enum] = state_class(self)
    
#     async def execute(self, data: Optional[StateData] = None) -> StateTransition:
#         """执行当前状态的逻辑并返回下一个状态"""
#         transition = await self._current_state.execute(data: Optional[StateData] = None)
#         return transition
    
#     def transition(self, new_state: AgentState, data: Optional[StateData] = None) -> bool:
#         """执行状态转换
        
#         Args:
#             new_state: 新状态
#             data: Optional[StateData] = None: 转换参数
            
#         Returns:
#             bool: 是否转换成功
#         """
#         # 检查状态是否存在
#         if new_state not in self._states:
#             return False
        
#         # 检查转换条件
#         if not self._current_state.can_transition_to(new_state, data: Optional[StateData] = None):
#             return False
        
#         # 添加状态转换记录
#         # 从思考状态到确认状态的参数和确认状态到执行状态的参数相同，因此不需要重复记录
#         params = kwargs
#         if new_state == AgentState.EXECUTING and self._current_state_enum == AgentState.WAITING_CONFIRMATION and 'response' in kwargs:
#             params = kwargs.copy()
#             params.pop('response')

#         self.agent.context.add_state_trace(
#             from_state=self._current_state_enum.value,
#             to_state=new_state.value,
#             params=params
#         )
        
#         # 退出当前状态
#         self._current_state.on_exit(data: Optional[StateData] = None)
#         old_state = self._current_state_enum
        
#         # 转换到新状态
#         self._current_state_enum = new_state
#         self._current_state = self._states[new_state]
        
#         # 进入新状态
#         self._current_state.on_enter(data: Optional[StateData] = None)
        
#         return True
    
#     def get_state(self) -> AgentState:
#         """获取当前状态"""
#         return self._current_state_enum
    
#     def get_current_state_object(self) -> State:
#         """获取当前状态对象"""
#         return self._current_state
    
#     def is_in_state(self, state: AgentState) -> bool:
#         """检查是否在指定状态"""
#         return self._current_state_enum == state
    
#     def reset(self) -> None:
#         """重置状态机"""
#         self.transition(AgentState.IDLE)
