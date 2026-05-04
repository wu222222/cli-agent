import asyncio
import json
import uuid
import logging

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from src.agent.types import AgentState, ThinkingToExecutingData

from .models import ChatRequest, ChatResponse, CuratorRequest, HealthResponse, DockerConfigRequest, DockerConfigResponse
from .streaming import create_queue, get_queue
from .services import (
    _get_or_init_components, _create_worker_agent, _create_curator_agent,
    _rebind_callbacks, run_agent_with_streaming, run_with_pending_check,
    get_pending_agent, set_pending_agent, history_store,
    get_docker_config, get_presets, update_docker_config,
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


@router.get("/config/docker", response_model=DockerConfigResponse)
async def get_docker_config_endpoint():
    return DockerConfigResponse(
        presets=get_presets(),
        current=get_docker_config(),
    )


@router.post("/config/docker", response_model=DockerConfigRequest)
async def update_docker_config_endpoint(request: DockerConfigRequest):
    return update_docker_config(request)
