import asyncio
import json
from typing import Dict, Any, Optional, Callable
from pydantic import ValidationError

from src.logger import get_logger
from src.llm import LLMClient, LLMConfig

from .statemachine import WorkerStateMachine,JudgeStateMachine
from .types import *
from .base import BaseAgent,BaseStateMachine

from src.agent.context import ContextManager
from src.agent.prompt import PromptManager
from src.agent.tools import ToolRegistry


logger = get_logger(__name__)

class WorkerAgent(BaseAgent):
    """工作代理，负责执行实际的任务"""
    def __init__(
        self, 
        name: str = "WorkerAgent", 
        llm_client: Optional[LLMClient] = None,
        context_manager: Optional[ContextManager] = None,
        prompt_manager: Optional[PromptManager] = None,
        tool_registry: Optional[ToolRegistry] = None,
        judge_agent: Optional["JudgeAgent"] = None,
        ):
        # 再调用父类的__init__
        super().__init__(name, llm_client, context_manager,prompt_manager, tool_registry)
        
    
    def _setup_system_prompt(self) -> None:
        system_prompt = self.prompt_manager._build_worker_prompt()
        self.context_manager.set_system_prompt(self.name,system_prompt)

    def _create_state_machine(self) -> BaseStateMachine:
        return WorkerStateMachine()

    def _prepare_context(self,input:str = None) -> None:
        """上下文控制流"""
        if input:
            self.context_manager.add_user_message(self.name,input, receivers=[self.name])

    def _parse_action(self, response_text: str) -> Optional[LLMOutput]:
        """解析 LLM 响应并返回结构化的 LLMOutput 对象"""
        try:
            # 1. 提取 JSON 字符串
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()

            # 2. 解析 JSON
            data = json.loads(json_str)
            
            # 3. 使用 Pydantic 进行结构校验
            # 这一步会自动检查 thought 和 action 字段是否存在
            return LLMOutput.model_validate(data)
        
        except (json.JSONDecodeError, IndexError, ValidationError) as e:
            logger.warning(f"JSON 解析或结构校验失败: {e}")
            return None

    async def _think(self) -> AgentResponse:
        messages = self.context_manager.get_agent_messages(agent_name=self.name)

        try:
            # 1. 调用 LLM
            response_text = await self.llm_client.achat(messages)
            logger.debug(f"LLM 响应原始文本: {response_text}")

            # 2. 解析 JSON 结构
            llm_output = self._parse_action(response_text)
            
            if not llm_output:
                # 解析失败的兜底逻辑
                return AgentResponse(
                    thought="解析失败，尝试直接回答",
                    content=response_text,
                    action_type=ActionType.STOP,
                    action_params={"answer": response_text}
                )

            # 此时你可以直接访问 llm_output.thought 和 llm_output.action
            raw_type = llm_output.action.type
            action_params = llm_output.action.parameters
            try:
                action_type = ActionType(raw_type)
            except ValueError:
                logger.warning(f"未知的类型: {raw_type}，设为 STOP")
                action_type = ActionType.STOP

            agent_resp = AgentResponse(
                thought=llm_output.thought, # 结构化存储思考
                content=response_text,
                action_type=action_type,
                action_params=action_params
            )
                
            # 执行 Schema 校验（这一步会检查参数是否符合 base.py 里的定义）
            agent_resp.validate_params()

            return agent_resp

        except Exception as e:
            logger.error(f"WorkerAgent 思考过程出错: {e}")
            raise


