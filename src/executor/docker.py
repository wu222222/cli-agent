import docker
import time
import os
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

from src.logger import get_logger
from .client import DockerClientFactory

logger = get_logger(__name__)


@dataclass
class DockerConfig:
    # 基础镜像配置
    image: str = "alpine:latest"
    container_name: Optional[str] = None
    network: str = "none"
    cpu_quota: int = 100000 
    memory_limit: str = "512m"
    timeout: int = 30

    # 工作空间配置 (Workspace)
    use_host_workspace: bool = True
    workspace_name: str = "workspace"
    workspace: str = os.path.abspath(f"./{workspace_name}")
    workspace_mode: str = "rw"  # 新增：控制工作区的读写权限 ("rw" 或 "ro")

    # 知识库配置 (Knowledge Base)
    use_knowledge_base: bool = True
    kb_path: str = os.path.abspath("./knowledge_base")
    kb_container_path: str = "/knowledge_base"
    kb_mode: str = "ro"  # 新增：控制知识库的读写权限 ("rw" 或 "ro")

    # 运行时目录配置
    # 如果不指定，则使用镜像默认工作目录；如果指定，启动时会切换到这里
    working_dir: Optional[str] = None


class DockerExecutor:
    def __init__(self, config: Optional[DockerConfig] = None):
        self.config = config or DockerConfig()
        self.client = None
        self.container = None
        self._initialize_docker()

    def _initialize_docker(self) -> None:
        try:
            self.client = DockerClientFactory.get()
            logger.info(f"Docker 客户端就绪, image: {self.config.image}")
        except docker.errors.DockerException as e:
            logger.error(f"Docker 初始化失败: {e}")
            logger.warning("Docker 守护进程未启动或无法连接")
            self.client = None

    def is_available(self) -> bool:
        return self.client is not None

    def start_container(self) -> bool:
        if not self.is_available():
            logger.error("Docker 不可用，无法启动容器")
            return False

        try:
            # 1. 预清理同名容器（防止调试时频繁报错）
            if self.config.container_name:
                try:
                    old_cont = self.client.containers.get(self.config.container_name)
                    logger.info(f"清理旧容器: {self.config.container_name}")
                    old_cont.remove(force=True)
                except docker.errors.NotFound:
                    pass

            # 2. 决定是否挂载
            volumes = {}
            # 1. 处理工作空间挂载
            if self.config.use_host_workspace:
                #检测工作空间是否存在，不存在则报错
                if not os.path.exists(self.config.workspace):
                    logger.error(f"工作空间 {self.config.workspace} 不存在")
                    return False
                # os.makedirs(self.config.workspace, exist_ok=True)
                volumes[self.config.workspace] = {
                    "bind": f"/{self.config.workspace_name}",
                    "mode": self.config.workspace_mode # 使用配置的 mode
                }
            
            # 2. 处理知识库挂载
            if self.config.use_knowledge_base:
                #检测知识库是否存在，不存在则报错
                if not os.path.exists(self.config.kb_path):
                    logger.error(f"知识库 {self.config.kb_path} 不存在")
                    return False
                # os.makedirs(self.config.kb_path, exist_ok=True)
                volumes[self.config.kb_path] = {
                    "bind": self.config.kb_container_path,
                    "mode": self.config.kb_mode # 使用配置的 mode
                }

            # 3. 启动容器
            self.container = self.client.containers.run(
                self.config.image,
                name=self.config.container_name,
                detach=True,
                tty=True,
                stdin_open=True,
                network=self.config.network,
                cpu_quota=self.config.cpu_quota,
                mem_limit=self.config.memory_limit,
                volumes=volumes,
                # 使用配置的 working_dir，如果为 None 则由 Docker 镜像决定
                working_dir=self.config.working_dir,
                command="sh -c 'tail -f /dev/null'"
            )
            
            logger.info(f"容器启动成功: {self.container.name} (Image: {self.config.image})")
            return True
        except Exception as e:
            logger.error(f"容器启动失败: {e}")
            return False

    def execute_command(self, command: str, timeout: Optional[int] = None) -> Tuple[str, str, int]:
        if not self.is_available():
            return "", "Docker 不可用", 1

        if not self.container:
            if not self.start_container():
                return "", "容器启动失败", 1

        try:
            exec_timeout = timeout or self.config.timeout
            logger.info(f"执行命令: {command} (超时: {exec_timeout}s)")

            # 执行命令 - 容器已经设置了工作目录
            exit_code, output = self.container.exec_run(
                ["sh", "-c", command],
                detach=False,
                tty=False,
                stdout=True,
                stderr=True,
                # user="nobody"  # 使用非root用户
            )

            # 处理输出
            stdout = output.decode('utf-8', errors='replace') if output else ""
            stderr = ""

            logger.info(f"命令执行完成，退出码: {exit_code}")
            return stdout, stderr, exit_code

        except docker.errors.ContainerError as e:
            logger.error(f"容器执行错误: {e}")
            return e.output.decode('utf-8', errors='replace'), str(e), e.exit_status
        except docker.errors.APIError as e:
            logger.error(f"API 错误: {e}")
            return "", str(e), 1
        except Exception as e:
            logger.error(f"执行命令时发生错误: {e}")
            return "", str(e), 1

    def stop_container(self) -> bool:
        if not self.container:
            return True

        try:
            self.container.stop(timeout=5)
            self.container.remove(force=True)
            logger.info(f"容器已销毁: {self.container.id}")
            self.container = None
            return True
        except Exception as e:
            logger.error(f"停止容器失败: {e}")
            return False

    def __enter__(self) -> "DockerExecutor":
        self.start_container()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop_container()

    async def __aenter__(self) -> "DockerExecutor":
        # 如果你的 start_container 是同步的，直接调用即可
        # 如果追求完美，可以使用 asyncio.to_thread 运行它
        self.start_container()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop_container()

    def close(self) -> None:
        self.stop_container()
        if self.client:
            self.client.close()
            self.client = None


