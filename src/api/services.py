import asyncio
import os
import logging
from typing import Optional, List

from src.agent import JudgeAgent, ContextManager, PromptManager, ToolRegistry
from src.agent.base import BaseAgent
from src.agent.types import AgentState, ThinkingToExecutingData
from src.agent.registry import get_agent_config
from src.executor import PluginContainerManager
from src.llm.client import LLMClient

from .streaming import (
    StreamingWorkerAgent, StreamingCuratorAgent,
    create_queue, get_queue, _make_emit_callbacks,
)

logger = logging.getLogger("api")

# --- 全局组件状态 ---
_llm_client: Optional[LLMClient] = None
_context_manager: Optional[ContextManager] = None
_prompt_manager: Optional[PromptManager] = None
_tool_registry: Optional[ToolRegistry] = None
_judge_agent: Optional[JudgeAgent] = None
_plugin_manager: Optional[PluginContainerManager] = None

_pending_agent: Optional[BaseAgent] = None

# Agent 工具配置（内存中，前端可配置）
_worker_tool_names: List[str] = ["call_judge"]

# 历史记录
history_store: list = []


def get_pending_agent() -> Optional[BaseAgent]:
    return _pending_agent


def set_pending_agent(agent: Optional[BaseAgent]):
    global _pending_agent
    _pending_agent = agent


def get_plugin_manager() -> Optional[PluginContainerManager]:
    return _plugin_manager


def get_tool_registry() -> Optional[ToolRegistry]:
    return _tool_registry


def get_context_manager() -> Optional[ContextManager]:
    return _context_manager


def get_worker_tool_names() -> List[str]:
    return list(_worker_tool_names)


def set_worker_tool_names(names: List[str]):
    global _worker_tool_names
    _worker_tool_names = list(names)
    logger.info(f"WorkerAgent 工具配置已更新: {names}")


def _get_or_init_components():
    global _llm_client, _context_manager, _prompt_manager, _tool_registry, _judge_agent, _plugin_manager

    if _llm_client is not None:
        return

    logger.info("首次请求，初始化全局组件...")
    _llm_client = LLMClient()
    _context_manager = ContextManager()
    _prompt_manager = PromptManager()
    _tool_registry = ToolRegistry()

    # 1. 插件管理器 + YAML 插件加载
    # 所有容器插件默认不自动启动，用户在工具设置页面手动启动
    _plugin_manager = PluginContainerManager()
    config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config")
    for yaml_name in ("plugins.yaml", "plugins_lab.yaml"):
        path = os.path.join(config_dir, yaml_name)
        if os.path.exists(path):
            _tool_registry.load_from_yaml(path, docker_client=_plugin_manager.client)
            logger.info(f"Loaded: {yaml_name}")
    logger.info(f"YAML 插件加载完成（容器默认不启动，请在工具设置页面启动）")

    # 2. 注册 CALL_JUDGE 的 handler（唯一保留的 LocalTool）
    _judge_agent = JudgeAgent(
        llm_client=_llm_client,
        context_manager=_context_manager,
        prompt_manager=_prompt_manager,
        tool_registry=_tool_registry,
    )

    async def judge_handler(final_answer: str, evidence_summary: str = "", **kwargs):
        logger.info("Judge 评审开始")
        history = _context_manager.get_recent_messages("WorkerAgent", include_system_prompt=False)
        content = f"'history': {history}\n'answer': {final_answer}\n'evidence': {evidence_summary}"
        payload = ContextManager.create_assistant_message(
            sender="WorkerAgent", content=content, receivers=[_judge_agent.name]
        )
        result = await _judge_agent.run(payload)
        judge_thought = _judge_agent.last_thought
        logger.info("Judge 评审完成")
        output = f"评审结果: {result}"
        if judge_thought:
            output = f"[JudgeAgent 思考] {judge_thought}\n\n{output}"
        return output

    # 为所有 agent_type="judge" 的 local 工具绑定 handler
    for tool_name in _tool_registry.list_tools():
        tool = _tool_registry.get_tool(tool_name)
        if tool and getattr(tool, 'agent_type', '') == 'judge' and getattr(tool, 'plugin_type', '') == 'local':
            tool.handler = judge_handler
            logger.info(f"Judge handler 已绑定到: {tool_name}")

    # 绑定 context_compress handler（LLM 摘要压缩）
    compress_tool = _tool_registry.get_tool("context_compress")
    if compress_tool:
        compress_tool.handler = _create_compress_handler(_llm_client, _context_manager)
        logger.info("ContextCompress handler 已绑定")

    logger.info(f"所有工具注册完成: {_tool_registry.list_tools()}")


