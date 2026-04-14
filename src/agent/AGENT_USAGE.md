# Agent 模块使用指南

本文档旨在帮助未来的AI理解如何使用 Safe-CLI-Agent 中的 Agent 模块。

## 1. 模块概述

Agent 模块是一个具备 **自我推理 (Reasoning)** 与 **工具调用 (Tool Use)** 能力的智能助手核心，基于 ReAct 模式实现。其主要功能包括：

- **ReAct 循环**：思考-行动-观察的推理过程
- **Function Calling**：支持工具调用格式
- **上下文管理**：维护对话历史和状态
- **人机确认**：危险操作的安全拦截

## 2. 安装与依赖

### 2.1 环境要求

- Python 3.10+
- 依赖包：
  - `openai` (用于LLM调用)
  - `docker` (用于沙盒执行)
  - `python-dotenv` (用于环境配置)
  - `rich` (用于CLI界面)

### 2.2 安装步骤

```bash
# 创建并激活虚拟环境
conda create -n safe-cli-agent python=3.10 -y
conda activate safe-cli-agent

# 安装依赖
pip install openai docker python-dotenv rich

# 配置环境变量
# 复制 .env.example 为 .env 并填写 API Key
cp .env.example .env
```

## 3. 基本使用

### 3.1 初始化 Agent

```python
from src.agent import Agent
from src.llm import LLMConfig

# 配置LLM
config = LLMConfig(api_key="your_api_key")

# 创建Agent实例
agent = Agent()

# 或者使用自定义配置
# agent = Agent(llm_client=custom_llm_client)
```

### 3.2 注册工具

```python
from src.agent import Tool

# 注册执行命令工具
agent.register_tool(Tool(
    name="execute_command",
    description="在Docker沙盒中执行Shell命令",
    parameters={
        "command": {
            "type": "string",
            "description": "要执行的Shell命令"
        }
    },
    required_params=["command"],
    handler=lambda command: f"执行结果: {command}"  # 实际实现会调用Docker
))

# 注册读取文件工具
agent.register_tool(Tool(
    name="read_file",
    description="读取文件内容",
    parameters={
        "file_path": {
            "type": "string",
            "description": "文件路径"
        }
    },
    required_params=["file_path"],
    handler=lambda file_path: f"文件内容: {file_path}"
))

# 注册写入文件工具
agent.register_tool(Tool(
    name="write_file",
    description="写入文件内容",
    parameters={
        "file_path": {
            "type": "string",
            "description": "文件路径"
        },
        "content": {
            "type": "string",
            "description": "要写入的内容"
        }
    },
    required_params=["file_path", "content"],
    handler=lambda file_path, content: f"已写入文件: {file_path}"
))
```

### 3.3 运行 Agent

```python
import asyncio

async def main():
    # 运行Agent
    response = await agent.chat("列出当前目录的文件")
    print("Agent 响应:", response)

    # 继续对话
    response = await agent.chat("查看README.md文件内容")
    print("Agent 响应:", response)

# 执行
asyncio.run(main())
```

## 4. 高级配置

### 4.1 上下文管理

```python
# 设置系统提示
agent.context.set_system_prompt("你是一个专业的命令行助手，擅长解决技术问题")

# 查看上下文摘要
print(agent.get_context_summary())

# 清除上下文
agent.clear_context()
```

### 4.2 人机确认

```python
def confirmation_handler(prompt):
    """确认处理函数"""
    print(f"\n⚠️  确认请求:\n{prompt}")
    user_input = input("是否确认执行? (y/n): ")
    return user_input.lower() == 'y'

# 设置确认处理函数
agent.set_confirmation_handler(confirmation_handler)
```

### 4.3 自定义 Prompt

```python
# 添加自定义Prompt
agent.prompts.add_custom_prompt(
    "debug_mode",
    "请以调试模式运行，详细解释每一步操作"
)

# 使用自定义Prompt
custom_system_prompt = agent.prompts.get_system_prompt() + "\n" + agent.prompts.get_custom_prompt("debug_mode")
agent.context.set_system_prompt(custom_system_prompt)
```

## 5. 工具调用格式

当需要调用工具时，LLM 应使用以下 JSON 格式：

```json
{
    "thought": "你的思考过程",
    "action": {
        "name": "工具名称",
        "parameters": {
            "参数名": "参数值"
        }
    }
}
```

### 5.1 示例

```json
{
    "thought": "用户需要查看当前目录的文件列表，我需要调用execute_command工具执行ls命令",
    "action": {
        "name": "execute_command",
        "parameters": {
            "command": "ls -la"
        }
    }
}
```

## 6. 安全注意事项

1. **执行命令**：所有命令会在Docker沙盒中执行，与宿主机隔离
2. **权限限制**：容器默认禁用 `--privileged` 模式，使用非root用户
3. **网络隔离**：默认添加 `--network none`，防止网络访问
4. **超时控制**：每个指令有30秒超时限制
5. **敏感操作**：会触发人机确认拦截层

## 7. 最佳实践

1. **明确需求**：向Agent提供清晰、具体的指令
2. **上下文管理**：对于复杂任务，保持对话的连贯性
3. **工具使用**：当需要执行系统操作时，明确要求Agent使用相应工具
4. **安全意识**：对于涉及文件修改、网络操作等敏感任务，仔细审查确认
5. **错误处理**：当Agent执行失败时，提供更多上下文信息

## 8. 故障排除

### 8.1 常见问题

1. **API Key 错误**：确保在 `.env` 文件中正确设置了 `DASHSCOPE_API_KEY`
2. **Docker 连接失败**：确保Docker守护进程正在运行
3. **工具调用失败**：检查工具参数是否正确，确保工具已注册
4. **上下文过长**：Agent会自动裁剪历史记录，如需更多上下文可调整 `max_history` 参数

### 8.2 调试技巧

1. **启用日志**：设置日志级别为 DEBUG 查看详细信息
2. **检查状态**：使用 `agent.get_state()` 查看Agent当前状态
3. **简化指令**：将复杂任务分解为多个简单步骤
4. **工具测试**：单独测试工具执行是否正常

## 9. 扩展指南

### 9.1 自定义工具

```python
# 创建自定义工具
class DatabaseTool(Tool):
    def __init__(self):
        super().__init__(
            name="query_database",
            description="查询数据库",
            parameters={
                "query": {
                    "type": "string",
                    "description": "SQL查询语句"
                }
            },
            required_params=["query"]
        )

    def execute(self, query):
        # 实现数据库查询逻辑
        return f"查询结果: {query}"

# 注册自定义工具
db_tool = DatabaseTool()
db_tool.handler = db_tool.execute
agent.register_tool(db_tool)
```

### 9.2 多Agent协同

```python
# 创建多个Agent实例
code_agent = Agent()
data_agent = Agent()

# 为不同Agent注册不同工具
code_agent.register_tool(Tool(
    name="execute_code",
    description="执行代码",
    parameters={"code": {"type": "string", "description": "代码"}},
    required_params=["code"]
))

data_agent.register_tool(Tool(
    name="analyze_data",
    description="分析数据",
    parameters={"data": {"type": "string", "description": "数据"}},
    required_params=["data"]
))
```

## 10. 总结

Agent 模块提供了一个强大的框架，使AI能够通过推理和工具调用来解决复杂问题。通过遵循本指南，您可以充分利用其功能，构建安全、高效的智能助手系统。

关键特性：
- **安全性**：Docker沙盒隔离
- **智能性**：ReAct推理循环
- **灵活性**：可扩展的工具系统
- **可靠性**：人机确认机制

祝您使用愉快！
