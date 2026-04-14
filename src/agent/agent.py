import asyncio
import json
from typing import Dict, Any, Optional, Callable


from src.logger import get_logger
from src.llm import LLMClient, LLMConfig
from .context import ContextManager
from .prompt import PromptManager
from .tools import ToolRegistry, Tool
from .statemachine import AgentStateMachine
from .base import AgentResponse, AgentState

logger = get_logger(__name__)



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
        self.state_machine = AgentStateMachine()
        self.max_iterations = 5
        self._confirmation_handler: Optional[Callable] = None

        self._setup_system_prompt()
        self.state_machine.set_agent(self)  # 设置关联的Agent实例


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
            logger.warning(f"无法解析action: {response_text}")
            return None

    async def run(self, user_input: str) -> str:
        # 初始化：向上下文添加用户输入，并进入起始状态
        self.context.add_user_message(user_input)
        self.state_machine.transition(AgentState.THINKING)

        try:
            for iteration in range(self.max_iterations):
                logger.info(f"ReAct 迭代 {iteration + 1}/{self.max_iterations}")

                # 核心逻辑：执行当前状态，并根据返回值自动切换到下一个状态
                # 每个 State.execute 会根据业务逻辑返回下一个 AgentState 枚举
                transition = await self.state_machine.execute()
                
                # 获取参数
                next_state_enum = transition.state
                data = transition.data

                # 执行状态转换（内部会触发 on_exit 和 on_enter）
                if not self.state_machine.transition(next_state_enum, data):
                    logger.error(f"非法状态转换: {self.state_machine.get_state()} -> {next_state_enum}")
                    return "状态转换错误"

                # 检查是否结束
                if self.state_machine.is_in_state(AgentState.COMPLETED):
                    return self.context.get_final_answer()
                
                if self.state_machine.is_in_state(AgentState.ERROR):
                    return "任务执行出错，已终止"

            return "达到最大迭代次数，任务未完成"

        except Exception as e:
            self.state_machine.transition(AgentState.ERROR, error=str(e))
            return f"系统崩溃: {str(e)}"

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
                        action_params=action_params
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
                action_params={"answer": response_text}
            )

        except Exception as e:
            logger.error(f"思考过程错误: {e}")
            raise

    async def _execute_action(self, action_type: str, action_params: Dict[str, Any]) -> str:
        """执行action"""
        logger.info(f"执行action: {action_type}, 参数: {action_params}")

        # 通过工具注册表执行工具
        result = self.tools.execute_tool(action_type, action_params)
        logger.info(f"工具执行结果: {result}")
        return result

    def get_state(self) -> AgentState:
        return self.state_machine.get_state()

    def get_context_summary(self) -> str:
        return self.context.get_context_summary()

    def clear_context(self) -> None:
        self.context.clear()
        self._setup_system_prompt()
        self.state_machine.reset()

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
