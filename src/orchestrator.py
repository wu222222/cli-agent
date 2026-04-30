import os
from typing import Optional
from src.logger import get_logger
from src.llm.client import LLMClient
from src.agent.context import ContextManager
from src.agent.prompt import PromptManager
from src.agent.tools import ToolRegistry, Tool
from src.agent.agent import WorkerAgent, JudgeAgent, CuratorAgent
from src.agent.types import TaskPolicy, ActionType
from src.executor.docker import DockerExecutor, DockerConfig

logger = get_logger(__name__)

class AgentOrchestrator:
    def __init__(
        self, 
        policy: TaskPolicy,
        llm_client: Optional[LLMClient] = None,
        context_manager: Optional[ContextManager] = None
    ):
        self.policy = policy
        # 支持外部传入已配置好的 Client，否则使用默认配置
        self.llm_client = llm_client or LLMClient()
        self.context_manager = context_manager or ContextManager()
        
        # 提示词和工具注册表依然根据 policy 动态生成
        self.prompt_manager = PromptManager(kb_search=policy.allow_kb_search)
        self.tool_registry = ToolRegistry(kb_search=policy.allow_kb_search)

    async def run_step_by_step(
        self,
        task_description: str,
        worker_config: DockerConfig,  # 1. 外部传入配置好的 Docker 环境
    ):
        judge = JudgeAgent(
            llm_client=self.llm_client, 
            context_manager=self.context_manager, 
            prompt_manager=self.prompt_manager, 
            tool_registry=self.tool_registry
            )
        worker = WorkerAgent(
            llm_client=self.llm_client, 
            context_manager=self.context_manager, 
            prompt_manager=self.prompt_manager, 
            tool_registry=self.tool_registry
            )
        judge.max_iterations = 10
        worker.max_iterations = 25

        self._setup_worker_handlers(worker, judge, worker_executor)

        

    async def run_mission(
        self, 
        task_description: str,
        worker_config: DockerConfig,  # 1. 外部传入配置好的 Docker 环境
        curator_config: Optional[DockerConfig] = None # 可选的 Curator 配置
    ):
        logger.info(f"🚀 开始任务 : {task_description}")

        try:
            async with DockerExecutor(worker_config) as worker_executor:
                if not worker_executor.is_available():
                    return "Docker 不可用"

                # 2. 这里的 Agent 也可以通过工厂方法创建，以适配不同的 LLM config
                judge = JudgeAgent(
                    llm_client=self.llm_client, 
                    context_manager=self.context_manager, 
                    prompt_manager=self.prompt_manager, 
                    tool_registry=self.tool_registry
                    )
                worker = WorkerAgent(
                    llm_client=self.llm_client, 
                    context_manager=self.context_manager, 
                    prompt_manager=self.prompt_manager, 
                    tool_registry=self.tool_registry
                    )
                judge.max_iterations = 10
                worker.max_iterations = 25

                self._setup_worker_handlers(worker, judge, worker_executor)

                final_result = await worker.run(task_description)

                # 3. 自动触发 Curator
                if self.policy.allow_curation:
                    # 如果外部没给 curator_config，我们提供一个默认的 Alpine 环境
                    cfg = curator_config or self._get_default_curator_config()
                    await self._run_curation_phase(cfg)
                
                return final_result
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            return f"任务执行失败: {e}"

    def ensure_kb_structure(self, base_path: str = "./knowledge_base"):
        sub_dirs = ["linux", "security", "tools", "troubleshooting"]
        for d in sub_dirs:
            path = os.path.join(base_path, d)
            if not os.path.exists(path):
                os.makedirs(path)
                # 自动生成一个简单的 README 说明
                with open(os.path.join(path, "info.txt"), "w") as f:
                    f.write(f"This directory is for {d} related knowledge.")

    def _get_default_curator_config(self) -> DockerConfig:
        """默认的知识库维护环境"""
        if not os.path.exists("./knowledge_base"):
            self.ensure_kb_structure()

        return DockerConfig(
            image="alpine:latest",
            container_name="curator_sandbox",
            use_host_workspace=False,
            kb_mode="rw",
            working_dir="/knowledge_base"
        )
        
    def _setup_worker_handlers(self, worker: WorkerAgent, judge: JudgeAgent, executor: DockerExecutor):
        """注入 Worker 运行所需的工具处理逻辑"""
        
        # Handler: 执行命令
        async def exec_handler(command: str):
            stdout, stderr, exit_code = executor.execute_command(command)
            return f"EXIT_CODE: {exit_code}\nSTDOUT: {stdout}\nSTDERR: {stderr}"

        # Handler: 询问法官
        async def judge_handler(final_answer: str, evidence_summary: str = ""):
            # 构造法官的输入消息
            history = worker.context_manager.get_recent_messages(worker.name,include_system_prompt=False)
            content = f"""
                'history': {history}
                'answer': {final_answer}
                'evidence': {evidence_summary}
                """ 

            payload = ContextManager.create_assistant_message(
                sender=worker.name,
                content=content,
                receivers=[judge.name]
            )

            result = await judge.run(payload)
        
            return f"评审结果: {result}"

        # Handler: 查阅知识库
        async def kb_handler(command: str):
            safe_command = f"cd /knowledge_base && {command}"
            stdout, stderr, exit_code = executor.execute_command(safe_command)
            return stdout if exit_code == 0 else f"KB Error: {stderr}"

        # 绑定到 Tool 对象上
        self.tool_registry.get_tool(ActionType.EXECUTE_COMMAND.value).handler = exec_handler
        self.tool_registry.get_tool(ActionType.CALL_JUDGE.value).handler = judge_handler
        if self.policy.allow_kb_search:
            self.tool_registry.get_tool(ActionType.QUERY_KNOWLEDGE.value).handler = kb_handler

    async def _run_curation_phase(self, curator_config: DockerConfig):
        """
        知识整理阶段：启动全新的只读/写容器
        """
        logger.info("🎨 开始知识整理阶段...")
        
        try:
            async with DockerExecutor(curator_config) as curator_executor:
                if not curator_executor.is_available():
                    return "Docker 不可用"
            # 注入 Curator 专属 Handler
            async def curator_exec_handler(command: str):
                stdout, stderr, exit_code = curator_executor.execute_command(command)
                return f"Result: {stdout if exit_code == 0 else stderr}"

            # 这里我们可以动态注册一个 Curator 专用命令工具，或者复用 execute_command
            self.tool_registry.get_tool(ActionType.EXECUTE_COMMAND.value).handler = curator_exec_handler
            
            curator = CuratorAgent(
                llm_client=self.llm_client, 
                context_manager=self.context_manager, 
                prompt_manager=self.prompt_manager, 
                tool_registry=self.tool_registry
                )
            curator.max_iterations = 20
            # 让 Curator 总结历史并写入 KB
            # 这里的 input 可以是从 context_manager 提取的精华历史
            curator_task = "Analyze the previous successful session and update relevant .md files in the KB."
            result = await curator.run(curator_task)
            logger.info(f"知识整理阶段执行结果: {result}")
        except Exception as e:
            logger.error(f"知识整理阶段执行失败: {e}")