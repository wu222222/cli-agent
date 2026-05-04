import asyncio
import re
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


def _format_action_start(action_type: ActionType, action_params: Dict[str, Any]) -> str:
    """格式化动作开始时的描述"""
    if action_type == ActionType.EXECUTE_COMMAND:
        cmd = action_params.get('command', '')
        return f"正在执行命令: {cmd}"
    elif action_type == ActionType.CALL_JUDGE:
        answer = action_params.get('final_answer', '')
        evidence = action_params.get('evidence_summary', '')
        lines = ["正在调用 JudgeAgent 进行评审..."]
        if answer:
            lines.append(f"待评审答案: {answer}")
        if evidence:
            lines.append(f"证据摘要: {evidence}")
        return "\n".join(lines)
    elif action_type == ActionType.QUERY_KNOWLEDGE:
        query = action_params.get('query', '')
        return f"正在查询知识库: {query}" if query else "正在查询知识库..."
    else:
        return f"正在执行: {action_type.value}"


def _format_tool_result(tool_name: str, raw_content: str) -> str:
    """格式化工具执行结果"""
    if tool_name == "execute_command":
        lines = []
        in_stdout = False
        for line in raw_content.split("\n"):
            if line.startswith("EXIT_CODE:"):
                lines.append(line)
                in_stdout = False
            elif line.startswith("STDOUT:"):
                lines.append("输出:")
                stdout = line[len("STDOUT:"):].strip()
                if stdout:
                    lines.append(stdout)
                in_stdout = True
            elif line.startswith("STDERR:"):
                stderr = line[len("STDERR:"):].strip()
                if stderr:
                    lines.append(f"错误: {stderr}")
                in_stdout = False
            elif in_stdout:
                lines.append(line)
        return "\n".join(lines) if lines else raw_content
    elif tool_name == "call_judge":
        obs_match = re.search(r"observation='(.*?)'", raw_content)
        action_match = re.search(r"action_type='(.*?)'", raw_content)
        if obs_match:
            obs = obs_match.group(1)
            action = action_match.group(1) if action_match else ""
            return f"评审意见: {obs}" + (f"\n处理方式: {action}" if action else "")
        return raw_content
    return raw_content


def _make_emit_callbacks(request_id: str):
    """创建 SSE 事件发射回调函数"""

    async def emit_tool_start(agent_name: str, tool_name: str, description: str):
        queue = get_queue(request_id)
        if queue:
            await queue.put({
                "event": "tool_start",
                "data": {"agent": agent_name, "tool": tool_name, "content": description}
            })

    async def emit_tool_result(agent_name: str, tool_name: str, result: str):
        queue = get_queue(request_id)
        if queue:
            formatted = _format_tool_result(tool_name, result)
            if formatted:
                await queue.put({
                    "event": "tool_result",
                    "data": {"agent": agent_name, "tool": tool_name, "content": formatted}
                })

    return emit_tool_start, emit_tool_result


class StreamingWorkerAgent(WorkerAgent):
    """支持实时回调工具执行结果的 WorkerAgent"""
    on_tool_start: Optional[Callable[[str, str, str], Awaitable[None]]] = None
    on_tool_result: Optional[Callable[[str, str, str], Awaitable[None]]] = None

    async def _execute_action(self, action_type: ActionType, action_params: Dict[str, Any]) -> str:
        agent_name = "JudgeAgent" if action_type == ActionType.CALL_JUDGE else self.name
        if self.on_tool_start:
            await self.on_tool_start(agent_name, action_type.value, _format_action_start(action_type, action_params))
        result = await super()._execute_action(action_type, action_params)
        if self.on_tool_result:
            await self.on_tool_result(agent_name, action_type.value, result)
        return result


class StreamingCuratorAgent(CuratorAgent):
    """支持实时回调工具执行结果的 CuratorAgent"""
    on_tool_start: Optional[Callable[[str, str, str], Awaitable[None]]] = None
    on_tool_result: Optional[Callable[[str, str, str], Awaitable[None]]] = None

    async def _execute_action(self, action_type: ActionType, action_params: Dict[str, Any]) -> str:
        if self.on_tool_start:
            await self.on_tool_start(self.name, action_type.value, _format_action_start(action_type, action_params))
        result = await super()._execute_action(action_type, action_params)
        if self.on_tool_result:
            await self.on_tool_result(self.name, action_type.value, result)
        return result
