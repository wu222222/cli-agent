import asyncio
from typing import Optional, Dict, Any, Callable, Awaitable

from src.agent import WorkerAgent, CuratorAgent
from src.agent.types import ActionType


# SSE 事件队列: request_id -> asyncio.Queue
_sse_queues: Dict[str, asyncio.Queue] = {}


def create_queue(request_id: str) -> asyncio.Queue:
    queue = asyncio.Queue()
    _sse_queues[request_id] = queue
    return queue


def get_queue(request_id: str) -> Optional[asyncio.Queue]:
    return _sse_queues.get(request_id)


def remove_queue(request_id: str):
    _sse_queues.pop(request_id, None)


def _make_emit_callbacks(request_id: str, tool_registry=None):
    """创建 SSE 事件发射回调函数，使用工具自描述格式化"""

    # 缓存每次工具调用的参数，供 tool_result 事件附带
    _last_params: Dict[str, Any] = {}

    def _get_tool(tool_name: str):
        if tool_registry:
            return tool_registry.get_tool(tool_name)
        return None

    def _extract_command(tool_name: str, params: Dict[str, Any]) -> str:
        """提取工具调用的关键参数用于展示"""
        if not params:
            return ""
        # exec 工具：显示 command
        if "command" in params:
            return params["command"]
        # 其他工具：显示所有参数的简要形式
        parts = []
        for k, v in params.items():
            val = str(v)
            if len(val) > 80:
                val = val[:77] + "..."
            parts.append(f"{k}: {val}")
        return ", ".join(parts)

    async def emit_tool_start(agent_name: str, tool_name: str, params: Dict[str, Any]):
        nonlocal _last_params
        _last_params = dict(params)
        queue = get_queue(request_id)
        if not queue:
            return
        tool = _get_tool(tool_name)
        if tool:
            description = tool.format_start(params)
            tool_type = tool.execution_mode
        else:
            description = f"正在执行: {tool_name}"
            tool_type = "local"
        await queue.put({
            "event": "tool_start",
            "data": {"agent": agent_name, "tool": tool_name, "tool_type": tool_type, "content": description}
        })

    async def emit_tool_result(agent_name: str, tool_name: str, result: str):
        queue = get_queue(request_id)
        if not queue:
            return
        tool = _get_tool(tool_name)
        if tool:
            formatted = tool.format_result(result)
            tool_type = tool.execution_mode
        else:
            formatted = result
            tool_type = "local"
        if formatted:
            command = _extract_command(tool_name, _last_params)
            await queue.put({
                "event": "tool_result",
                "data": {
                    "agent": agent_name, "tool": tool_name,
                    "tool_type": tool_type, "content": formatted,
                    "command": command,
                }
            })

    async def emit_thought(agent_name: str, thought: str):
        queue = get_queue(request_id)
        if queue and thought:
            await queue.put({
                "event": "thought",
                "data": {"agent": agent_name, "content": thought}
            })

    return emit_tool_start, emit_tool_result, emit_thought


class StreamingWorkerAgent(WorkerAgent):
    """支持实时回调工具执行结果的 WorkerAgent"""
    on_tool_start: Optional[Callable] = None
    on_tool_result: Optional[Callable] = None
    on_thought: Optional[Callable] = None

    async def _execute_action(self, action_type: ActionType, action_params: Dict[str, Any], tool_name: str = None) -> str:
        exec_name = tool_name or action_type.value
        # call_judge 工具的执行结果显示为 JudgeAgent
        agent_name = "JudgeAgent" if exec_name == "call_judge" else self.name

        # 发送当前 agent 的 thought（如果有）
        if self.on_thought and self.last_thought:
            await self.on_thought(self.name, self.last_thought)
            self.last_thought = ""

        if self.on_tool_start:
            await self.on_tool_start(agent_name, exec_name, action_params)

        result = await self.tools.run(exec_name, action_params)

        if self.on_tool_result:
            await self.on_tool_result(agent_name, exec_name, result)

        return result


class StreamingCuratorAgent(CuratorAgent):
    """支持实时回调工具执行结果的 CuratorAgent"""
    on_tool_start: Optional[Callable] = None
    on_tool_result: Optional[Callable] = None
    on_thought: Optional[Callable] = None

    async def _execute_action(self, action_type: ActionType, action_params: Dict[str, Any], tool_name: str = None) -> str:
        exec_name = tool_name or action_type.value

        # 发送 thought
        if self.on_thought and self.last_thought:
            await self.on_thought(self.name, self.last_thought)
            self.last_thought = ""

        if self.on_tool_start:
            await self.on_tool_start(self.name, exec_name, action_params)

        result = await self.tools.run(exec_name, action_params)

        if self.on_tool_result:
            await self.on_tool_result(self.name, exec_name, result)

        return result