class PluginContainerManager:
    """管理插件容器的生命周期（持久化 daemon 模式）"""

    def __init__(self):
        self.client = None
        self._containers: Dict[str, Any] = {}
        try:
            self.client = DockerClientFactory.get()
        except Exception as e:
            logger.error(f"PluginContainerManager Docker 初始化失败: {e}")

    def is_available(self) -> bool:
        return self.client is not None

    def ensure_running(self, container_name: str, image: str = "", volumes: Optional[Dict[str, Dict[str, str]]] = None, network_mode: str = "none", privileged: bool = False) -> bool:
        """确保插件容器在后台运行

        Args:
            container_name: 容器名称
            image: 容器镜像
            volumes: 卷挂载配置，格式: {host_path: {"bind": container_path, "mode": "ro/rw"}}
            network_mode: 网络模式，"none"=断网（默认安全），"bridge"=NAT 联网
            privileged: 特权模式，nmap 等需要 raw socket 的工具必须开启
        """
        if not self.is_available():
            logger.error("Docker 不可用，无法管理插件容器")
            return False

        try:
            # 检查容器是否已存在
            try:
                container = self.client.containers.get(container_name)
                if container.status == 'running':
                    self._containers[container_name] = container
                    logger.info(f"插件容器已在运行: {container_name}")
                    return True
                else:
                    # 容器存在但未运行，启动它
                    container.start()
                    self._containers[container_name] = container
                    logger.info(f"插件容器已启动: {container_name}")
                    return True
            except docker.errors.NotFound:
                pass

            # 容器不存在，创建并启动
            if not image:
                logger.error(f"插件容器 '{container_name}' 不存在且未指定镜像")
                return False

            container = self.client.containers.run(
                image,
                name=container_name,
                detach=True,
                tty=True,
                network=network_mode,
                privileged=privileged,
                volumes=volumes or {},
                command="sh -c 'tail -f /dev/null'"
            )
            self._containers[container_name] = container
            logger.info(f"插件容器创建并启动: {container_name} (image: {image})")
            return True

        except Exception as e:
            logger.error(f"确保插件容器运行失败: {e}")
            return False

    def get_container(self, container_name: str):
        """获取已运行的容器"""
        if container_name in self._containers:
            return self._containers[container_name]

        # 尝试从 Docker 获取
        if self.is_available():
            try:
                container = self.client.containers.get(container_name)
                if container.status == 'running':
                    self._containers[container_name] = container
                    return container
            except docker.errors.NotFound:
                pass

        return None

    def stop_all(self) -> None:
        """停止所有管理的插件容器"""
        for name, container in self._containers.items():
            try:
                container.stop(timeout=5)
                logger.info(f"插件容器已停止: {name}")
            except Exception as e:
                logger.warning(f"停止插件容器失败: {name} ({e})")
        self._containers.clear()

    def close(self) -> None:
        self.stop_all()
        if self.client:
            self.client.close()
            self.client = None
