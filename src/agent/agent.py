from typing import Optional, Any

from src.logger import get_logger
from src.llm import LLMClient

from .statemachine import WorkerStateMachine, JudgeStateMachine, CuratorStateMachine
from .types import *
from .base import BaseAgent, BaseStateMachine

from src.agent.context import ContextManager
from src.agent.prompt import PromptManager
from src.agent.tools import ToolRegistry

# Agent 策略预设
AGENT_POLICIES = {
    "worker": ContextPolicy(
        tool_full_turns=2, tool_truncate_turns=5, tool_max_turns=8,
        summary_enabled=True, summary_interval=6,
        keep_user_messages=True, keep_errors=True,
    ),
    "judge": ContextPolicy(
        tool_full_turns=0, tool_truncate_turns=0, tool_max_turns=3,
        summary_enabled=False,
        keep_user_messages=True, keep_errors=True,
    ),
    "curator": ContextPolicy(
        tool_full_turns=0, tool_truncate_turns=3, tool_max_turns=20,
        summary_enabled=False,
        keep_user_messages=True, keep_errors=True,
    ),
}


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
        tool_names: Optional[list] = None,
        context_policy: Optional[ContextPolicy] = None,
    ):
        self._tool_names = tool_names
        if context_policy and context_manager:
            context_manager.policy = context_policy
        super().__init__(name, llm_client, context_manager, prompt_manager, tool_registry)

    def _setup_system_prompt(self) -> None:
        system_prompt = self.prompt_manager._build_worker_prompt(
            tool_registry=self.tools,
            tool_names=self._tool_names,
        )
        logger.info(f"WorkerAgent 系统提示词已生成，工具列表: {self._tool_names}")
        self.context_manager.set_system_prompt(self.name, system_prompt)

    def _create_state_machine(self) -> BaseStateMachine:
        return WorkerStateMachine()

    def _prepare_context(self, input: str = None) -> None:
        if input:
            self.context_manager.add_user_message(self.name, input, receivers=[self.name])

    async def _think(self) -> AgentResponse:
        messages = self.context_manager.get_agent_messages(agent_name=self.name)

        try:
            response_text = await self.llm_client.achat(messages)
            logger.debug(f"LLM 响应原始文本: {response_text}")

            llm_output = self._parse_action(response_text)

            if not llm_output:
                return AgentResponse(
                    thought="解析失败，尝试直接回答",
                    content=response_text,
                    action_type=ActionType.STOP,
                    action_params={"answer": response_text}
                )

            raw_type = llm_output.action.type
            action_params = llm_output.action.parameters
            llm_tool_name = llm_output.action.tool_name

            # 解析动作类型和工具名
            effective_tool = llm_tool_name or raw_type
            action_type, found = ActionType.from_raw(raw_type)

            logger.info(f"LLM 返回: type={raw_type!r}, tool_name={llm_tool_name!r}, effective={effective_tool!r}")

            if not found:
                # raw_type 不是 ActionType，查 ToolRegistry 的 bound_action
                bound = self.tools.resolve_action(effective_tool)
                if bound:
                    action_type = bound
                    logger.info(f"工具 '{effective_tool}' 绑定动作: {bound.value}")
                else:
                    logger.warning(f"未知的工具/动作: {effective_tool}，设为 STOP")
                    action_type = ActionType.STOP

            # tool_name 始终设置为 effective_tool（不管工具是否注册）
            # 未注册的错误在 ToolRegistry.run() 中处理
            tool_name = effective_tool

            # 强制限制：如果配置了 tool_names，LLM 选择的工具必须在列表内
            # 但 STOP 动作不受限制（LLM 可以随时选择停止）
            if self._tool_names and action_type != ActionType.STOP and tool_name not in self._tool_names:
                logger.warning(f"WorkerAgent LLM 选择了 '{tool_name}'，但仅允许 {self._tool_names}，优雅降为 STOP")
                action_type = ActionType.STOP
                action_params = {"answer": llm_output.thought or "任务已完成"}
                tool_name = "stop"

            agent_resp = AgentResponse(
                thought=llm_output.thought,
                content=response_text,
                action_type=action_type,
                action_params=action_params,
                tool_name=tool_name,
            )

            # 参数校验（仅对 ACTION_SCHEMA_MAP 中定义的动作）
            if action_type in ACTION_SCHEMA_MAP:
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
        super().__init__(name, llm_client, context_manager, prompt_manager, tool_registry)

    def _setup_system_prompt(self) -> None:
        system_prompt = self.prompt_manager._build_judge_prompt()
        self.context_manager.set_system_prompt(self.name, system_prompt)

    def _create_state_machine(self) -> BaseStateMachine:
        return JudgeStateMachine()

    def _prepare_context(self, input: Message = None) -> None:
        if isinstance(input, Message):
            self.context_manager.add_assistant_message(input.sender, input.content, input.receivers)
        else:
            logger.warning(f"JudgeAgent 接收的输入不是 Message 类型: {input}")

    def _get_final_result(self) -> Any:
        sm = self.state_machine
        completed = sm._states.get(AgentState.COMPLETED)
        if completed and hasattr(completed, 'temp_data') and completed.temp_data:
            return completed.temp_data
        return super()._get_final_result()

    async def _think(self) -> AgentResponse:
        messages = self.context_manager.get_agent_messages(agent_name=self.name, include_system_prompt=True)
        response_text = await self.llm_client.achat(messages)

        llm_output = self._parse_action(response_text)

        if not llm_output:
            return AgentResponse(
                thought="解析失败，尝试直接回答",
                content=response_text,
                action_type=ActionType.STOP,
                action_params={"answer": response_text},
                tool_name="stop",
            )

        raw_type = llm_output.action.type
        # JudgeAgent 的 LLM 可能返回 "review"，映射到 LOCAL_CALL
        if raw_type == "review":
            action_type = ActionType.LOCAL_CALL
        else:
            action_type, _ = ActionType.from_raw(raw_type)

        tool_name = llm_output.action.tool_name or raw_type

        agent_resp = AgentResponse(
            thought=llm_output.thought,
            content=response_text,
            action_type=action_type,
            action_params=llm_output.action.parameters,
            tool_name=tool_name,
        )

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
        tool_names: Optional[list] = None,
    ):
        self._tool_names = tool_names
        super().__init__(name, llm_client, context_manager, prompt_manager, tool_registry)

    def _setup_system_prompt(self) -> None:
        system_prompt = self.prompt_manager._build_curator_prompt(
            tool_registry=self.tools,
            tool_names=self._tool_names,
        )
        self.context_manager.set_system_prompt(self.name, system_prompt)

    def _prepare_context(self, input: str | dict | Message = None) -> None:
        if isinstance(input, str):
            self.context_manager.add_user_message(self.name, input, [self.name])
        else:
            logger.warning(f"CuratorAgent 接收的输入不是 str 类型: {input}")

    def _create_state_machine(self) -> BaseStateMachine:
        return CuratorStateMachine()

    async def _think(self) -> AgentResponse:
        messages = self.context_manager.get_all_messages(agent_name=self.name, include_system_prompt=True)

        try:
            response_text = await self.llm_client.achat(messages)
            logger.debug(f"LLM 响应原始文本: {response_text}")

            llm_output = self._parse_action(response_text)

            if not llm_output:
                return AgentResponse(
                    thought="解析失败，尝试直接回答",
                    content=response_text,
                    action_type=ActionType.STOP,
                    action_params={"answer": response_text},
                    tool_name="stop",
                )

            raw_type = llm_output.action.type
            # CuratorAgent 只支持 EXECUTE_COMMAND 和 STOP
            if raw_type in ("curate", "local_call", "execute_command"):
                action_type = ActionType.EXECUTE_COMMAND
            else:
                action_type, _ = ActionType.from_raw(raw_type)

            tool_name = llm_output.action.tool_name or raw_type

            # 强制限制：如果配置了 tool_names，LLM 选择的工具必须在列表内
            if self._tool_names and tool_name not in self._tool_names:
                override = self._tool_names[0]
                logger.warning(f"CuratorAgent LLM 选择了 '{tool_name}'，但仅允许 {self._tool_names}，强制覆盖为 '{override}'")
                tool_name = override

            agent_resp = AgentResponse(
                thought=llm_output.thought,
                content=response_text,
                action_type=action_type,
                action_params=llm_output.action.parameters,
                tool_name=tool_name,
            )

            # 校验时优先用工具的独立 param_schema
            tool_schema = None
            if tool_name and self.tools:
                t = self.tools.get_tool(tool_name)
                if t and t.param_schema:
                    tool_schema = t.param_schema
            agent_resp.validate_params(tool_param_schema=tool_schema)
            return agent_resp

        except Exception as e:
            logger.error(f"CuratorAgent 思考过程出错: {e}")
            raise


# ============================================================
# Agent 类型注册 — 加新 Agent 类型只需在此加一条
# ============================================================

from .registry import AgentConfig, register_agent
from .statemachine import WorkerStateMachine, JudgeStateMachine, CuratorStateMachine

register_agent(AgentConfig(
    agent_type="worker",
    base_class=WorkerAgent,
    state_machine_class=WorkerStateMachine,
    prompt_method="_build_worker_prompt",
    tool_filter="config",
    route_api="/agent/chat",
))

register_agent(AgentConfig(
    agent_type="curator",
    base_class=CuratorAgent,
    state_machine_class=CuratorStateMachine,
    prompt_method="_build_curator_prompt",
    tool_filter="all_matching",
    auto_start_containers=True,
    route_api="/agent/curator",
))

register_agent(AgentConfig(
    agent_type="judge",
    base_class=JudgeAgent,
    state_machine_class=JudgeStateMachine,
    prompt_method="_build_judge_prompt",
    tool_filter="all_matching",
    auto_start_containers=False,
    route_api=None,  # 不直接暴露给用户
))
