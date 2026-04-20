import asyncio
import json
from typing import Dict, Any, Optional, Callable
from pydantic import ValidationError

from src.logger import get_logger
from src.llm import LLMClient, LLMConfig

from .statemachine import WorkerStateMachine
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
        prompt_manager: Optional[PromptManager] = None,
        context_manager: Optional[ContextManager] = None,
        tool_registry: Optional[ToolRegistry] = None,
        ):
        # 再调用父类的__init__
        super().__init__(name, llm_client, prompt_manager, context_manager, tool_registry)

    
    def _setup_system_prompt(self) -> None:
        system_prompt = self.prompt_manager._build_worker_prompt()
        self.context_manager.set_system_prompt(system_prompt)

    def _create_state_machine(self) -> BaseStateMachine:
        return WorkerStateMachine()

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
        messages = self.context_manager.get_messages()

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

            # 5. 业务逻辑增强：处理确认逻辑和提示词
            # self._enrich_action_logic(agent_resp)

            return agent_resp

        except Exception as e:
            logger.error(f"WorkerAgent 思考过程出错: {e}")
            raise

    # def _enrich_action_logic(self, resp: AgentResponse) -> None:
    #     """
    #     专门处理特定 Action 的业务增强逻辑（如确认提示词、安全检查）
    #     """
    #     if resp.action_type == ActionType.EXECUTE_COMMAND:
    #         command = resp.action_params.get("command", "")
            
    #         # 标记需要人工确认
    #         resp.requires_confirmation = True
    #         resp.confirmation_prompt = f"⚠️ 准备执行 Shell 命令:\n  > {command}\n是否允许？"
            
    #     elif resp.action_type == ActionType.STOP:
    #         # 如果 stop 参数里没 answer，把 content 补进去
    #         if "answer" not in resp.action_params:
    #             resp.action_params["answer"] = resp.content


    async def _execute_action(self, action_type: ActionType, action_params: Dict[str, Any]) -> str:
        """执行action"""
        logger.info(f"执行action: {action_type}, 参数: {action_params}")
        # 通过工具注册表执行工具
        result = await self.tools.execute_tool(action_type.value, action_params)
        logger.info(f"工具执行结果: {result}")
        return result

# class Agent:
#     def __init__(
#         self,
#         name: str,
#         llm_client: Optional[LLMClient] = None,
#         context_manager: Optional[ContextManager] = None,
#         prompt_manager: Optional[PromptManager] = None,
#         tool_registry: Optional[ToolRegistry] = None,
#     ):
#         self.name = name
#         self.llm_client = llm_client or LLMClient()
#         self.context = context_manager or ContextManager()
#         self.prompts = prompt_manager or PromptManager()
#         self.tools = tool_registry or ToolRegistry()
#         self.state_machine = AgentStateMachine()
#         self.max_iterations = 10
#         self._confirmation_handler: Optional[Callable] = None

#         self._setup_system_prompt()
#         self.state_machine.set_agent(self)  # 设置关联的Agent实例


#     def _setup_system_prompt(self) -> None:
#         system_prompt = self.prompts.get_system_prompt(self.name)
#         self.context.set_system_prompt(system_prompt)

#     def register_tool(self, tool: Tool) -> None:
#         self.tools.register(tool)
#         self._setup_system_prompt()

#     def set_confirmation_handler(self, handler: Callable[[str], bool]) -> None:
#         self._confirmation_handler = handler

#     def _parse_action(self, response_text: str) -> Optional[Dict[str, Any]]:
#         """解析LLM响应中的action"""
#         try:
#             # 提取JSON内容
#             if "```json" in response_text:
#                 json_str = response_text.split("```json")[1].split("```")[0].strip()
#             elif "```" in response_text:
#                 json_str = response_text.split("```")[1].split("```")[0].strip()
#             else:
#                 json_str = response_text.strip()

