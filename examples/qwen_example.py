import asyncio
from src.logger import get_logger, setup_logger
from src.llm import LLMClient, LLMConfig

# 设置日志级别为INFO
setup_logger(level=10)

logger = get_logger(__name__)


def test_sync_chat():
    print("=" * 50)
    print("测试同步调用")
    print("=" * 50)

    config = LLMConfig.from_env()
    client = LLMClient(config)

    messages = [
        {"role": "system", "content": "你是一个有帮助的助手。"},
        {"role": "user", "content": "你好，请用一句话介绍你自己。"},
    ]

    try:
        response = client.chat(messages)
        print(f"回复: {response}")
    except Exception as e:
        print(f"同步调用失败: {e}")
    finally:
        client.close()


async def test_async_chat():
    print("\n" + "=" * 50)
    print("测试异步调用")
    print("=" * 50)

    config = LLMConfig.from_env()
    client = LLMClient(config)

    messages = [
        {"role": "system", "content": "你是一个有帮助的助手。"},
        {"role": "user", "content": "请用一句话解释什么是Docker。"},
    ]

    try:
        response = await client.achat(messages)
        print(f"回复: {response}")
    except Exception as e:
        print(f"异步调用失败: {e}")
    finally:
        await client.aclose()


async def test_stream_chat():
    print("\n" + "=" * 50)
    print("测试流式调用")
    print("=" * 50)

    config = LLMConfig.from_env()
    client = LLMClient(config)

    messages = [
        {"role": "system", "content": "你是一个有帮助的助手。"},
        {"role": "user", "content": "请列出Python的三个优点。"},
    ]

    try:
        print("回复: ", end="", flush=True)
        async for chunk in client.achat_stream(messages):
            print(chunk, end="", flush=True)
        print()
    except Exception as e:
        print(f"\n流式调用失败: {e}")
    finally:
        await client.aclose()


async def test_context_manager():
    print("\n" + "=" * 50)
    print("测试上下文管理器")
    print("=" * 50)

    config = LLMConfig.from_env()

    async with LLMClient(config) as client:
        messages = [
            {"role": "user", "content": "1+1等于几？"},
        ]
        response = await client.achat(messages)
        print(f"回复: {response}")


def main():
    test_sync_chat()
    asyncio.run(test_async_chat())
    asyncio.run(test_stream_chat())
    asyncio.run(test_context_manager())


if __name__ == "__main__":
    main()
