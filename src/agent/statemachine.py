from enum import Enum
from typing import Dict, Any, Callable, Optional, Type, TYPE_CHECKING,NamedTuple
from abc import ABC, abstractmethod
from .base import BaseStateMachine,BaseAgent,State
from .types import *
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


class WorkerThinkingState(State):
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

        # 根据响应决定下一个状态
        match self.response.action_type:
            case ActionType.STOP:
                # 先进入判断状态，再进入完成状态
                answer = self.response.action_params.get("answer", self.response.content)
                self.agent.context_manager.add_assistant_message(self.agent.name,self.response.content,[self.agent.name])
                self.agent.context_manager.set_final_answer(answer)
                return StateTransition(state=AgentState.COMPLETED)

            case ActionType.EXECUTE_COMMAND:
                needs_confirm = True
                command = self.response.action_params.get('command', '')
                thought = self.response.thought or ''
                if thought:
                    prompt = f"[思考] {thought}\n\n[命令] {command}\n\n是否允许执行以上命令?"
                else:
                    prompt = f"是否允许执行: {command}?"
                out_data = ThinkingToExecutingData(
                    response=self.response,
                    requires_confirmation=needs_confirm,
                    confirmation_prompt=prompt
                )
                return StateTransition(
                    state=AgentState.WAITING_CONFIRMATION, 
                    data=out_data
                )

            case ActionType.CALL_JUDGE:
                return StateTransition(
                    state=AgentState.EXECUTING, 
                    data=ThinkingToExecutingData(response=self.response)
                )
            
            case ActionType.QUERY_KNOWLEDGE:
                return StateTransition(
                    state=AgentState.EXECUTING, 
                    data=ThinkingToExecutingData(response=self.response)
                )
            
            case _:
                # 3. 处理执行逻辑 (通用动作)
                return StateTransition(
                    state=AgentState.EXECUTING, 
                    data= ThinkingToExecutingData(response=self.response)
                )
    
    def can_transition_to(self, new_state: AgentState, data: Optional[StateData] = None) -> bool:
        return new_state in [
            AgentState.WAITING_CONFIRMATION,
            AgentState.EXECUTING,
            AgentState.ERROR,
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
                self.agent.context_manager.add_assistant_message(self.agent.name,self.response.content,[self.agent.name])
                self.agent.context_manager.add_tool_result(
                    agent_name=self.agent.name,
                    tool_name=self.response.action_type.value,
                    result=observation
                )
                return StateTransition(state=AgentState.THINKING, data=ExecutionResultData(observation=observation, action_type=self.response.action_type))
            except Exception as e:
                self.agent.context_manager.set_final_answer(f"执行错误: {str(e)}")
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
        self.data:Optional[ThinkingToExecutingData] = None
    
    def on_enter(self, data: Optional[StateData] = None):
        self.data = None # 重置数据状态
        if isinstance(data, ThinkingToExecutingData):
            self.data = data
        else:
            logger.error(f"WaitingConfirmationState 期待 ThinkingToExecutingData, 但收到 {type(data)}")
        pass
    
    def on_exit(self, data: Optional[StateData] = None):
        pass

    async def execute(self, data: Optional[StateData] = None) -> StateTransition:
        """执行等待确认状态逻辑"""
        if not isinstance(self.data, ThinkingToExecutingData):
            return StateTransition(state=AgentState.ERROR, data=ErrorData(error_message="数据类型错误"))

        # 如果不需要确认，直接进入执行
        if not self.data.requires_confirmation:
            return StateTransition(state=AgentState.EXECUTING, data=self.data)

        # 处理需要确认的情况
        # 检查 self.data.confirmed（由外部在调用 step() 前设置）
        if self.data.confirmed is None:
            # 情况 A: 用户还没点按钮，继续保持原地挂起
            return StateTransition(state=AgentState.WAITING_CONFIRMATION, data=self.data)

        if self.data.confirmed is True:
            # 情况 B: 用户点允许
            return StateTransition(state=AgentState.EXECUTING, data=self.data)
        else:
            # 情况 C: 用户点拒绝
            self.agent.context_manager.set_final_answer("操作已被用户取消")
            return StateTransition(state=AgentState.COMPLETED)

        # if self.data.requires_confirmation:
        #     confirmation_prompt = self.data.confirmation_prompt 
        #     thought = self.data.response.thought
        #     confirmed = self.confirmation_handler(confirmation_prompt,thought)
        #     if confirmed:
        #         return StateTransition(state=AgentState.EXECUTING, data=self.data)
        #     else:
        #         self.agent.context_manager.set_final_answer("操作已取消")
        #         return StateTransition(state=AgentState.COMPLETED)

    
    def can_transition_to(self, new_state: AgentState, data: Optional[StateData] = None) -> bool:
        if new_state == AgentState.EXECUTING:
            return True
        elif new_state in [AgentState.COMPLETED, AgentState.ERROR]:
            return True
        return False

    # def confirmation_handler(self, prompt: str,thought: str = None) -> bool:
    #     """人机确认处理器"""
    #     print("\n" + "=" * 60)
    #     print("🔐 安全确认")
    #     if thought:
    #         print(f"思考: {thought}")
    #     print("=" * 60)
    #     print(f"⚠️  {prompt}")
    #     print("=" * 60)
        
    #     # 等待用户确认
    #     while True:
    #         confirm = input("\n是否确认执行？(y/n): ").lower().strip()
    #         if confirm == 'y':
    #             return True
    #         elif confirm == 'n':
    #             return False
    #         else:
    #             print("请输入 'y' 或 'n'")


class CompletedState(State):
    """完成状态"""
    
    def __init__(self, state_machine: BaseStateMachine):
        super().__init__(state_machine)
        self.state = AgentState.COMPLETED
        self.temp_data:Optional[StateData] = None
    
    def on_enter(self, data: Optional[StateData] = None):
        self.temp_data = data
    
    def on_exit(self, data: Optional[StateData] = None):
        pass
    
    async def execute(self, data: Optional[StateData] = None) -> StateTransition:
        """执行完成状态逻辑"""
        return StateTransition(state=AgentState.COMPLETED, data=self.temp_data)  # 保持在完成状态
    
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

class JudgeState(State):
    """判断状态"""

    def __init__(self, state_machine: BaseStateMachine):
        super().__init__(state_machine)
        self.state = AgentState.THINKING
        self.response:Optional[AgentResponse] = None
    
    def on_enter(self, data: Optional[StateData] = None):
        pass
    
    def on_exit(self, data: Optional[StateData] = None):
        pass
    
    async def execute(self, data: Optional[StateData] = None) -> StateTransition:
        self.response = await self.agent._think()
        # 4. 根据 Judge 的 ActionType.REVIEW 结果决定 Worker 的去向
        review_data = self.response.validate_params() # 拿到 ReviewParams 对象

        if review_data.is_passed:
            data = ExecutionResultData(
                observation=f"评审通过,原因：{review_data.reason}",
                action_type=ActionType.REVIEW,
            )
            # self.agent.context_manager.add_tool_result(
            #     agent_name=self.agent.name,
            #     tool_name="review", 
            #     result=f"评审通过,原因：{review_data.reason}",
            #     receivers=[self.agent.name]
            # )
            return StateTransition(state=AgentState.COMPLETED, data=data)
        else:
            data = ExecutionResultData(
                observation=f"评审打回,原因：{review_data.reason}",
                action_type=ActionType.REVIEW,
            )
            # self.agent.context_manager.add_tool_result(
            #     agent_name=self.agent.name,
            #     tool_name="review",
            #     result=f"评审打回,原因：{review_data.reason}",
            #     receivers=[self.agent.name]
            # )
            return StateTransition(state=AgentState.COMPLETED, data=data)
    
    def can_transition_to(self, new_state: AgentState, data: Optional[StateData] = None) -> bool:
        return new_state in [
            AgentState.THINKING,
            AgentState.COMPLETED,
            AgentState.ERROR
        ]

class CuratorThinkingState(State):
    """知识整理者思考状态"""
    
    def __init__(self, state_machine: BaseStateMachine):
        super().__init__(state_machine)
        self.state = AgentState.THINKING
        self.response:Optional[AgentResponse] = None
    
    def on_enter(self, data: Optional[StateData] = None):
        pass

    def on_exit(self, data: Optional[StateData] = None):
        pass
    
    async def execute(self, data: Optional[StateData] = None) -> StateTransition:
        """执行知识整理者思考状态逻辑"""
        self.response = await self.agent._think()
        
        logger.debug(f"状态{self.state},response:{self.response}")

        # 根据响应决定下一个状态
        match self.response.action_type:
            case ActionType.STOP:
                # 先进入判断状态，再进入完成状态
                answer = self.response.action_params.get("answer", self.response.content)
                self.agent.context_manager.add_assistant_message(self.agent.name,self.response.content,[self.agent.name])
                self.agent.context_manager.set_final_answer(answer)
                return StateTransition(state=AgentState.COMPLETED)

            case ActionType.EXECUTE_COMMAND:
                needs_confirm = True
                prompt = f"是否允许执行: {self.response.action_params.get('command')}?"
                out_data = ThinkingToExecutingData(
                    response=self.response,
                    requires_confirmation=needs_confirm,
                    confirmation_prompt=prompt
                )
                return StateTransition(
                    state=AgentState.WAITING_CONFIRMATION, 
                    data=out_data
                )
            
            case _:
                # 3. 跳转至Error状态
                return StateTransition(
                    state=AgentState.ERROR, 
                    data= ErrorData(response=self.response)
                )
    
    def can_transition_to(self, new_state: AgentState, data: Optional[StateData] = None) -> bool:
        return new_state in [
            AgentState.COMPLETED,
            AgentState.ERROR,
            AgentState.WAITING_CONFIRMATION
        ]


class WorkerStateMachine(BaseStateMachine):
    def __init__(self):
        super().__init__(AgentState.IDLE)
        self._setup_states()

    def _setup_states(self):
        # 包含执行和确认状态
        self._states = {
            AgentState.IDLE: IdleState(self),
            AgentState.THINKING: WorkerThinkingState(self),
            AgentState.EXECUTING: ExecutingState(self),
            AgentState.WAITING_CONFIRMATION: WaitingConfirmationState(self),
            AgentState.COMPLETED: CompletedState(self),
            AgentState.ERROR: ErrorState(self)
        }
        self._current_state = self._states[AgentState.IDLE]

    # def get_judge_agent(self) -> BaseAgent:
    #     if hasattr(self.agent, 'judge_agent'):
    #         return self.agent.judge_agent
    #     else:
    #         return None

class JudgeStateMachine(BaseStateMachine):
    """
    简单的评审状态机
    """
    
    def __init__(self):
        super().__init__(AgentState.IDLE)
        self._setup_states()

    def _setup_states(self):

        self._states = {
            AgentState.IDLE: IdleState(self),
            AgentState.THINKING: JudgeState(self),
            AgentState.COMPLETED: CompletedState(self),
            AgentState.ERROR: ErrorState(self)
        }
        self._current_state = self._states[AgentState.IDLE]

class CuratorStateMachine(BaseStateMachine):
    """
    知识整理者状态机
    """
    def __init__(self):
        super().__init__(AgentState.IDLE)
        self._setup_states()

    def _setup_states(self):
        self._states = {
            AgentState.IDLE: IdleState(self),
            # THINKING 阶段：分析历史，提取知识点
            AgentState.THINKING: CuratorThinkingState(self), 
            # EXECUTING 阶段：调用本地工具进行文件 IO 操作
            AgentState.WAITING_CONFIRMATION: WaitingConfirmationState(self),
            AgentState.EXECUTING: ExecutingState(self), 
            AgentState.COMPLETED: CompletedState(self),
            AgentState.ERROR: ErrorState(self)
        }
        self._current_state = self._states[AgentState.IDLE]