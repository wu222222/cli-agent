import asyncio
import json
import uuid
import logging
import os
import yaml
from typing import List, Dict, Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agent.types import AgentState, ThinkingToExecutingData

from .models import ChatRequest, ChatResponse, CuratorRequest, HealthResponse, PluginInfo, PluginActionResponse
from .streaming import create_queue, get_queue
from .services import (
    _get_or_init_components, _create_worker_agent, _create_curator_agent,
    _rebind_callbacks, run_agent_with_streaming, run_with_pending_check,
    get_pending_agent, set_pending_agent, history_store,
    get_plugin_manager, get_tool_registry,
    get_worker_tool_names, set_worker_tool_names,
)

logger = logging.getLogger("api")

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()


@router.get("/agent/chat/stream")
async def stream_events(request_id: str = Query(...)):
    queue = get_queue(request_id)
    if not queue:
        return StreamingResponse(
            iter([f'event: error\ndata: {json.dumps({"content": "无效的 request_id"})}\n\n']),
            media_type="text/event-stream"
        )

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=180)
                except asyncio.TimeoutError:
                    yield f"event: error\ndata: {json.dumps({'content': '连接超时'})}\n\n"
                    break

                event_type = event.get("event", "message")
                data = json.dumps(event.get("data", {}), ensure_ascii=False)
                yield f"event: {event_type}\ndata: {data}\n\n"

                if event_type in ("final", "error", "confirm"):
                    break
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/agent/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    logger.info(f"收到请求: message={request.message!r}, confirmed={request.confirmed}, pending={get_pending_agent() is not None}")

    _get_or_init_components()

    request_id = str(uuid.uuid4())[:8]
    create_queue(request_id)

    # --- 情况 A：确认 ---
    if request.confirmed and get_pending_agent() is not None:
        logger.info("处理确认请求")
        agent = get_pending_agent()
        set_pending_agent(None)

        waiting_state = agent.state_machine._states[AgentState.WAITING_CONFIRMATION]
        if isinstance(waiting_state.data, ThinkingToExecutingData):
            waiting_state.data.confirmed = True

        asyncio.create_task(run_agent_with_streaming(agent, request_id))
        return ChatResponse(request_id=request_id, type="text", agent=agent.name)

    # --- 情况 B：新消息 ---
    set_pending_agent(None)

    logger.info("创建新 Agent")
    agent = _create_worker_agent(request_id)
    agent._prepare_context(request.message)
    agent.state_machine.transition(AgentState.THINKING)

    asyncio.create_task(run_with_pending_check(agent, request_id))
    return ChatResponse(request_id=request_id, type="text", agent=agent.name)


@router.post("/agent/chat/confirm", response_model=ChatResponse)
async def confirm_command(request: ChatRequest):
    if not get_pending_agent():
        return ChatResponse(request_id="", content="没有待确认的命令", type="text")

    request_id = str(uuid.uuid4())[:8]
    create_queue(request_id)

    agent = get_pending_agent()
    set_pending_agent(None)

    waiting_state = agent.state_machine._states[AgentState.WAITING_CONFIRMATION]
    if isinstance(waiting_state.data, ThinkingToExecutingData):
        waiting_state.data.confirmed = True

    _rebind_callbacks(agent, request_id)

    asyncio.create_task(run_with_pending_check(agent, request_id))
    return ChatResponse(request_id=request_id, type="text", agent=agent.name)


@router.post("/agent/chat/reject", response_model=ChatResponse)
async def reject_command():
    """用户拒绝待确认的命令"""
    if not get_pending_agent():
        return ChatResponse(request_id="", content="没有待确认的命令", type="text")

    agent = get_pending_agent()
    set_pending_agent(None)

    # 设置 confirmed = False，让状态机走拒绝路径
    waiting_state = agent.state_machine._states[AgentState.WAITING_CONFIRMATION]
    if isinstance(waiting_state.data, ThinkingToExecutingData):
        waiting_state.data.confirmed = False

    # 运行一步让 Agent 完成拒绝流程（内部会转到 COMPLETED）
    try:
        await agent.step()
    except Exception:
        pass

    return ChatResponse(request_id="", content="命令已被拒绝", type="text")


@router.post("/agent/curator", response_model=ChatResponse)
async def run_curator(request: CuratorRequest):
    logger.info(f"收到 Curator 请求: task={request.task!r}")

    _get_or_init_components()

    request_id = str(uuid.uuid4())[:8]
    create_queue(request_id)

    agent = _create_curator_agent(request_id)
    agent._prepare_context(request.task)
    agent.state_machine.transition(AgentState.THINKING)

    asyncio.create_task(run_with_pending_check(agent, request_id))
    return ChatResponse(request_id=request_id, type="text", agent=agent.name)


@router.get("/agent/history")
async def get_history():
    return history_store


@router.delete("/agent/history")
async def clear_history():
    history_store.clear()
    return {"status": "success"}


@router.get("/plugins", response_model=List[PluginInfo])
async def list_plugins():
    _get_or_init_components()
    registry = get_tool_registry()
    manager = get_plugin_manager()
    if not registry:
        return []
    return _build_plugin_list(registry, manager)