class JudgeAgent(BaseAgent):
    """评审代理，负责检查 Worker 的任务完成质量"""
    
    def __init__(
        self,
        name: str = "JudgeAgent",
        llm_client: Optional[LLMClient] = None,
        context_manager: Optional[ContextManager] = None,
        prompt_manager: Optional[PromptManager] = None,
        tool_registry: Optional[ToolRegistry] = None,
        ):
        # 再调用父类的__init__
        super().__init__(name, llm_client, context_manager,prompt_manager, tool_registry)

    def _setup_system_prompt(self) -> None:
        system_prompt = self.prompt_manager._build_judge_prompt()
        self.context_manager.set_system_prompt(self.name,system_prompt)

    def _create_state_machine(self) -> BaseStateMachine:
        # Judge 通常只需要单次思考或简单的状态机
        return JudgeStateMachine()
    
    def _execute_action(self, action_type: ActionType, action_params: Dict[str, Any]) -> str:
        return super()._execute_action(action_type, action_params)

    def _parse_action(self, response_text: str) -> Optional[LLMOutput]:
        """解析 LLM 响应并返回结构化的 LLMOutput 对象"""
        try:
            # 1. 提取 JSON 字符串
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()

            # 2. 解析 JSON
            data = json.loads(json_str)
            
            # 3. 使用 Pydantic 进行结构校验
            # 这一步会自动检查 thought 和 action 字段是否存在
            return LLMOutput.model_validate(data)
        
        except (json.JSONDecodeError, IndexError, ValidationError) as e:
            logger.warning(f"JSON 解析或结构校验失败: {e}")
            return None

    def _prepare_context(self, input: Message = None) -> None:
        """接受 Worker 的操作记录，添加到上下文管理器"""
        if isinstance(input, Message):
            self.context_manager.add_assistant_message(input.sender, input.content, input.receivers)
        else:
            logger.warning(f"JudgeAgent 接收的输入不是 Message 类型: {input}")

    async def run(self,input:Message = None) -> str:
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
                    return data
                
                if self.state_machine.is_in_state(AgentState.ERROR):
                    return f"[{self.name}] 执行出错"

            return "达到最大迭代次数"
        except Exception as e:
            self.state_machine.transition(AgentState.ERROR, data=ErrorData(error_message=str(e)))
            return f"系统崩溃: {str(e)}"

    async def _think(self) -> AgentResponse:
        messages = self.context_manager.get_agent_messages(agent_name=self.name,include_system_prompt=True)
        # return None
        response_text = await self.llm_client.achat(messages)
        
        # 使用我们之前写好的通用解析逻辑
        llm_output = self._parse_action(response_text)

        if not llm_output:
                # 解析失败的兜底逻辑
                return AgentResponse(
                    thought="解析失败，尝试直接回答",
                    content=response_text,
                    action_type=ActionType.STOP,
                    action_params={"answer": response_text}
                )
        
        raw_type = llm_output.action.type
        action_params = llm_output.action.parameters
        try:
            action_type = ActionType(raw_type)
        except ValueError:
            logger.warning(f"未知的类型: {raw_type}，设为 STOP")
            action_type = ActionType.STOP

        agent_resp = AgentResponse(
            thought=llm_output.thought, # 结构化存储思考
            content=response_text,
            action_type=action_type,
            action_params=action_params
        )
            
        # 执行 Schema 校验（这一步会检查参数是否符合 base.py 里的定义）
        agent_resp.validate_params()

        return agent_resp

class CuratorAgent(BaseAgent):
    """CuratorAgent，负责管理知识库"""
    def __init__(
        self,
        name: str = "CuratorAgent",
        llm_client: Optional[LLMClient] = None,
        context_manager: Optional[ContextManager] = None,
        prompt_manager: Optional[PromptManager] = None,
        tool_registry: Optional[ToolRegistry] = None,
        ):
        # 再调用父类的__init__
        super().__init__(name, llm_client, context_manager,prompt_manager, tool_registry)
    
    def _setup_system_prompt(self) -> None:
        system_prompt = self.prompt_manager._build_judge_prompt()
        self.context_manager.set_system_prompt(self.name,system_prompt)

    def _create_state_machine(self) -> BaseStateMachine:
        return JudgeStateMachine()
    
    def _execute_action(self, action_type: ActionType, action_params: Dict[str, Any]) -> str:
        return super()._execute_action(action_type, action_params)

