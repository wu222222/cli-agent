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

        # 存储 thought，供 StreamingAgent 发送 SSE thought 事件
        self.agent.last_thought = self.response.thought or ""

        logger.debug(f"状态{self.state},response:{self.response}")

        match self.response.action_type:
            case ActionType.STOP:
                answer = self.response.action_params.get("answer", self.response.content)
                self.agent.context_manager.add_assistant_message(self.agent.name,self.response.content,[self.agent.name])
                self.agent.context_manager.set_final_answer(answer)
                return StateTransition(state=AgentState.COMPLETED)

            case ActionType.EXECUTE_COMMAND:
                tool = self.agent.tools.get_tool(self.response.tool_name) if self.response.tool_name else None
                if not tool:
                    error_msg = f"工具 '{self.response.tool_name}' 未注册或不可用。请在工具设置页面启动对应容器，或使用 stop 动作直接告知用户。"
                    logger.warning(error_msg)
                    self.agent.context_manager.add_tool_result(
                        agent_name=self.agent.name,
                        tool_name=self.response.tool_name or "unknown",
                        result=error_msg,
                    )
                    return StateTransition(
                        state=AgentState.THINKING,
                        data=ExecutionResultData(observation=error_msg, action_type=self.response.action_type),
                    )
                needs_confirm = tool.requires_confirmation
                if needs_confirm:
                    command = self.response.action_params.get('command', '')
                    thought = self.response.thought or ''
                    prompt = f"[思考] {thought}\n\n[命令] {command}\n\n是否允许执行以上命令?" if thought else f"是否允许执行: {command}?"
                    out_data = ThinkingToExecutingData(
                        response=self.response,
                        confirmation_prompt=prompt
                    )
                    return StateTransition(state=AgentState.WAITING_CONFIRMATION, data=out_data)
                return StateTransition(
                    state=AgentState.EXECUTING, 
                    data=ThinkingToExecutingData(response=self.response)
                )

            case ActionType.LOCAL_CALL:
                return StateTransition(
                    state=AgentState.EXECUTING,
                    data=ThinkingToExecutingData(response=self.response)
                )

            case _:
                return StateTransition(
                    state=AgentState.EXECUTING, 
                    data=ThinkingToExecutingData(response=self.response)
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
        self._user_guidance = ""
        if isinstance(data, ThinkingToExecutingData):
            self.response = data.response
            self._user_guidance = data.user_guidance or ""
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
                tool_name = self.response.tool_name or self.response.action_type.value
                tool = self.agent.tools.get_tool(tool_name)
                if not tool:
                    error_msg = f"工具 '{tool_name}' 未注册或不可用。请使用 stop 动作告知用户当前环境限制。"
                    logger.error(error_msg)
                    self.agent.context_manager.add_tool_result(
                        agent_name=self.agent.name,
                        tool_name=tool_name,
                        result=error_msg,
                    )
                    return StateTransition(
                        state=AgentState.THINKING,
                        data=ExecutionResultData(observation=error_msg, action_type=self.response.action_type),
                    )

                observation = await self.agent._execute_action(
                    self.response.action_type,
                    self.response.action_params,
                    self.response.tool_name,
                )
                # 如果有用户引导，追加到工具结果
                if self._user_guidance:
                    observation = f"{observation}\n\n[用户引导] {self._user_guidance}"
                # 添加assistant消息和工具结果到上下文
                self.agent.context_manager.add_assistant_message(self.agent.name,self.response.content,[self.agent.name])
                self.agent.context_manager.add_tool_result(
                    agent_name=self.agent.name,
                    tool_name=self.response.tool_name or self.response.action_type.value,
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

        # 确认需求由 tool.requires_confirmation 决定（非 ThinkingToExecutingData 字段）
        resp = self.data.response
        tool = self.agent.tools.get_tool(resp.tool_name) if resp.tool_name else None
        needs_confirm = tool.requires_confirmation if tool else False

        if not needs_confirm:
            return StateTransition(state=AgentState.EXECUTING, data=self.data)

        # 处理需要确认的情况
        # 检查 self.data.confirmed（由外部在调用 step() 前设置）
        if self.data.confirmed is None:
            # 情况 A: 用户还没点按钮，继续保持原地挂起
            return StateTransition(state=AgentState.WAITING_CONFIRMATION, data=self.data)

        if self.data.confirmed is True:
            # 情况 B: 用户点允许（可选带引导）
            return StateTransition(state=AgentState.EXECUTING, data=self.data)
        else:
            # 情况 C: 用户点拒绝
            if self.data.user_guidance:
                # 有引导 → 注入 tool_result，回到 THINKING 重新思考
                tool_name = resp.tool_name or resp.action_type.value
                guidance_result = f"[用户拒绝执行并提供引导] {self.data.user_guidance}"
                self.agent.context_manager.add_assistant_message(
                    self.agent.name, resp.content, [self.agent.name]
                )
                self.agent.context_manager.add_tool_result(
                    agent_name=self.agent.name,
                    tool_name=tool_name,
                    result=guidance_result,
                )
                return StateTransition(state=AgentState.THINKING, data=self.data)
            else:
                # 无引导 → 终止
                self.agent.context_manager.set_final_answer("操作已被用户取消")
                return StateTransition(state=AgentState.COMPLETED)

    def can_transition_to(self, new_state: AgentState, data: Optional[StateData] = None) -> bool:
        if new_state == AgentState.EXECUTING:
            return True
        elif new_state in [AgentState.COMPLETED, AgentState.ERROR]:
            return True
        return False


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
        # 存储 thought
        self.agent.last_thought = self.response.thought or ""
        # 根据 Judge 的 LOCAL_CALL 结果决定 Worker 的去向
        review_data = self.response.validate_params()

        if review_data.is_passed:
            data = ExecutionResultData(
                observation=f"评审通过,原因：{review_data.reason}",
                action_type=ActionType.LOCAL_CALL,
            )
            return StateTransition(state=AgentState.COMPLETED, data=data)
        else:
            data = ExecutionResultData(
                observation=f"评审打回,原因：{review_data.reason}",
                action_type=ActionType.LOCAL_CALL,
            )
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

        # 存储 thought，供 StreamingAgent 发送 SSE thought 事件
        self.agent.last_thought = self.response.thought or ""

        logger.debug(f"状态{self.state},response:{self.response}")

        match self.response.action_type:
            case ActionType.STOP:
                answer = self.response.action_params.get("answer", self.response.content)
                self.agent.context_manager.add_assistant_message(self.agent.name,self.response.content,[self.agent.name])
                self.agent.context_manager.set_final_answer(answer)
                return StateTransition(state=AgentState.COMPLETED)

            case ActionType.EXECUTE_COMMAND:
                tool = self.agent.tools.get_tool(self.response.tool_name) if self.response.tool_name else None
                needs_confirm = tool.requires_confirmation if tool else False
                if needs_confirm:
                    prompt = f"是否允许执行: {self.response.action_params.get('command')}?"
                    out_data = ThinkingToExecutingData(
                        response=self.response,
                        confirmation_prompt=prompt
                    )
                    return StateTransition(state=AgentState.WAITING_CONFIRMATION, data=out_data)
                return StateTransition(
                    state=AgentState.EXECUTING,
                    data=ThinkingToExecutingData(response=self.response)
                )
            
            case _:
                return StateTransition(
                    state=AgentState.ERROR, 
                    data=ErrorData(error_message=f"不支持的动作类型: {self.response.action_type.value}")
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