def _build_plugin_list(registry, manager, include_call_judge: bool = False) -> List[PluginInfo]:
    """构建插件列表，支持复用"""
    from src.agent.tools import ExecContainerPlugin
    import yaml, os

    # 从 YAML 读取额外元数据（category, icon）
    yaml_meta: Dict[str, Dict] = {}
    plugins_yaml = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "plugins.yaml")
    if os.path.exists(plugins_yaml):
        with open(plugins_yaml, encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        for p in cfg.get('plugins', []):
            yaml_meta[p.get('name', '')] = p

    plugins: List[PluginInfo] = []

    for name in registry.list_tools():
        tool = registry.get_tool(name)
        if not tool:
            continue
        container_name = tool.container_name if isinstance(tool, ExecContainerPlugin) else ""
        status = "unknown"
        if manager and container_name:
            container = manager.get_container(container_name)
            status = "running" if container else "stopped"

        meta = yaml_meta.get(name, {})
        mount_dirs = getattr(tool, 'mount_dirs', []) if isinstance(tool, ExecContainerPlugin) else []

        plugins.append(PluginInfo(
            name=tool.name,
            description=tool.description,
            tool_type=tool.execution_mode,
            container_name=container_name,
            status=status,
            bound_action=tool.bound_action.value if tool.bound_action else None,
            requires_confirmation=tool.requires_confirmation,
            mount_dirs=mount_dirs,
            parameters=tool.parameters if tool.parameters else None,
            required_params=tool.required_params if tool.required_params else None,
            category=meta.get('category', 'other'),
            icon=meta.get('icon', 'default'),
        ))

    return plugins


@router.get("/presets", response_model=List[PluginInfo])
async def get_presets_endpoint():
    """获取所有可用插件预设（含 call_judge）"""
    _get_or_init_components()
    registry = get_tool_registry()
    manager = get_plugin_manager()
    if not registry:
        return []
    return _build_plugin_list(registry, manager, include_call_judge=True)


@router.post("/plugins/{name}/start", response_model=PluginActionResponse)
async def start_plugin(name: str):
    _get_or_init_components()
    registry = get_tool_registry()
    manager = get_plugin_manager()
    if not registry or not manager:
        return PluginActionResponse(success=False, message="系统未初始化")

    tool = registry.get_tool(name)
    if not tool:
        return PluginActionResponse(success=False, message=f"插件 '{name}' 不存在")

    from src.agent.tools import ExecContainerPlugin
    if not isinstance(tool, ExecContainerPlugin):
        return PluginActionResponse(success=False, message=f"'{name}' 不是容器插件")

    if not tool.container_name:
        return PluginActionResponse(success=False, message="未配置容器名")

    # 尝试从 YAML 获取 image
    import yaml, os
    plugins_yaml = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "plugins.yaml")
    image = ""
    if os.path.exists(plugins_yaml):
        with open(plugins_yaml, encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        for p in cfg.get('plugins', []):
            if p.get('name') == name:
                image = p.get('image', '')
                break

    success = manager.ensure_running(tool.container_name, image)
    if success:
        container = manager.get_container(tool.container_name)
        if container:
            tool.bind_container(container)
    return PluginActionResponse(
        success=success,
        message=f"插件 '{name}' 已启动" if success else f"插件 '{name}' 启动失败"
    )


@router.post("/plugins/{name}/stop", response_model=PluginActionResponse)
async def stop_plugin(name: str):
    _get_or_init_components()
    registry = get_tool_registry()
    manager = get_plugin_manager()
    if not registry or not manager:
        return PluginActionResponse(success=False, message="系统未初始化")

    tool = registry.get_tool(name)
    if not tool:
        return PluginActionResponse(success=False, message=f"插件 '{name}' 不存在")

    from src.agent.tools import ExecContainerPlugin
    if not isinstance(tool, ExecContainerPlugin):
        return PluginActionResponse(success=False, message=f"'{name}' 不是容器插件")

    if not tool.container_name:
        return PluginActionResponse(success=False, message="未配置容器名")

    container = manager.get_container(tool.container_name)
    if not container:
        return PluginActionResponse(success=True, message=f"插件 '{name}' 已停止")

    try:
        container.stop(timeout=5)
        manager._containers.pop(tool.container_name, None)
        tool.bind_container(None)
        return PluginActionResponse(success=True, message=f"插件 '{name}' 已停止")
    except Exception as e:
        return PluginActionResponse(success=False, message=f"停止失败: {e}")


# --- Agent 工具配置 API ---

class AgentToolConfig(BaseModel):
    tool_names: List[str]


@router.get("/agent/tools")
async def get_agent_tools():
    """获取 WorkerAgent 当前的工具配置"""
    _get_or_init_components()
    registry = get_tool_registry()
    manager = get_plugin_manager()
    return {
        "tool_names": get_worker_tool_names(),
        "available_tools": _build_plugin_list(registry, manager, include_call_judge=True) if registry else [],
    }


@router.post("/agent/tools")
async def set_agent_tools(config: AgentToolConfig):
    """设置 WorkerAgent 的工具配置"""
    set_worker_tool_names(config.tool_names)
    return {"success": True, "tool_names": config.tool_names}
