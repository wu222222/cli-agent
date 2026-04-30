from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio

from src.agent import WorkerAgent,JudgeAgent,CuratorAgent,ContextManager,Message,PromptManager,ToolRegistry,Tool,TaskPolicy
from src.executor import DockerExecutor,DockerConfig
from src.orchestrator import AgentOrchestrator
from src.llm.client import LLMClient

# --- 全局单例初始化 ---
# 在实际生产中，你会根据 Session ID 为每个用户创建实例
# 这里为了方便演示，我们创建一个全局共享的实例
llm_client = LLMClient()
context_manager = ContextManager()

# 预设你的测试 Policy
policy = TaskPolicy(allow_kb_search=False, allow_curation=True, read_only_kb=True)
orchestrator = AgentOrchestrator(policy, llm_client, context_manager)



app = FastAPI(title="Safe-CLI-Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    confirmed: Optional[bool] = False

class ChatResponse(BaseModel):
    content: str
    thought: Optional[str] = ""
    type: str = "text"

class HealthResponse(BaseModel):
    status: str = "healthy"

history_store: list = []

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()

@app.post("/agent/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    # 情况 A：用户点击了“确认执行”按钮
    if request.confirmed:
        # 此时 context 中已经有了待执行的命令
        # 触发 orchestrator 内部的“执行并继续”逻辑
        result = await orchestrator.resume_with_action(approved=True)
        return format_response(result)
    
    response_content = f"已收到您的请求: '{request.message}'\n\n这是模拟的执行结果:\n\n```\n示例输出内容\n```"
    
    history_store.append({
        "query": request.message,
        "response": response_content,
        "timestamp": "2024-01-15 14:30:00"
    })
    
    return ChatResponse(
        content=response_content,
        thought="已处理用户请求，返回模拟结果",
        type="text"
    )

@app.get("/agent/history")
async def get_history():
    return history_store

@app.delete("/agent/history")
async def clear_history():
    history_store.clear()
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)