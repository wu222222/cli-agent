import asyncio
import os
from src.executor import DockerExecutor
from src.logger import setup_logger, get_logger

# 设置日志
setup_logger(level=10)
logger = get_logger(__name__)


def test_docker_availability():
    """测试Docker是否可用"""
    print("=" * 50)
    print("测试Docker可用性")
    print("=" * 50)

    executor = DockerExecutor()
    is_available = executor.is_available()
    print(f"Docker 可用: {is_available}")

    if not is_available:
        print("Docker 不可用，跳过后续测试")
    
    executor.close()
    return is_available


def test_container_management():
    """测试容器管理功能"""
    print("\n" + "=" * 50)
    print("测试容器管理")
    print("=" * 50)

    executor = DockerExecutor()

    try:
        # 启动容器
        start_success = executor.start_container()
        print(f"启动容器: {start_success}")

        if start_success:
            # 执行简单命令
            stdout, stderr, exit_code = executor.execute_command("echo 'Hello, Docker!'")
            print(f"执行命令结果:")
            print(f"  退出码: {exit_code}")
            print(f"  输出: {stdout.strip()}")
            print(f"  错误: {stderr.strip()}")

        # 停止容器
        stop_success = executor.stop_container()
        print(f"停止容器: {stop_success}")

    finally:
        executor.close()


def test_command_execution():
    """测试命令执行功能"""
    print("\n" + "=" * 50)
    print("测试命令执行")
    print("=" * 50)

    executor = DockerExecutor()

    try:
        # 测试ls命令
        print("\n测试 ls 命令:")
        stdout, stderr, exit_code = executor.execute_command("ls -la")
        print(f"  退出码: {exit_code}")
        print(f"  输出: {stdout.strip()}")

        # 测试创建文件
        print("\n测试创建文件:")
        test_content = "Hello from Docker!"
        executor.execute_command(f"echo '{test_content}' > /{executor.config.workspace_name}/test.txt")
        
        # 测试读取文件
        print("\n测试读取文件:")
        stdout, stderr, exit_code = executor.execute_command(f"cat /{executor.config.workspace_name}/test.txt")
        print(f"  退出码: {exit_code}")
        print(f"  文件内容: {stdout.strip()}")

        # 测试超时
        print("\n测试命令超时:")
        stdout, stderr, exit_code = executor.execute_command("sleep 5", timeout=2)
        print(f"  退出码: {exit_code}")
        print(f"  错误: {stderr.strip()}")

    finally:
        executor.close()


def test_context_manager():
    """测试上下文管理器"""
    print("\n" + "=" * 50)
    print("测试上下文管理器")
    print("=" * 50)

    with DockerExecutor() as executor:
        stdout, stderr, exit_code = executor.execute_command("echo 'Context manager test'")
        print(f"  退出码: {exit_code}")
        print(f"  输出: {stdout.strip()}")

    print("容器已自动关闭")


def main():
    """主测试函数"""
    is_docker_available = test_docker_availability()

    if is_docker_available:
        test_container_management()
        test_command_execution()
        test_context_manager()
    else:
        print("Docker 不可用，无法运行完整测试")


if __name__ == "__main__":
    main()
