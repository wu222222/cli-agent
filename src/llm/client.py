from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncOpenAI, OpenAI

from src.logger import get_logger

from .config import LLMConfig
from .retry import retry_async, retry_sync

logger = get_logger(__name__)


class LLMClient:
    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig.from_env()
        self._sync_client: OpenAI | None = None
        self._async_client: AsyncOpenAI | None = None

        self.initialize_clients_logger()

    def initialize_clients_logger(self) -> None:
        logger.info(f"初始化LLM客户端,模型名称: {self.config.model}")

    @property
    def sync_client(self) -> OpenAI:
        if self._sync_client is None:
            self._sync_client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        return self._sync_client

    @property
    def async_client(self) -> AsyncOpenAI:
        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        return self._async_client

    @retry_sync(max_retries=3, retry_delay=1.0, exponential_backoff=True)
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        response = self.sync_client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            **kwargs,
        )
        content = response.choices[0].message.content
        logger.debug(f"同步调用完成，使用模型: {self.config.model}")
        logger.debug(f"输入消息: {messages}")
        return content

    @retry_async(max_retries=3, retry_delay=1.0, exponential_backoff=True)
    async def achat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        response = await self.async_client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            **kwargs,
        )
        content = response.choices[0].message.content
        logger.debug(f"异步调用完成，使用模型: {self.config.model}")
        logger.debug(f"输入消息: {messages}")
        return content

    @retry_async(max_retries=3, retry_delay=1.0, exponential_backoff=True)
    async def achat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        stream = await self.async_client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            stream=True,
            **kwargs,
        )
        logger.debug(f"输入消息: {messages}")
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def close(self) -> None:
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None

    async def aclose(self) -> None:
        if self._async_client:
            await self._async_client.close()
            self._async_client = None

    def __enter__(self) -> "LLMClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    async def __aenter__(self) -> "LLMClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.aclose()
