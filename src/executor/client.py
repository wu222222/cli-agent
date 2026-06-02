"""全局 Docker 客户端工厂，避免重复初始化 docker.from_env()"""
import logging

import docker

logger = logging.getLogger("executor")


class DockerClientFactory:
    _instance: docker.DockerClient | None = None

    @classmethod
    def get(cls) -> docker.DockerClient:
        if cls._instance is None:
            cls._instance = docker.from_env()
            logger.info("Docker 客户端初始化成功 (singleton)")
        return cls._instance

    @classmethod
    def reset(cls):
        if cls._instance:
            cls._instance.close()
            cls._instance = None
            logger.info("Docker 客户端已重置")
