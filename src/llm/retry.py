import asyncio
import functools
import inspect
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from src.logger import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def retry_sync(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    exponential_backoff: bool = True,
    exceptions: tuple = (Exception,),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None
            delay = retry_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"第 {attempt + 1} 次重试，原因: {e}，等待 {delay:.1f}s"
                        )
                        import time
                        time.sleep(delay)
                        if exponential_backoff:
                            delay *= 2
                    else:
                        logger.error(f"重试 {max_retries} 次后仍然失败: {e}")

            raise last_exception

        return wrapper

    return decorator


def retry_async(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    exponential_backoff: bool = True,
    exceptions: tuple = (Exception,),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None
            delay = retry_delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"第 {attempt + 1} 次重试，原因: {e}，等待 {delay:.1f}s"
                        )
                        await asyncio.sleep(delay)
                        if exponential_backoff:
                            delay *= 2
                    else:
                        logger.error(f"重试 {max_retries} 次后仍然失败: {e}")

            raise last_exception

        # 检查是否是异步生成器函数
        if inspect.iscoroutinefunction(func):
            return wrapper
        else:
            # 对于异步生成器函数，需要特殊处理
            @functools.wraps(func)
            def async_gen_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                async def wrapped_gen():
                    delay = retry_delay

                    for attempt in range(max_retries + 1):
                        try:
                            gen = func(*args, **kwargs)
                            async for item in gen:
                                yield item
                            break  # 成功完成迭代
                        except exceptions as e:
                            if attempt < max_retries:
                                logger.warning(
                                    f"第 {attempt + 1} 次重试，原因: {e}，等待 {delay:.1f}s"
                                )
                                await asyncio.sleep(delay)
                                if exponential_backoff:
                                    delay *= 2
                            else:
                                logger.error(f"重试 {max_retries} 次后仍然失败: {e}")
                                raise
                return wrapped_gen()
            return async_gen_wrapper

    return decorator
