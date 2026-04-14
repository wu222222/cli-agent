import asyncio
import os
import sys
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.logger import get_logger, setup_logger
from src.llm import LLMClient
from src.agent import Agent
from src.executor import DockerExecutor

# 设置日志 - 使用结构化日志，减少噪音
setup_logger(
    level=logging.DEBUG,  #  提高日志级别，减少调试信息
    use_color=True,      # 使用彩色输出
    format_string="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = get_logger(__name__)


def setup_tools(agent, executor):
    """为Agent注册工具处理函数"""
    # 注册 execute_command 工具的处理函数
    def execute_command_handler(command):
        """执行命令的处理函数"""
        try:
            logger.info(f"执行命令: {command}")
            stdout, stderr, exit_code = executor.execute_command(command)
            result = f"退出码: {exit_code}\n\n标准输出:\n{stdout}\n\n标准错误:\n{stderr}"
            return result
        except Exception as e:
            return f"执行命令失败: {str(e)}"
    
    # 获取工具并设置处理函数
    execute_command_tool = agent.tools.get_tool("execute_command")
    if execute_command_tool:
        execute_command_tool.handler = execute_command_handler



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
        agent = Agent(llm_client=llm_client)
        
        # 4. 设置工具处理函数
        setup_tools(agent, executor)
        
        # 5. 设置确认处理器
        def confirmation_handler(prompt: str) -> bool:
            """人机确认处理器"""
            print("\n" + "=" * 60)
            print("🔐 安全确认")
            print("=" * 60)
            print(f"⚠️  {prompt}")
            print("\n该命令将在隔离的 Docker 容器中执行，不会影响宿主机。")
            
            # 等待用户确认
            while True:
                confirm = input("\n是否确认执行？(y/n): ").lower().strip()
                if confirm == 'y':
                    return True
                elif confirm == 'n':
                    return False
                else:
                    print("请输入 'y' 或 'n'")
        
        agent.set_confirmation_handler(confirmation_handler)
        
        # 6. 测试示例
        test_cases = [
            "简述当前目录下这几个文件的内容"
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n" + "=" * 60)
            print(f"测试案例 {i}: {test_case}")
            print("=" * 60)
            
            # 运行 Agent
            response = await agent.chat(test_case)
            
            print("\n" + "=" * 60)
            print("🤖 Agent 响应")
            print("=" * 60)
            print(response)
            
            # 等待用户输入，继续下一个测试
            input("\n按 Enter 键继续...")
            
    finally:
        # 清理资源
        executor.close()
        print("\n" + "=" * 60)
        print("测试完成，资源已清理")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_safe_cli_agent())
