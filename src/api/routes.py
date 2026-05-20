import asyncio
import json
import uuid
import logging
import os
import shlex
import yaml
from typing import List, Dict, Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agent.types import AgentState, ThinkingToExecutingData

from .models import ChatRequest, ChatResponse, CuratorRequest, HealthResponse, PluginInfo, PluginActionResponse, ComposePluginInfo
from .streaming import create_queue, get_queue
from .services import (
    _get_or_init_components, _create_worker_agent, _create_curator_agent,
    _rebind_callbacks, run_agent_with_streaming, run_with_pending_check,
    get_pending_agent, set_pending_agent, history_store,
    get_plugin_manager, get_tool_registry, get_context_manager,
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
        waiting_state.data.user_guidance = request.message or ""

    _rebind_callbacks(agent, request_id)

    asyncio.create_task(run_with_pending_check(agent, request_id))
    return ChatResponse(request_id=request_id, type="text", agent=agent.name)


@router.post("/agent/chat/reject", response_model=ChatResponse)
async def reject_command(request: ChatRequest):
    """用户拒绝待确认的命令。message 有内容时作为引导重新思考，无内容时终止。"""
    if not get_pending_agent():
        return ChatResponse(request_id="", content="没有待确认的命令", type="text")

    agent = get_pending_agent()
    guidance = request.message or ""

    if guidance:
        # 有引导 → 不清除 pending，带引导重新思考
        request_id = str(uuid.uuid4())[:8]
        create_queue(request_id)

        waiting_state = agent.state_machine._states[AgentState.WAITING_CONFIRMATION]
        if isinstance(waiting_state.data, ThinkingToExecutingData):
            waiting_state.data.confirmed = False
            waiting_state.data.user_guidance = guidance

        _rebind_callbacks(agent, request_id)
        asyncio.create_task(run_with_pending_check(agent, request_id))
        return ChatResponse(request_id=request_id, type="text", agent=agent.name)
    else:
        # 无引导 → 终止
        set_pending_agent(None)
        waiting_state = agent.state_machine._states[AgentState.WAITING_CONFIRMATION]
        if isinstance(waiting_state.data, ThinkingToExecutingData):
            waiting_state.data.confirmed = False
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


@router.get("/agent/context")
async def get_context_status():
    """获取上下文状态（用于前端可视化面板）"""
    _get_or_init_components()
    cm = get_context_manager()
    if not cm:
        return {"step": 0, "policy": None, "messages": [], "summary_count": 0}

    policy = cm.policy
    messages = []
    for msg in cm.messages:
        age = cm.current_step - msg.step_index

        # 判断衰减阶段
        if msg.importance == "critical" or msg.role == "user":
            stage = "locked"
        elif msg.role == "summary":
            stage = "summary"
        elif msg.role == "tool":
            if age <= policy.tool_full_turns:
                stage = "full"
            elif age <= policy.tool_truncate_turns:
                stage = "truncated"
            elif age <= policy.tool_max_turns:
                stage = "oneline"
            else:
                stage = "forgotten"
        else:
            stage = "full"

        messages.append({
            "role": msg.role,
            "sender": msg.sender,
            "tool_name": msg.tool_name,
            "step_index": msg.step_index,
            "age": age,
            "stage": stage,
            "preview": msg.content[:80].replace('\n', ' '),
            "content_len": len(msg.content),
        })

    return {
        "step": cm.current_step,
        "policy": policy.model_dump(),
        "messages": messages,
        "summary_count": len(cm.context_summaries),
        "total_count": len(cm.messages),
    }


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
    """构建插件列表 — 所有数据直接从 Tool 对象读取，不再重读 YAML"""
    from src.agent.tools import ExecContainerPlugin

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

        mount_dirs = getattr(tool, 'mount_dirs', []) if isinstance(tool, ExecContainerPlugin) else []

        plugins.append(PluginInfo(
            name=tool.name,
            description=tool.description,
            plugin_type=getattr(tool, 'plugin_type', 'exec'),
            agent_type=getattr(tool, 'agent_type', 'worker'),
            container_name=container_name,
            status=status,
            bound_action=tool.bound_action.value if tool.bound_action else None,
            requires_confirmation=tool.requires_confirmation,
            mount_dirs=mount_dirs,
            parameters=tool.parameters if tool.parameters else None,
            required_params=tool.required_params if tool.required_params else None,
            category=getattr(tool, 'category', 'other'),
            icon=getattr(tool, 'icon', 'default'),
            command_trigger=getattr(tool, 'command_trigger', ''),
            display_name=getattr(tool, 'display_name', ''),
            parent_compose=getattr(tool, '_parent_compose', None),
        ))

    return plugins


@router.post("/plugins/{name}/start", response_model=PluginActionResponse)
async def start_plugin(name: str):
    _get_or_init_components()
    registry = get_tool_registry()
    manager = get_plugin_manager()
    if not registry:
        return PluginActionResponse(success=False, message="系统未初始化")

    # 检查是否为 compose 插件
    compose = registry.get_compose(name)
    if compose:
        return await _start_compose(compose, registry, manager)

    # 普通 exec/command 插件
    tool = registry.get_tool(name)
    if not tool:
        return PluginActionResponse(success=False, message=f"插件 '{name}' 不存在")

    from src.agent.tools import ExecContainerPlugin
    if not isinstance(tool, ExecContainerPlugin):
        return PluginActionResponse(success=False, message=f"'{name}' 不是容器插件")

    if not tool.container_name:
        return PluginActionResponse(success=False, message="未配置容器名")

    # 从 YAML 获取 image 和 mount_dirs
    import yaml, os
    plugins_yaml = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "plugins.yaml")
    image = ""
    mount_dirs = []
    if os.path.exists(plugins_yaml):
        with open(plugins_yaml, encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        for p in cfg.get('plugins', []):
            if p.get('name') == name:
                image = p.get('image', '')
                mount_dirs = p.get('mount_dirs', [])
                break

    # 转换 mount_dirs 为 Docker volumes 格式
    volumes = {}
    for m in mount_dirs:
        parts = m.split(':')
        if len(parts) >= 2:
            host_path = os.path.abspath(parts[0])
            container_path = parts[1]
            mode = parts[2] if len(parts) > 2 else 'rw'
            volumes[host_path] = {'bind': container_path, 'mode': mode}

    network_mode = getattr(tool, 'network_mode', 'none')
    privileged = getattr(tool, 'privileged', False)
    success = manager.ensure_running(tool.container_name, image, volumes=volumes or None, network_mode=network_mode, privileged=privileged)
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
    if not registry:
        return PluginActionResponse(success=False, message="系统未初始化")

    # 检查是否为 compose 插件
    compose = registry.get_compose(name)
    if compose:
        return await _stop_compose(compose, registry)

    # 普通 exec/command 插件
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
        container.remove(force=True)
        manager._containers.pop(tool.container_name, None)
        tool.bind_container(None)
        return PluginActionResponse(success=True, message=f"插件 '{name}' 已停止并删除")
    except Exception as e:
        return PluginActionResponse(success=False, message=f"停止失败: {e}")


@router.post("/command/{name}")
async def execute_command_plugin(name: str, body: dict = None):
    """直接执行 command 类型插件（不经过 Agent）"""
    _get_or_init_components()
    registry = get_tool_registry()
    if not registry:
        return {"success": False, "message": "系统未初始化"}

    tool = registry.get_tool(name)
    if not tool:
        return {"success": False, "message": f"插件 '{name}' 不存在"}

    from src.agent.tools import ExecContainerPlugin
    if not isinstance(tool, ExecContainerPlugin) or getattr(tool, 'plugin_type', '') != 'command':
        return {"success": False, "message": f"'{name}' 不是命令插件"}

    if not tool._container:
        return {"success": False, "message": f"插件 '{name}' 容器未启动，请先启动所属 Compose"}

    # 使用用户传入的命令，或默认命令
    command = (body or {}).get('command', '') or tool.default_command
    if not command:
        return {"success": False, "message": f"插件 '{name}' 未配置默认命令，请传入 command 参数"}

    try:
        exit_code, output = tool._container.exec_run(
            ["sh", "-c", f"{tool.entrypoint_cmd} {shlex.quote(command)}"],
            detach=False, stdout=True, stderr=True,
        )
        stdout = output.decode('utf-8', errors='replace') if output else ""
        return {
            "success": exit_code == 0,
            "output": stdout.strip(),
            "exit_code": exit_code,
        }
    except Exception as e:
        return {"success": False, "message": f"执行异常: {e}"}


@router.post("/plugins/{name}/reset", response_model=PluginActionResponse)
async def reset_plugin(name: str):
    """重置 compose 插件（down -v + up）"""
    _get_or_init_components()
    registry = get_tool_registry()
    manager = get_plugin_manager()
    if not registry or not manager:
        return PluginActionResponse(success=False, message="系统未初始化")

    compose = registry.get_compose(name)
    if not compose:
        return PluginActionResponse(success=False, message=f"'{name}' 不是 compose 插件")

    # 先注销子工具
    compose.unbind_children(registry)
    # 重置
    ok, msg = await compose.reset()
    if ok:
        registered = compose.bind_children(manager.client, registry)
        return PluginActionResponse(
            success=True,
            message=f"Compose '{name}' 已重置，注册工具: {', '.join(registered)}"
        )
    return PluginActionResponse(success=False, message=f"重置失败: {msg}")


@router.post("/composes/{name}/regenerate")
async def regenerate_compose(name: str):
    """重新生成 compose 项目的 flag 并重启（仅限有 generate 脚本的项目）"""
    _get_or_init_components()
    registry = get_tool_registry()
    if not registry:
        return {"success": False, "message": "系统未初始化"}

    compose = registry.get_compose(name)
    if not compose:
        return {"success": False, "message": f"Compose '{name}' 不存在"}

    lab_dir = os.path.dirname(os.path.abspath(compose.compose_file)).replace("\\", "/")
    if not lab_dir.endswith("/"):
        lab_dir += "/"
    gen_script = lab_dir + "generate_lab.sh"

    if not os.path.exists(gen_script):
        return {"success": False, "message": f"'{name}' 没有 generate_lab.sh 脚本"}

    try:
        # 1. 停止并删除旧容器
        if compose.running:
            compose.unbind_children(registry)
            await compose.down(volumes=True)

        # 2. 生成新 flag（纯 Python，避免 bash 路径兼容性问题）
        import secrets
        shared_dir = os.path.join(lab_dir, "shared")
        os.makedirs(shared_dir, exist_ok=True)

        flag1 = f"FLAG{{{secrets.token_hex(16)}}}"
        flag2 = f"FLAG{{{secrets.token_hex(12)}}}"
        flag3 = f"FLAG{{{secrets.token_hex(8)}}}"

        env_path = os.path.join(lab_dir, ".env")
        with open(env_path, "w") as f:
            f.write(f"FLAG1={flag1}\nFLAG2={flag2}\nFLAG3={flag3}\n")

        flags_path = os.path.join(shared_dir, "flags.txt")
        with open(flags_path, "w") as f:
            f.write(f"{flag1}\n{flag2}\n{flag3}\n")

        gen_output = f"Flag 1: {flag1}\nFlag 2: {flag2}\nFlag 3: {flag3}"

        # 3. 重新启动
        ok, msg = await compose.up()
        if ok:
            manager = get_plugin_manager()
            if manager:
                compose.bind_children(manager.client, registry)
            return {"success": True, "message": f"Flag 已重新生成并重启\n{gen_output}"}
        return {"success": False, "message": f"重启失败: {msg}"}

    except Exception as e:
        return {"success": False, "message": f"异常: {e}"}


@router.get("/composes", response_model=List[ComposePluginInfo])
async def list_composes():
    """获取所有 compose 插件"""
    _get_or_init_components()
    registry = get_tool_registry()
    manager = get_plugin_manager()
    if not registry:
        return []

    result = []
    for cname in registry.list_compose():
        compose = registry.get_compose(cname)
        if not compose:
            continue
        children = []
        for child_cfg in compose.children_config:
            role = child_cfg.get('role', None)
            child_type = child_cfg.get('type', 'exec')  # 兼容旧字段

            # 新版 role 字段: exec / command / aux
            if role is not None:
                if role == 'aux':
                    continue  # 辅助容器不注册
                child_type = role
            else:
                # 旧版兼容: type + register 字段
                if child_type == 'exec' and not child_cfg.get('register', True):
                    continue
                if child_type not in ('exec', 'command'):
                    continue

            child_name = child_cfg.get('name', '')
            service_name = child_cfg.get('service_name', '')
            # 检查子工具是否已注册
            child_tool = registry.get_tool(child_name)
            status = "registered" if child_tool else "pending"
            children.append(PluginInfo(
                name=child_name,
                description=child_cfg.get('description', ''),
                plugin_type=child_type,
                agent_type=child_cfg.get('agent_type', 'none' if child_type == 'command' else 'worker'),
                container_name=f"{cname}-{service_name}-1",
                status=status,
                bound_action=child_cfg.get('bound_action', 'execute_command'),
                requires_confirmation=child_cfg.get('requires_confirmation', False),
                parameters=child_cfg.get('parameters'),
                required_params=child_cfg.get('required_params'),
                category=child_cfg.get('category', 'other'),
                icon=child_cfg.get('icon', 'default'),
                command_trigger=child_cfg.get('command_trigger', ''),
                parent_compose=cname,
            ))
        lab_dir = os.path.dirname(os.path.abspath(compose.compose_file))
        gen_script = os.path.join(lab_dir, "generate_lab.sh")
        has_regenerate = os.path.exists(gen_script)

        result.append(ComposePluginInfo(
            name=compose.name,
            description=compose.description,
            compose_file=compose.compose_file,
            running=compose.running,
            category=compose.category,
            icon=compose.icon,
            children=children,
            has_regenerate=has_regenerate,
        ))
    return result


async def _start_compose(compose, registry, manager):
    """启动 compose 插件"""
    ok, msg = await compose.up()
    if not ok:
        return PluginActionResponse(success=False, message=f"Compose 启动失败: {msg}")

    registered = compose.bind_children(manager.client, registry)
    return PluginActionResponse(
        success=True,
        message=f"Compose '{compose.name}' 已启动，注册工具: {', '.join(registered)}"
    )


async def _stop_compose(compose, registry):
    """停止 compose 插件"""
    compose.unbind_children(registry)
    ok, msg = await compose.down()
    if ok:
        return PluginActionResponse(success=True, message=f"Compose '{compose.name}' 已停止")
    return PluginActionResponse(success=False, message=f"停止失败: {msg}")


# --- Agent 工具配置 API ---

class AgentToolConfig(BaseModel):
    tool_names: List[str]


@router.get("/agent/tools")
async def get_agent_tools():
    """获取 WorkerAgent 当前的工具配置（不含 command 类型插件）"""
    _get_or_init_components()
    registry = get_tool_registry()
    manager = get_plugin_manager()
    if not registry:
        return {"tool_names": [], "available_tools": []}
    all_tools = _build_plugin_list(registry, manager, include_call_judge=True)
    # command 类型插件不是 WorkerAgent 工具，不显示在工具配置列表中
    worker_tools = [t for t in all_tools if t.plugin_type != "command"]
    return {
        "tool_names": get_worker_tool_names(),
        "available_tools": worker_tools,
    }


@router.post("/agent/tools")
async def set_agent_tools(config: AgentToolConfig):
    """设置 WorkerAgent 的工具配置"""
    set_worker_tool_names(config.tool_names)
    return {"success": True, "tool_names": config.tool_names}
