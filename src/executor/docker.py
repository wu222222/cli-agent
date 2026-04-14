import docker
import time
import os
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DockerConfig:
    image: str = "alpine:latest"
    container_name: Optional[str] = None
    network: str = "none"
    cpu_quota: int = 100000  # 100% CPU
    memory_limit: str = "512m"
    workspace_name: str = "workspace"
    workspace: str = os.path.abspath(f"./{workspace_name}")
    timeout: int = 30


class DockerExecutor:
    def __init__(self, config: Optional[DockerConfig] = None):
        self.config = config or DockerConfig()
        self.client = None
        self.container = None
        self._initialize_docker()

    def _initialize_docker(self) -> None:
        try:
            self.client = docker.from_env()
            logger.info("Docker 客户端初始化成功")
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
            # 确保工作目录存在
            os.makedirs(self.config.workspace, exist_ok=True)

            # 创建容器 - 使用 tail -f /dev/null 保持容器运行，并设置工作目录
            self.container = self.client.containers.run(
                self.config.image,
                name=self.config.container_name,
                detach=True,
                tty=True,
                network=self.config.network,
                cpu_quota=self.config.cpu_quota,
                mem_limit=self.config.memory_limit,
                volumes={
                    self.config.workspace: {
                        "bind": f"/{self.config.workspace_name}",
                        "mode": "rw"
                    }
                },
                working_dir=f"/{self.config.workspace_name}",  # 设置工作目录
                command="sh -c 'tail -f /dev/null'"  # 保持容器运行
            )
            logger.info(f"可以使用以下命令进入容器: docker exec -it {self.container.name} sh")
            logger.info(f"容器启动成功: {self.container.id}")
            logger.info(f"容器名称: {self.container.name}")
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
                tty=True,
                stdout=True,
                stderr=True,
                user="nobody"  # 使用非root用户
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

    def close(self) -> None:
        self.stop_container()
        if self.client:
            self.client.close()
            self.client = None
