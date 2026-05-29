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

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()


@router.get("/setup/status")
async def setup_status():
    """检测是否已完成首次配置"""
    import shutil

    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    has_env = os.path.exists(env_path)

    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    base_url = os.getenv("DASHSCOPE_BASE_URL", "")
    model = os.getenv("LLM_MODEL", "")
    # 配置来源检测
    all_filled = bool(api_key and model and base_url)
    if all_filled and has_env:
        config_source = "env_file"
        configured = True
    elif all_filled and not has_env:
        config_source = "env"
        configured = True
    elif has_env and (api_key or model or base_url):
        config_source = "partial"
        configured = False
    elif not has_env and (api_key or model or base_url):
        config_source = "env"
        configured = False
    else:
        config_source = "none"
        configured = False

    # Docker 检测：区分未安装 / 已安装未运行 / 正常
    docker_status = "not_installed"
    docker_installed = shutil.which("docker") is not None
    if docker_installed:
        try:
            import subprocess
            subprocess.run(["docker", "info"], capture_output=True, timeout=5, check=True)
            docker_status = "running"
        except Exception:
            docker_status = "not_running"

    return {
        "configured": configured,
        "has_env": has_env,
        "docker_status": docker_status,
        "config_source": config_source,
        "api_key": api_key[:8] + "***" if api_key else "",
        "base_url": base_url,
        "model": model,
    }


@router.post("/setup/save")
async def setup_save(body: dict):
    """保存首次配置到 .env 文件"""
    api_key = body.get("api_key", "").strip()
    base_url = body.get("base_url", "").strip()
    model = body.get("model", "").strip()

    # API Key: 如果用户留空但系统环境变量有值，则保留环境变量
    if not api_key:
        api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        return {"success": False, "message": "API Key 不能为空（未检测到系统环境变量）"}
    if not model:
        return {"success": False, "message": "模型名称不能为空"}

    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")

    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    # 更新或追加配置
    def set_env(lines, key, value):
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                return lines
        lines.append(f"{key}={value}\n")
        return lines

    lines = set_env(lines, "DASHSCOPE_API_KEY", api_key)
    lines = set_env(lines, "DASHSCOPE_BASE_URL", base_url)
    lines = set_env(lines, "LLM_MODEL", model)

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # 更新当前进程的环境变量
    os.environ["DASHSCOPE_API_KEY"] = api_key
    os.environ["DASHSCOPE_BASE_URL"] = base_url
    os.environ["LLM_MODEL"] = model

    logger.info(f"配置已保存: model={model}, base_url={base_url}")
    return {"success": True, "message": "配置已保存，请重启应用使配置生效"}


@router.get("/plugins/config")
async def get_plugins_config():
    """读取 plugins.yaml 内容"""
    config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config")
    plugins_path = os.path.join(config_dir, "plugins.yaml")
    if not os.path.exists(plugins_path):
        return {"content": "", "exists": False}
    with open(plugins_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"content": content, "exists": True}


@router.post("/plugins/config")
async def save_plugins_config(body: dict):
    """保存 plugins.yaml 内容"""
    content = body.get("content", "")
    if not content.strip():
        return {"success": False, "message": "配置内容不能为空"}

    # YAML 语法验证
    try:
        import yaml
        parsed = yaml.safe_load(content)
        if not isinstance(parsed, dict) or "plugins" not in parsed:
            return {"success": False, "message": "YAML 格式错误：缺少 plugins 根键"}
    except yaml.YAMLError as e:
        return {"success": False, "message": f"YAML 语法错误: {e}"}

    config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config")
    os.makedirs(config_dir, exist_ok=True)
    plugins_path = os.path.join(config_dir, "plugins.yaml")

    with open(plugins_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"plugins.yaml 已保存 ({len(content)} bytes)")
    return {"success": True, "message": "插件配置已保存，重启应用后生效"}


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
    logger.info(f"收到请求: message={request.message!r}, confirmed={request.confirmed}, session_id={request.session_id}, pending={get_pending_agent() is not None}")

    _get_or_init_components()

    request_id = str(uuid.uuid4())[:8]
    create_queue(request_id)
    session_id = request.session_id

    # --- 情况 A：确认 ---
    if request.confirmed and get_pending_agent() is not None:
        logger.info("处理确认请求")
        agent = get_pending_agent()
        set_pending_agent(None)

        waiting_state = agent.state_machine._states[AgentState.WAITING_CONFIRMATION]
        if isinstance(waiting_state.data, ThinkingToExecutingData):
            waiting_state.data.confirmed = True

        asyncio.create_task(run_agent_with_streaming(agent, request_id, session_id))
        return ChatResponse(request_id=request_id, type="text", agent=agent.name)

    # --- 情况 B：新消息 ---
    set_pending_agent(None)

    logger.info("创建新 Agent")
    agent = _create_worker_agent(request_id)
    agent._prepare_context(request.message)
    agent.state_machine.transition(AgentState.THINKING)

    asyncio.create_task(run_with_pending_check(agent, request_id, session_id))
    return ChatResponse(request_id=request_id, type="text", agent=agent.name)


