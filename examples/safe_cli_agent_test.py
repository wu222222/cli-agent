import asyncio
import os
import sys
import logging

# 添加项目根目录到Python路径
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.logger import get_logger, setup_logger
from src.llm import LLMClient
from src.agent import WorkerAgent, JudgeAgent,ContextManager,Message,PromptManager,ToolRegistry,Tool
from src.executor import DockerExecutor

# 设置日志 - 使用结构化日志，减少噪音
setup_logger(
    level=logging.DEBUG,  
    use_color=True,      # 使用彩色输出
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
            "简述当前目录下这几个文件的内容"
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


if __name__ == "__main__":
    asyncio.run(test_safe_cli_agent())
