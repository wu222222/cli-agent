import asyncio
import logging
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Windows: PEP 540 UTF-8 模式 — 必须在任何 I/O 之前设置
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")

# Windows: 修复控制台编码 + asyncio 子进程事件循环兼容性
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from .routes import router
from src.logger import setup_logger, get_logger

# 配置全局日志：控制台彩色 + 文件输出（带时间戳）
setup_logger(
    level=logging.INFO,
    log_file=os.path.join("logs", "server.log"),
    use_color=True,
    format_string="%(asctime)s [%(name)s] %(message)s",
)

logger = get_logger("api")

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
FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "frontend", "dist"
)

if os.path.exists(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    logger.info(f"前端静态文件服务已启用: {FRONTEND_DIST}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
