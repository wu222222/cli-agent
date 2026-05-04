import asyncio
import logging
from typing import Optional, List

from src.agent import JudgeAgent, ContextManager, PromptManager, ToolRegistry, TaskPolicy
from src.agent.base import BaseAgent
from src.agent.types import AgentState, ThinkingToExecutingData
from src.executor import DockerExecutor, DockerConfig
from src.llm.client import LLMClient

from .streaming import (
    StreamingWorkerAgent, StreamingCuratorAgent,
    create_queue, get_queue, _make_emit_callbacks,
)
from .models import DockerPreset, DockerConfigRequest

logger = logging.getLogger("api")

# --- 预定义 Docker 镜像 ---
DOCKER_PRESETS: List[DockerPreset] = [
    DockerPreset(name="Alpine Linux", image="alpine:latest", description="轻量级 Linux 发行版，适合基础命令操作"),
    DockerPreset(name="Ubuntu", image="ubuntu:latest", description="主流 Linux 发行版，软件生态丰富"),
    DockerPreset(name="Debian", image="debian:latest", description="稳定可靠的 Linux 发行版"),
    DockerPreset(name="MyLab", image="my_lab_image:latest", description="flag靶场"),
]

# --- 当前 Docker 配置 ---
_docker_config: DockerConfigRequest = DockerConfigRequest(
    image="alpine:latest",
    container_name="cli_agent_sandbox",
    network="none",
    memory_limit="512m",
    timeout=30,
    use_host_workspace=False,
    use_knowledge_base=True,
    kb_mode="ro",
)

# --- 全局组件状态 ---
_llm_client: Optional[LLMClient] = None
_context_manager: Optional[ContextManager] = None
_prompt_manager: Optional[PromptManager] = None
_tool_registry: Optional[ToolRegistry] = None
_executor: Optional[DockerExecutor] = None
_judge_agent: Optional[JudgeAgent] = None

_pending_agent: Optional[BaseAgent] = None

# 历史记录
history_store: list = []


def get_pending_agent() -> Optional[BaseAgent]:
    return _pending_agent


def set_pending_agent(agent: Optional[BaseAgent]):
    global _pending_agent
    _pending_agent = agent


def get_docker_config() -> DockerConfigRequest:
    return _docker_config


def get_presets() -> List[DockerPreset]:
    return DOCKER_PRESETS


def update_docker_config(config: DockerConfigRequest) -> DockerConfigRequest:
    """更新 Docker 配置并重置组件（下次请求时重新初始化）"""
    global _docker_config, _llm_client, _executor
    _docker_config = config
    # 重置 executor 使其在下次请求时用新配置重新创建
    _executor = None
    _llm_client = None
    logger.info(f"Docker 配置已更新: image={config.image}, container={config.container_name}")
    return _docker_config


def _get_or_init_components():
    global _llm_client, _context_manager, _prompt_manager, _tool_registry, _executor, _judge_agent

    if _llm_client is not None:
        return

    logger.info("首次请求，初始化全局组件...")
    policy = TaskPolicy(allow_kb_search=False, allow_curation=True, read_only_kb=True)
    _llm_client = LLMClient()
    _context_manager = ContextManager()
    _prompt_manager = PromptManager(kb_search=policy.allow_kb_search)
    _tool_registry = ToolRegistry(kb_search=policy.allow_kb_search)

    docker_cfg = DockerConfig(
        image=_docker_config.image,
        container_name=_docker_config.container_name,
        use_host_workspace=_docker_config.use_host_workspace,
        use_knowledge_base=_docker_config.use_knowledge_base,
        kb_mode=_docker_config.kb_mode,
        network=_docker_config.network,
        memory_limit=_docker_config.memory_limit,
        timeout=_docker_config.timeout,
    )
    _executor = DockerExecutor(docker_cfg)
    logger.info(f"Docker 可用: {_executor.is_available()}, image: {_docker_config.image}")

    _judge_agent = JudgeAgent(
        llm_client=_llm_client,
        context_manager=_context_manager,
        prompt_manager=_prompt_manager,
        tool_registry=_tool_registry,
    )

    async def exec_handler(command: str):
        if not _executor.is_available():
            return "错误: Docker 未启动，无法执行命令。请先启动 Docker Desktop。"
        logger.info(f"Docker 执行命令: {command}")
        stdout, stderr, exit_code = _executor.execute_command(command)
        logger.info(f"命令完成, exit_code={exit_code}")
        return f"EXIT_CODE: {exit_code}\nSTDOUT: {stdout}\nSTDERR: {stderr}"

    _tool_registry.get_tool("execute_command").handler = exec_handler

    async def judge_handler(final_answer: str, evidence_summary: str = ""):
        logger.info("Judge 评审开始")
        history = _context_manager.get_recent_messages("WorkerAgent", include_system_prompt=False)
        content = f"'history': {history}\n'answer': {final_answer}\n'evidence': {evidence_summary}"
        payload = ContextManager.create_assistant_message(
            sender="WorkerAgent", content=content, receivers=[_judge_agent.name]
        )
        result = await _judge_agent.run(payload)
        logger.info("Judge 评审完成")
        return f"评审结果: {result}"

    _tool_registry.get_tool("call_judge").handler = judge_handler


def _create_worker_agent(request_id: str) -> StreamingWorkerAgent:
    _get_or_init_components()
    agent = StreamingWorkerAgent(
        llm_client=_llm_client,
        context_manager=_context_manager,
        prompt_manager=_prompt_manager,
        tool_registry=_tool_registry,
    )
    emit_start, emit_result = _make_emit_callbacks(request_id)
    agent.on_tool_start = emit_start
    agent.on_tool_result = emit_result
    return agent


def _create_curator_agent(request_id: str) -> StreamingCuratorAgent:
    _get_or_init_components()
    agent = StreamingCuratorAgent(
        llm_client=_llm_client,
        context_manager=_context_manager,
        prompt_manager=_prompt_manager,
        tool_registry=_tool_registry,
    )
    emit_start, emit_result = _make_emit_callbacks(request_id)
    agent.on_tool_start = emit_start
    agent.on_tool_result = emit_result
    return agent


def _rebind_callbacks(agent: BaseAgent, request_id: str):
    """为挂起后恢复的 Agent 重新绑定 SSE 回调"""
    emit_start, emit_result = _make_emit_callbacks(request_id)
    agent.on_tool_start = emit_start
    agent.on_tool_result = emit_result


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
                if queue:
                    await queue.put({"event": "confirm", "data": {"content": prompt, "agent": agent.name}})
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
