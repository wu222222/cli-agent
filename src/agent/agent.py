import asyncio
import json
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum

from src.logger import get_logger
from src.llm import LLMClient, LLMConfig
from .context import ContextManager
from .prompt import PromptManager
from .tools import ToolRegistry, Tool

logger = get_logger(__name__)


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING_CONFIRMATION = "waiting_confirmation"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class AgentResponse:
    content: str
    action_type: str  # execute_command, read_file, write_file, stop
    action_params: Dict[str, Any]
    requires_confirmation: bool = False
    confirmation_prompt: str = ""
    is_final_answer: bool = False  # 是否是最终回答


class Agent:
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        context_manager: Optional[ContextManager] = None,
        prompt_manager: Optional[PromptManager] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.llm_client = llm_client or LLMClient()
        self.context = context_manager or ContextManager()
        self.prompts = prompt_manager or PromptManager()
        self.tools = tool_registry or ToolRegistry()
        self.state = AgentState.IDLE
        self.max_iterations = 5
        self._confirmation_handler: Optional[Callable] = None

        self._setup_system_prompt()

    def _setup_system_prompt(self) -> None:
        system_prompt = self.prompts.get_system_prompt()
        self.context.set_system_prompt(system_prompt)

    def register_tool(self, tool: Tool) -> None:
        self.tools.register(tool)
        self._setup_system_prompt()

    def set_confirmation_handler(self, handler: Callable[[str], bool]) -> None:
        self._confirmation_handler = handler

    def _parse_action(self, response_text: str) -> Optional[Dict[str, Any]]:
        """解析LLM响应中的action"""
        try:
            # 提取JSON内容
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()

            data = json.loads(json_str)
            return data.get("action", {})
        except (json.JSONDecodeError, IndexError):
            return None

    async def run(self, user_input: str) -> str:
        self.state = AgentState.THINKING
        self.context.add_user_message(user_input)

        try:
            for iteration in range(self.max_iterations):
                logger.info(f"ReAct 迭代 {iteration + 1}/{self.max_iterations}")

                response = await self._think()

                # logger.debug(f"ReAct 响应: {response}")
                # 如果是最终回答，直接返回
                if response.is_final_answer:
                    self.state = AgentState.COMPLETED
                    return response.action_params.get("answer", response.content)

                # 如果需要确认
                if response.requires_confirmation:
                    self.state = AgentState.WAITING_CONFIRMATION
                    if self._confirmation_handler:
                        confirmed = self._confirmation_handler(response.confirmation_prompt)
                        if not confirmed:
                            return "操作已取消"
                    self.state = AgentState.EXECUTING

                # 执行action
                if response.action_type and response.action_type != "stop":
                    self.state = AgentState.EXECUTING
                    observation = await self._execute_action(response.action_type, response.action_params)
                    
                    # 添加assistant消息和工具结果到上下文
                    self.context.add_assistant_message(response.content)
                    self.context.add_tool_result(
                        response.action_type,
                        observation
                    )
                else:
                    # 没有action或stop action，返回内容
                    self.context.add_assistant_message(response.content)
                    self.state = AgentState.COMPLETED
                    return response.content

            return "达到最大迭代次数，任务未完成"

        except Exception as e:
            self.state = AgentState.ERROR
            logger.error(f"Agent 执行错误: {e}")
            return f"执行错误: {str(e)}"

    async def _think(self) -> AgentResponse:
        messages = self.context.get_messages()

        try:
            response_text = await self.llm_client.achat(messages)
            logger.debug(f"LLM 响应: {response_text}")

            action = self._parse_action(response_text)

            if action:
                action_type = action.get("type", "")
                action_params = action.get("parameters", {})

                # 处理 stop action
                if action_type == "stop":
                    return AgentResponse(
                        content=response_text,
                        action_type="stop",
                        action_params=action_params,
                        is_final_answer=True
                    )

                # 处理 execute_command action
                if action_type == "execute_command":
                    command = action_params.get("command", "")
                    return AgentResponse(
                        content=response_text,
                        action_type="execute_command",
                        action_params=action_params,
                        requires_confirmation=True,
                        confirmation_prompt=f"是否执行以下命令?\n{command}"
                    )

                # 处理其他 actions
                return AgentResponse(
                    content=response_text,
                    action_type=action_type,
                    action_params=action_params
                )

            # 没有action，直接返回内容
            return AgentResponse(
                content=response_text,
                action_type="stop",
                action_params={"answer": response_text},
                is_final_answer=True
            )

        except Exception as e:
            logger.error(f"思考过程错误: {e}")
            raise

    async def _execute_action(self, action_type: str, action_params: Dict[str, Any]) -> str:
        """执行action"""
        logger.info(f"执行action: {action_type}, 参数: {action_params}")

        # 通过工具注册表执行工具
        result = self.tools.execute_tool(action_type, action_params)
        logger.debug(f"工具执行结果: {result}")
        return result

    def get_state(self) -> AgentState:
        return self.state

    def get_context_summary(self) -> str:
        return self.context.get_context_summary()

    def clear_context(self) -> None:
        self.context.clear()
        self._setup_system_prompt()

    async def chat(self, message: str) -> str:
        return await self.run(message)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.llm_client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.llm_client.aclose()