#             data = json.loads(json_str)
#             return data.get("action", {})
#         except (json.JSONDecodeError, IndexError):
#             logger.warning(f"无法解析action: {response_text}")
#             return None

#     async def run(self, user_input: str) -> str:
#         # 初始化：向上下文添加用户输入，并进入起始状态
#         self.context.add_user_message(user_input)
#         self.state_machine.transition(AgentState.THINKING)

#         try:
#             for iteration in range(self.max_iterations):
#                 logger.info(f"ReAct 迭代 {iteration + 1}/{self.max_iterations}")

#                 # 核心逻辑：执行当前状态，并根据返回值自动切换到下一个状态
#                 # 每个 State.execute 会根据业务逻辑返回下一个 AgentState 枚举
#                 transition = await self.state_machine.execute()
                
#                 # 获取参数
#                 next_state_enum = transition.state
#                 data = transition.data
#                 if data is None:
#                     data = {}

#                 # 执行状态转换（内部会触发 on_exit 和 on_enter）
#                 if not self.state_machine.transition(next_state_enum, **data):
#                     logger.error(f"非法状态转换: {self.state_machine.get_state()} -> {next_state_enum}")
#                     return "状态转换错误"

#                 # 检查是否结束
#                 if self.state_machine.is_in_state(AgentState.COMPLETED):
#                     return self.context.get_final_answer()
                
#                 if self.state_machine.is_in_state(AgentState.ERROR):
#                     return "任务执行出错，已终止"

#             return "达到最大迭代次数，任务未完成"

#         except Exception as e:
#             self.state_machine.transition(AgentState.ERROR, error=str(e))
#             return f"系统崩溃: {str(e)}"

#     async def _think(self) -> AgentResponse:
#         messages = self.context.get_messages()

#         try:
#             response_text = await self.llm_client.achat(messages)
#             logger.debug(f"LLM 响应: {response_text}")

#             action = self._parse_action(response_text)

#             if action:
#                 action_type = action.get("type", "")
#                 action_params = action.get("parameters", {})

#                 # 处理 stop action
#                 if action_type == "stop":
#                     return AgentResponse(
#                         content=response_text,
#                         action_type="stop",
#                         action_params=action_params
#                     )

#                 # 处理 execute_command action
#                 if action_type == "execute_command":
#                     command = action_params.get("command", "")
#                     return AgentResponse(
#                         content=response_text,
#                         action_type="execute_command",
#                         action_params=action_params,
#                         requires_confirmation=True,
#                         confirmation_prompt=f"是否执行以下命令?\n{command}"
#                     )

#                 # 处理其他 actions
#                 return AgentResponse(
#                     content=response_text,
#                     action_type=action_type,
#                     action_params=action_params
#                 )

#             # 没有action，直接返回内容
#             return AgentResponse(
#                 content=response_text,
#                 action_type="stop",
#                 action_params={"answer": response_text}
#             )

#         except Exception as e:
#             logger.error(f"思考过程错误: {e}")
#             raise

#     async def _execute_action(self, action_type: str, action_params: Dict[str, Any]) -> str:
#         """执行action"""
#         logger.info(f"执行action: {action_type}, 参数: {action_params}")

#         # 通过工具注册表执行工具
#         result = self.tools.execute_tool(action_type, action_params)
#         logger.info(f"工具执行结果: {result}")
#         return result

#     def get_state(self) -> AgentState:
#         return self.state_machine.get_state()

#     def get_context_summary(self) -> str:
#         return self.context.get_context_summary()

#     def clear_context(self) -> None:
#         self.context.clear()
#         self._setup_system_prompt()
#         self.state_machine.reset()

#     async def chat(self, message: str) -> str:
#         return await self.run(message)

#     def __enter__(self):
#         return self

#     def __exit__(self, exc_type, exc_val, exc_tb):
#         self.llm_client.close()

#     async def __aenter__(self):
#         return self

#     async def __aexit__(self, exc_type, exc_val, exc_tb):
#         await self.llm_client.aclose()
