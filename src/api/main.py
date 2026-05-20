import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
