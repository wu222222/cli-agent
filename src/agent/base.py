from typing import Dict, Any, Optional, Type
from abc import ABC, abstractmethod
import json

from pydantic import ValidationError

from src.logger import get_logger
from src.agent.context import ContextManager
from src.agent.prompt import PromptManager
from src.agent.tools import ToolRegistry
from src.agent.types import *
from src.llm import LLMClient

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

        self.state_machine = self._create_state_machine()
        self.state_machine.set_agent(self)

        self.max_iterations = 15
        self.last_thought: str = ""

    @abstractmethod
    def _setup_system_prompt(self) -> None:
        pass

    @abstractmethod
    def _create_state_machine(self) -> 'BaseStateMachine':
        pass

    @abstractmethod
    def _prepare_context(self, input: str | dict | Message = None) -> None:
        pass

    async def step(self) -> StateTransition:
        if self.state_machine.is_in_state(AgentState.COMPLETED):
            return StateTransition(state=AgentState.COMPLETED)

        self.context_manager.current_step += 1

        transition = await self.state_machine.execute()

        success = self.state_machine.transition(transition.state, transition.data)

        if not success:
            return StateTransition(
                state=AgentState.ERROR,
                data=ErrorData(error_message=f"Illegal transition to {transition.state}")
            )

        if self.context_manager.should_compress():
            self._fire_compress()

        return transition

    def _fire_compress(self) -> None:
        """Fire-and-forget: run compression in background, don't block Agent"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self._auto_compress())
        except RuntimeError:
            pass

    async def _auto_compress(self) -> None:
        expired = self.context_manager.collect_expired_messages()
        if not expired:
            return
        try:
            text = "\n".join(
                f"[{m.role}] {m.sender}: {m.content[:200]}"
                for m in expired
            )
            compress_tool = self.tools.get_tool("context_compress") if self.tools else None
            if compress_tool and compress_tool.handler:
                await compress_tool.handler(messages_to_compress=text)
            self.context_manager.mark_compressed(expired)
            logger.info(f"Auto-compress done: {len(expired)} messages -> summary")
        except Exception as e:
            logger.warning(f"Auto-compress failed: {e}")

    async def run(self, input: str | dict | Message = None) -> str:
        self._prepare_context(input)
        self.state_machine.transition(AgentState.THINKING)

        try:
            for iteration in range(self.max_iterations):
                transition = await self.state_machine.execute()
                next_state = transition.state
                data = transition.data or {}

                if not self.state_machine.transition(next_state, data):
                    return f"[{self.name}] state transition error"

                if self.state_machine.is_in_state(AgentState.COMPLETED):
                    return self._get_final_result()

                if self.state_machine.is_in_state(AgentState.ERROR):
                    return f"[{self.name}] execution error"

            return "Max iterations reached"
        except Exception as e:
            self.state_machine.transition(AgentState.ERROR, data=ErrorData(error_message=str(e)))
            return f"System error: {str(e)}"

    @abstractmethod
    async def _think(self) -> AgentResponse:
        pass

    def _parse_action(self, response_text: str) -> Optional[LLMOutput]:
        try:
            json_str = self._extract_json(response_text)
            if not json_str:
                return None

            data = json.loads(json_str, strict=False)
            return LLMOutput.model_validate(data)
        except (json.JSONDecodeError, IndexError, ValidationError) as e:
            # 重试：修复 LLM 输出中常见的无效转义（如 Windows 路径中的 \k, \l 等）
            try:
                json_str = self._extract_json(response_text)
                if json_str:
                    fixed = self._fix_invalid_escapes(json_str)
                    if fixed != json_str:
                        data = json.loads(fixed, strict=False)
                        return LLMOutput.model_validate(data)
            except Exception:
                pass
            logger.warning(f"JSON parse or validation failed: {e}")
            if isinstance(e, json.JSONDecodeError) and e.pos:
                logger.debug(f"JSON near error: {repr(json_str[max(0,e.pos-30):e.pos+30])}")
            return None

    @staticmethod
    def _fix_invalid_escapes(s: str) -> str:
        """修复 JSON 字符串中 LLM 产生的无效转义（如 \\k, \\l 等非 JSON 标准转义）"""
        # JSON 允许的转义: \" \\ \/ \b \f \n \r \t \uXXXX
        # 将其他 \X 替换为 \\X（双重转义后等价于字面量 \X）
        import re

        def _replace(m: re.Match) -> str:
            char = m.group(1)
            if char in ('"', '\\', '/', 'b', 'f', 'n', 'r', 't', 'u'):
                return m.group(0)  # 有效转义，保留
            return '\\\\' + char  # 无效转义，转义反斜杠本身

        # 匹配字符串内部的 \X 模式（不处理已经是 \\ 的情况）
        return re.sub(r'\\(.)', _replace, s)

    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        json_start = text.find('```json')
        if json_start >= 0:
            content_start = text.find('\n', json_start)
            if content_start < 0:
                content_start = json_start + 7
            last_close = text.rfind('```')
            if last_close > content_start:
                return text[content_start:last_close].strip()

        code_start = text.find('```')
        if code_start >= 0:
            content_start = text.find('\n', code_start)
            if content_start < 0:
                content_start = code_start + 3
            last_close = text.rfind('```')
            if last_close > content_start:
                candidate = text[content_start:last_close].strip()
                if candidate.startswith('{'):
                    return candidate

        start = text.find('{')
        if start >= 0:
            end = text.rfind('}')
            if end > start:
                return text[start:end+1].strip()

        return text.strip()

    async def _execute_action(self, action_type: ActionType, action_params: Dict[str, Any], tool_name: Optional[str] = None) -> str:
        exec_name = tool_name or action_type.value
        logger.info(f"Execute tool: {exec_name} (action: {action_type}), params: {action_params}")
        result = await self.tools.run(exec_name, action_params)
        logger.info(f"Tool result: {result}")
        return result

    def _get_final_result(self) -> str:
        return self.context_manager.get_final_answer()


class State(ABC):
    def __init__(self, state_machine: 'BaseStateMachine'):
        self.state_machine = state_machine
        self.state = None
        self.agent: Optional[BaseAgent] = None

    @abstractmethod
    def on_enter(self, data: Optional[StateData] = None):
        pass

    @abstractmethod
    def on_exit(self, data: Optional[StateData] = None):
        pass

    @abstractmethod
    async def execute(self, data: Optional[StateData] = None) -> StateTransition:
        pass

    def can_transition_to(self, new_state: AgentState) -> bool:
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
        pass

    def is_in_state(self, state_enum: AgentState) -> bool:
        return self._current_state_enum == state_enum

    def transition(self, new_state_enum: AgentState, data: Optional[StateData] = None) -> bool:
        if new_state_enum not in self._states:
            return False

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