def _create_compress_handler(llm_client, context_manager):
    """创建上下文压缩 handler"""
    async def compress_handler(messages_to_compress: str, **kwargs) -> str:
        prompt = f"""请将以下对话历史压缩为一段简洁的摘要，保留关键信息：

{messages_to_compress}

摘要格式要求：
1. 保留关键操作和发现（按时间顺序）
2. 保留具体的文件路径、IP 地址、URL、flag 值等硬数据
3. 保留遇到的错误及对应的解决方法
4. 用中文，控制在 300 字以内

直接输出摘要，不要加额外解释。"""
        try:
            response = await llm_client.achat([{"role": "user", "content": prompt}])
            summary = response.strip()
            if context_manager:
                context_manager.inject_summary(summary)
            return summary
        except Exception as e:
            logger.error(f"上下文压缩失败: {e}")
            return f"压缩失败: {e}"
    return compress_handler


# --- Agent 创建（基于 AgentRegistry，数据驱动） ---

def _resolve_tool_names(agent_type: str) -> List[str]:
    """根据 AgentConfig.tool_filter 解析工具名列表"""
    config = get_agent_config(agent_type)
    if not config:
        return []

    if config.tool_filter == "config":
        return list(_worker_tool_names)
    elif config.tool_filter == "all_matching":
        return [
            name for name in _tool_registry.list_tools()
            if getattr(_tool_registry.get_tool(name), 'agent_type', '') == agent_type
        ]
    elif config.tool_filter == "fixed":
        return list(config.fixed_tool_names or [])
    return []


def _auto_start_containers_for_tools(tool_names: List[str]):
    """为指定工具列表自动启动容器"""
    if not _plugin_manager:
        return
    from src.agent.tools import ExecContainerPlugin
    for name in tool_names:
        tool = _tool_registry.get_tool(name)
        if not isinstance(tool, ExecContainerPlugin):
            continue
        if not tool.container_name:
            continue
        if tool._container:
            continue
        image = "alpine:latest"  # 默认镜像，compose 子工具不需要
        volumes = {}
        for m in getattr(tool, 'mount_dirs', []):
            parts = m.split(':')
            if len(parts) >= 2:
                host_path = os.path.abspath(parts[0])
                container_path = parts[1]
                mode = parts[2] if len(parts) > 2 else 'rw'
                volumes[host_path] = {'bind': container_path, 'mode': mode}
        network = getattr(tool, 'network_mode', 'none')
        priv = getattr(tool, 'privileged', False)
        success = _plugin_manager.ensure_running(
            tool.container_name, image,
            volumes=volumes or None,
            network_mode=network,
            privileged=priv,
        )
        if success:
            container = _plugin_manager.get_container(tool.container_name)
            if container:
                tool.bind_container(container)
                logger.info(f"容器已自动启动: {tool.container_name} (工具: {name})")


def _create_agent_for_type(agent_type: str, request_id: str) -> BaseAgent:
    """根据 agent_type 动态创建 Agent — 完全数据驱动，无硬编码"""
    _get_or_init_components()
    config = get_agent_config(agent_type)
    if not config or not config.base_class:
        raise ValueError(f"未知的 agent_type: {agent_type}")

    tool_names = _resolve_tool_names(agent_type)

    # 自动启动容器
    if config.auto_start_containers:
        _auto_start_containers_for_tools(tool_names)

    # 确定使用哪个 streaming 包装类（StreamingXxxAgent 才有 SSE 回调能力）
    # 映射在 services.py 维护（避免 agent.py 循环导入）
    streaming_cls = STREAMING_WRAPPER_MAP.get(agent_type)
    # 获取对应的 ContextPolicy
    from src.agent.agent import AGENT_POLICIES
    policy = AGENT_POLICIES.get(agent_type)
    if streaming_cls:
        agent = streaming_cls(
            llm_client=_llm_client,
            context_manager=_context_manager,
            prompt_manager=_prompt_manager,
            tool_registry=_tool_registry,
            tool_names=tool_names,
            context_policy=policy,
        )
    else:
        # judge 等不需要 streaming 的 Agent
        agent = config.base_class(
            llm_client=_llm_client,
            context_manager=_context_manager,
            prompt_manager=_prompt_manager,
            tool_registry=_tool_registry,
            tool_names=tool_names,
        )

    # 绑定 SSE 回调
    emit_start, emit_result, emit_thought = _make_emit_callbacks(request_id, _tool_registry)
    agent.on_tool_start = emit_start
    agent.on_tool_result = emit_result
    agent.on_thought = emit_thought

    return agent