@router.post("/agent/chat/confirm", response_model=ChatResponse)
async def confirm_command(request: ChatRequest):
    if not get_pending_agent():
        return ChatResponse(request_id="", content="没有待确认的命令", type="text")

    request_id = str(uuid.uuid4())[:8]
    create_queue(request_id)
    session_id = request.session_id

    agent = get_pending_agent()
    set_pending_agent(None)

    waiting_state = agent.state_machine._states[AgentState.WAITING_CONFIRMATION]
    if isinstance(waiting_state.data, ThinkingToExecutingData):
        waiting_state.data.confirmed = True
        waiting_state.data.user_guidance = request.message or ""

    _rebind_callbacks(agent, request_id)

    asyncio.create_task(run_with_pending_check(agent, request_id, session_id))
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

            # type 字段优先（与顶层插件同构），role 兼容旧格式
            child_type = child_cfg.get('type', None)
            if child_type is None:
                child_type = child_cfg.get('role', 'exec')
            if child_type == 'aux':
                continue
            if child_type not in ('exec', 'command'):
                continue
            if child_type == 'exec' and not child_cfg.get('register', True):
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
    logger.info(f"[set_agent_tools] Received tool_names: {config.tool_names}")
    set_worker_tool_names(config.tool_names)
    logger.info(f"[set_agent_tools] Saved tool_names: {get_worker_tool_names()}")
    return {"success": True, "tool_names": config.tool_names}


# ============================================================
# Session API（对话历史持久化）
# ============================================================

from .services import get_session_manager


@router.get("/agent/sessions")
async def list_sessions():
    """列出所有会话"""
    sm = get_session_manager()
    if not sm:
        return []
    return sm.list_sessions()


@router.post("/agent/sessions")
async def create_session():
    """创建新会话"""
    sm = get_session_manager()
    if not sm:
        return {"error": "SessionManager 未初始化"}
    tool_names = get_worker_tool_names()
    session_id = sm.create_session(tool_names)
    logger.info(f"Created new session: {session_id} with tools: {tool_names}")
    return {"session_id": session_id, "tool_names": tool_names}


@router.get("/agent/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话详情"""
    sm = get_session_manager()
    if not sm:
        return {"error": "SessionManager 未初始化"}
    session = sm.load_session(session_id)
    if not session:
        return {"error": "会话不存在"}
    return session


@router.delete("/agent/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话（同时清理内存中的上下文）"""
    sm = get_session_manager()
    if not sm:
        return {"error": "SessionManager 未初始化"}
    # 清理内存中的上下文（如果当前上下文属于该会话）
    _get_or_init_components()
    cm = get_context_manager()
    if cm:
        cm.clear()
    success = sm.delete_session(session_id)
    return {"success": success}


@router.post("/agent/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    """恢复会话（session 工具配置 → 恢复到全局，加载消息 + 上下文）"""
    sm = get_session_manager()
    if not sm:
        logger.error("[resume_session] SessionManager is None!")
        return {"error": "SessionManager 未初始化"}
    session = sm.load_session(session_id)
    if not session:
        logger.error(f"[resume_session] Session not found: {session_id}")
        return {"error": "会话不存在"}

    session_tool_names = session.get("tool_names", [])

    logger.info(f"[resume_session] session_id={session_id}, session_tools={session_tool_names}, messages={len(session.get('messages', []))}")

    # session 的工具配置是 source of truth → 恢复到全局
    if session_tool_names:
        set_worker_tool_names(session_tool_names)

    # 自动启动相关容器
    _get_or_init_components()
    from .services import _auto_start_containers_for_tools
    _auto_start_containers_for_tools(session_tool_names)

    # 恢复上下文状态（先清空旧上下文，再加载新 session 的）
    from .services import get_context_manager
    cm = get_context_manager()
    if cm:
        cm.clear()
    context_data = sm.load_context(session_id)
    if context_data and cm:
        cm.from_dict(context_data)
        logger.info(f"[resume_session] 上下文已恢复: {len(cm.messages)} 条消息")
    else:
        logger.info(f"[resume_session] 无保存的上下文，已清空")

    return {
        "session_id": session_id,
        "tool_names": session_tool_names,
        "messages": session.get("messages", []),
    }


@router.post("/agent/sessions/{session_id}/title")
async def update_session_title(session_id: str, body: dict):
    """更新会话标题"""
    sm = get_session_manager()
    if not sm:
        return {"error": "SessionManager 未初始化"}
    title = body.get("title", "新对话")
    success = sm.update_title(session_id, title)
    return {"success": success}


@router.post("/agent/sessions/{session_id}/tools")
async def update_session_tools(session_id: str, body: dict):
    """更新会话的工具配置"""
    sm = get_session_manager()
    if not sm:
        logger.error("[update_session_tools] SessionManager is None!")
        return {"error": "SessionManager 未初始化"}
    tool_names = body.get("tool_names", [])
    logger.info(f"[update_session_tools] session_id={session_id}, tool_names={tool_names}")
    success = sm.update_tool_names(session_id, tool_names)
    logger.info(f"[update_session_tools] result: {success}")
    return {"success": success}


@router.post("/agent/sessions/{session_id}/message")
async def save_session_message(session_id: str, body: dict):
    """保存消息到会话"""
    sm = get_session_manager()
    if not sm:
        return {"error": "SessionManager 未初始化"}
    message = body.get("message", {})
    success = sm.save_message(session_id, message)
    return {"success": success}
