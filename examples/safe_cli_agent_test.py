import os
import asyncio
import logging

from src.logger import get_logger, setup_logger
from src.llm import LLMClient
from src.agent import WorkerAgent,JudgeAgent,CuratorAgent,ContextManager,Message,PromptManager,ToolRegistry,Tool,TaskPolicy
from src.executor import DockerExecutor,DockerConfig

# 设置日志 - 使用结构化日志，减少噪音
setup_logger(
    level=logging.DEBUG,
    log_file=os.path.join("logs", "agent.log"),
    use_color=True,
    format_string="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = get_logger(__name__)

def setup_tools(workeragent: WorkerAgent, judgeagent: JudgeAgent, executor: DockerExecutor):
    """为Agent注册工具处理函数"""
    # 注册 execute_command 工具的处理函数
    def execute_command_handler(command) -> str:
        """执行命令的处理函数 (结构化增强版)"""
        try:
            logger.info(f"执行命令: {command}")
            stdout, stderr, exit_code = executor.execute_command(command)
            
            result = []
            result.append(f"command: {command}\n")
            if exit_code == 0:
                result.append(f"exit_code: {exit_code}\n")
                result.append(f"stdout:\n{stdout}\n")
            else:
                result.append(f"exit_code: {exit_code}\n")
                result.append(f"stderr:\n{stderr}\n")
            return "\n".join(result)
        except Exception as e:
            return f"执行命令失败: {str(e)}"

    # 注册 judge 工具的处理函数
    async def call_judge_handler(final_answer: str, evidence_summary: str = None) -> str:
        """
        参数名必须匹配 CallJudgeParams 里的字段名
        """
        history = workeragent.context_manager.get_recent_messages(workeragent.name,include_system_prompt=False)
        content = f"""
            'history': {history}
            'answer': {final_answer}
            'evidence': {evidence_summary}
            """ 

        payload = ContextManager.create_assistant_message(
            sender=workeragent.name,
            content=content,
            receivers=[judgeagent.name]
        )

        result = await judgeagent.run(payload)
        
        # 将 Judge 的 ReviewParams 结果转化为字符串返回给 Worker 的 Context
        return f"评审结果: {result}"

    # 外部注入逻辑示例
    async def query_knowledge_handler(command: str) -> str:
        # 强制加上前缀，确保所有操作被限制在知识库目录下
        # 且使用只读方式执行
        safe_command = f"cd /knowledge_base && {command}"
        
        # 这里的 executor 已经在 DockerConfig 里配置了只读挂载
        stdout, stderr, exit_code = await executor.execute_command(
            safe_command, 
            timeout=10 # 检索操作通常很快，10s 足够
        )
        
        if exit_code != 0:
            return f"[Knowledge Base Error]: {stderr or stdout}"
        
        return stdout if stdout.strip() else "No matching knowledge found."

    # 获取工具并设置处理函数
    execute_command_tool = workeragent.tools.get_tool("execute_command")
    if execute_command_tool:
        execute_command_tool.handler = execute_command_handler
    else:
        logger.error("execute_command 工具未注册")

    judge_tool = workeragent.tools.get_tool("call_judge")
    if judge_tool:
        judge_tool.handler = call_judge_handler
    else:
        logger.error("call_judge 工具未注册")

    # 注册 query_knowledge 工具
    query_knowledge_tool = workeragent.tools.get_tool("query_knowledge")
    if query_knowledge_tool:
        query_knowledge_tool.handler = query_knowledge_handler
    else:
        logger.error("query_knowledge 工具未注册")

def execute_curate(llm_client: LLMClient,context_manager: ContextManager, prompt_manager: PromptManager, tools: ToolRegistry):
    curator_cfg = DockerConfig(
        image="alpine:latest",             # 轻量级镜像即可
        container_name="knowledge_manager",
        use_host_workspace=False,          # Curator 不需要 Worker 的工作区
        use_knowledge_base=True,
        kb_mode="rw",                      # 关键：Curator 拥有读写权限
        working_dir="/knowledge_base"      # 落地就在知识库
    )
    curator_executor = DockerExecutor(curator_cfg)
    curator_executor.start_container()
    
    curator = CuratorAgent(llm_client=llm_client,context_manager=context_manager,prompt_manager=prompt_manager,tool_registry=tools)


async def test_safe_cli_agent():
    """测试 Safe-CLI-Agent 完整工作流"""
    print("=" * 60)
    print("测试 Safe-CLI-Agent 完整工作流")
    print("=" * 60)
    
    # 1. 初始化 Docker 执行器
    executor = DockerExecutor()
    
    if not executor.is_available():
        logger.error("Docker 不可用，无法执行测试")
        return
    
    try:
        # 2. 初始化 LLM 客户端
        llm_client = LLMClient()

        # 3. 初始化 Agent
        context_manager = ContextManager()
        prompt_manager = PromptManager()
        tools = ToolRegistry()
        
        judge_agent = JudgeAgent(llm_client=llm_client,context_manager=context_manager,prompt_manager=prompt_manager,tool_registry=tools)
        agent = WorkerAgent(llm_client=llm_client,context_manager=context_manager,prompt_manager=prompt_manager,tool_registry=tools)
        agent.max_iterations = 25

        # 4. 设置工具处理函数
        setup_tools(agent, judge_agent, executor)

        # 5. 测试示例
        test_cases = [
            "当前目录下的这几个文件的内容有可能错乱了，帮我整理一下"
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n" + "=" * 60)
            print(f"测试案例 {i}: {test_case}")
            print("=" * 60)
            
            # 运行 Agent
            response = await agent.run(test_case)
            
            print("\n" + "=" * 60)
            print("🤖 Agent 响应")
            print("=" * 60)
            print(response)
            
            # 等待用户输入，继续下一个测试
            input("\n按 Enter 键继续...")
            
    finally:
        #输出历史信息
        logger.debug(agent.context_manager.format_history("detailed"))
        
        logger.debug(agent.context_manager.get_state_trace())
        # 清理资源
        executor.close()
        print("\n" + "=" * 60)
        print("测试完成，资源已清理")
        print("=" * 60)

async def test_agent_capability():
    task_policy = TaskPolicy(
        allow_kb_search=True,
        allow_curation=True,
        read_only_kb=True,
    )
    # 1. 启动靶场容器
    worker_cfg = DockerConfig(
        image="my_lab_image:latest",       # 靶场镜像
        container_name="worker_sandbox",
        workspace_name="challenge",        # 工作区设为 challenge
        kb_mode="ro",                      # 知识库必须只读！防止 Worker 篡改
        working_dir="/challenge"
    )

    executor = DockerExecutor(worker_cfg)
    
   # 2. 初始化 LLM 客户端
    llm_client = LLMClient()

    # 3. 初始化 Agent
    context_manager = ContextManager()
    prompt_manager = PromptManager(kb_search=task_policy.allow_kb_search)
    tools = ToolRegistry(kb_search=task_policy.allow_kb_search)
    
    judge_agent = JudgeAgent(llm_client=llm_client,context_manager=context_manager,prompt_manager=prompt_manager,tool_registry=tools)
    worker = WorkerAgent(llm_client=llm_client,context_manager=context_manager,prompt_manager=prompt_manager,tool_registry=tools)
    worker.max_iterations = 25
    
    # 3. 注入工具逻辑（包含 call_judge_handler）
    setup_tools(worker, judge_agent, executor)
    
    # 4. 下达任务
    task = f"找到隐藏在 /{workspace_name} 目录下的Flag (可能存在多个)。"
    result = await worker.run(task)
    
    logger.info(f"最终判定结果: {result}")
    #输出历史信息
    logger.debug(worker.context_manager.format_history("detailed"))
    logger.debug(worker.context_manager.get_state_trace())


if __name__ == "__main__":
    asyncio.run(test_agent_capability())
