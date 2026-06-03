import asyncio
import logging
import os
import sys

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Windows: PEP 540 UTF-8 模式 — 必须在任何 I/O 之前设置
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")

# Windows: 修复控制台编码 + asyncio 子进程事件循环兼容性
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from src.logger import get_logger, setup_logger

from .routes import router

# 配置全局日志：控制台彩色 + 文件输出（RotatingFileHandler 自动轮转）
setup_logger(
    level=logging.INFO,
    log_file=os.path.join("logs", "server.log"),
    use_color=True,
    format_string="%(asctime)s [%(name)s] %(message)s",
)

logger = get_logger("api")
logger.info("=" * 50)
logger.info("Safe-CLI-Agent backend starting...")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Python: {sys.executable}")
logger.info("=" * 50)

app = FastAPI(title="Safe-CLI-Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# ── 生产模式：Serve 前端静态文件 ──────────────────────────
# 仅在桌面端打包后生效（frontend/dist 存在时）
# 不能用 app.mount("/") — 它会拦截所有请求导致 /api/* 路由 404
FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "frontend", "dist"
)

if os.path.exists(FRONTEND_DIST):
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import FileResponse

    class FrontendMiddleware(BaseHTTPMiddleware):
        """非 /api 请求 → 返回 dist/index.html（SPA fallback）"""
        async def dispatch(self, request, call_next):
            # 调试日志
            logger.info(f"[Middleware] 请求: {request.method} {request.url.path}")
            # 排除 API 和 WebSocket 请求
            if request.url.path.startswith("/api") or request.url.path.startswith("/ws"):
                logger.info(f"[Middleware] 跳过: {request.url.path}")
                return await call_next(request)
            # 尝试返回静态文件，不存在则 fallback 到 index.html
            file_path = os.path.join(FRONTEND_DIST, request.url.path.lstrip("/"))
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    app.add_middleware(FrontendMiddleware)
    logger.info(f"前端静态文件服务已启用: {FRONTEND_DIST}")


# ── WebSocket: 容器终端 ──────────────────────────────────

@app.websocket("/ws/terminal/{container_name}")
async def terminal_websocket(websocket: WebSocket, container_name: str):
    """WebSocket 终端：连接到 Docker 容器的交互式 shell"""
    logger.info(f"[Terminal] 收到 WebSocket 请求: {container_name}")
    logger.info(f"[Terminal] Headers: {dict(websocket.headers)}")
    await websocket.accept()
    logger.info(f"[Terminal] WebSocket 已接受: {container_name}")

    try:
        import docker

        from src.executor.client import DockerClientFactory

        client = DockerClientFactory.get()
        container = client.containers.get(container_name)

        # 创建交互式 shell
        exec_obj = container.exec_run(
            cmd=["/bin/sh", "-i"],
            stdin=True,
            stdout=True,
            stderr=True,
            tty=True,
            socket=True,
        )

        # 获取 socket
        sock = exec_obj.output._sock if hasattr(exec_obj.output, '_sock') else exec_obj.output

        async def read_from_container():
            """从容器读取输出并发送到 WebSocket"""
            try:
                while True:
                    # 在线程池中执行阻塞读取
                    loop = asyncio.get_event_loop()
                    data = await loop.run_in_executor(None, lambda: sock.recv(4096))
                    if not data:
                        break
                    await websocket.send_bytes(data)
            except Exception as e:
                logger.debug(f"[Terminal] 读取结束: {e}")

        async def write_to_container():
            """从 WebSocket 读取输入并发送到容器"""
            try:
                while True:
                    data = await websocket.receive_bytes()
                    sock.send(data)
            except WebSocketDisconnect:
                logger.info(f"[Terminal] 客户端断开: {container_name}")
            except Exception as e:
                logger.debug(f"[Terminal] 写入结束: {e}")

        # 并行运行读写
        await asyncio.gather(
            read_from_container(),
            write_to_container(),
        )

    except docker.errors.NotFound:
        await websocket.send_text(f"\r\n❌ 容器不存在: {container_name}\r\n")
        await websocket.close()
    except Exception as e:
        logger.error(f"[Terminal] 错误: {e}")
        await websocket.send_text(f"\r\n❌ 错误: {e}\r\n")
        await websocket.close()
    finally:
        logger.info(f"[Terminal] 连接关闭: {container_name}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