# agent_type → Streaming 包装类映射（在 services.py 维护，避免循环导入）
STREAMING_WRAPPER_MAP = {
    "worker": StreamingWorkerAgent,
    "curator": StreamingCuratorAgent,
    # "judge" 不在此处 — JudgeAgent 不需要 SSE 回调
}


def _create_worker_agent(request_id: str):
    """向后兼容别名"""
    return _create_agent_for_type("worker", request_id)


def _create_curator_agent(request_id: str):
    """向后兼容别名"""
    return _create_agent_for_type("curator", request_id)


def _rebind_callbacks(agent: BaseAgent, request_id: str):
    """为挂起后恢复的 Agent 重新绑定 SSE 回调"""
    emit_start, emit_result, emit_thought = _make_emit_callbacks(request_id, _tool_registry)
    agent.on_tool_start = emit_start
    agent.on_tool_result = emit_result
    agent.on_thought = emit_thought


async def run_agent_with_streaming(agent: BaseAgent, request_id: str):
    """驱动 Agent 执行，通过 SSE 队列实时推送工具结果"""
    queue = get_queue(request_id)
    MAX_STEPS = 50

    for step_num in range(MAX_STEPS):
        logger.info(f"[Step {step_num + 1}] 当前状态: {agent.state_machine._current_state_enum.value}")
        transition = await agent.step()
        logger.info(f"[Step {step_num + 1}] 转换到: {transition.state.value}")

        if agent.state_machine.is_in_state(AgentState.WAITING_CONFIRMATION):
            waiting_state = agent.state_machine._states[AgentState.WAITING_CONFIRMATION]
            data = waiting_state.data
            if isinstance(data, ThinkingToExecutingData):
                prompt = data.confirmation_prompt or "需要确认操作"
                thought = data.response.thought if data.response else ""
                command = data.response.action_params.get('command', '') if data.response else ""
                if queue:
                    await queue.put({"event": "confirm", "data": {
                        "content": prompt, "agent": agent.name,
                        "thought": thought, "command": command,
                        "tool_name": data.response.tool_name or "",
                    }})
                return
            if queue:
                await queue.put({"event": "confirm", "data": {"content": "需要确认操作", "agent": agent.name}})
            return

        if agent.state_machine.is_in_state(AgentState.COMPLETED):
            result = agent._get_final_result()
            logger.info(f"任务完成: {result[:100]}...")
            if queue:
                await queue.put({"event": "final", "data": {"content": result, "agent": agent.name}})
            return

        if agent.state_machine.is_in_state(AgentState.ERROR):
            err = transition.data.error_message if transition.data else "未知错误"
            logger.error(f"执行出错: {err}")
            if queue:
                await queue.put({"event": "final", "data": {"content": f"执行出错: {err}", "agent": agent.name}})
            return

    if queue:
        await queue.put({"event": "final", "data": {"content": "达到最大执行步数，任务中止", "agent": agent.name}})


async def run_with_pending_check(agent: BaseAgent, request_id: str):
    """运行 Agent 并在挂起时保存实例"""
    try:
        await asyncio.wait_for(run_agent_with_streaming(agent, request_id), timeout=120)
        if agent.state_machine.is_in_state(AgentState.WAITING_CONFIRMATION):
            set_pending_agent(agent)
            logger.info("Agent 挂起，等待用户确认")
    except asyncio.TimeoutError:
        queue = get_queue(request_id)
        if queue:
            await queue.put({"event": "final", "data": {"content": "请求处理超时", "agent": agent.name}})
    except Exception as e:
        logger.exception("Agent 运行异常")
        queue = get_queue(request_id)
        if queue:
            await queue.put({"event": "final", "data": {"content": f"系统错误: {str(e)}", "agent": agent.name}})
