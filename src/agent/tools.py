from typing import Dict, Any, Callable, Optional, List, Union, Awaitable

from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
import json

from .types import *


class Tool(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    required_params: List[str] = Field(default_factory=list)

    # 支持同步或异步处理函数
    handler: Optional[Union[Callable[..., Any], Callable[..., Awaitable[Any]]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required_params
                }
            }
        }



class ToolRegistry:
    def __init__(self,kb_search: bool = False):
        self._tools: Dict[str, Tool] = {}
        self.kb_search = kb_search
        # 注册默认工具
        self._register_default_tools(kb_search)

    def _register_default_tools(self,kb_search: bool = False) -> None:
        """
        在这里只定义工具的说明文档。
        具体的 handler（如 docker 执行逻辑）建议在外部（如在 Worker 初始化时）注入。
        """
        self.register(Tool(
            name=ActionType.EXECUTE_COMMAND.value,
            description="在指定的 Docker 容器中执行 Shell 命令",
            parameters={
                "command": {
                    "type": "string",
                    "description": "要执行的 Shell 命令"
                }
            },
            required_params=["command"]
        ))

        self.register(Tool(
            name=ActionType.CALL_JUDGE.value,
            description="让法官判断最终结果是否符合预期",
            parameters={
                "final_answer": {
                    "type": "string",
                    "description": "最终准备给用户的判断结果"
                },
                "evidence_summary": {
                    "type": "string",
                    "description": "简述你得出此结论的证据链（可选）"
                }
            },
            required_params=["final_answer"]
        ))
        
        if kb_search:
            self.register(Tool(
                name=ActionType.QUERY_KNOWLEDGE.value,
                description=(
                    "Search and query the local knowledge base for CLI best practices, "
                    "troubleshooting steps, and command syntax. The knowledge base is "
                    "stored in '/knowledge_base' and is read-only. "
                    "Use standard commands like 'ls -R', 'grep', 'find', or 'cat' to "
                    "explore files and extract information. "
                    "Example: 'grep -r \"Permission denied\" /knowledge_base' to find solutions."
                ),
                parameters={
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute inside the knowledge base directory."
                    }
                },
                required_params=["command"]
            ))

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def get_all_tools(self) -> List[Dict[str, Any]]:
        return [tool.to_dict() for tool in self._tools.values()]

    # def execute_tool(self, name: str, params: Dict[str, Any]) -> str:
    #     tool = self.get_tool(name)
    #     if not tool:
    #         return f"错误: 未找到工具 '{name}'"

    #     if not tool.validate_params(params):
    #         return f"错误: 工具 '{name}' 参数验证失败，缺少必需参数"

    #     if tool.handler:
    #         try:
    #             result = tool.handler(**params)
    #             return str(result)
    #         except Exception as e:
    #             return f"错误: 工具执行失败 - {str(e)}"
    #     else:
    #         return f"错误: 工具 '{name}' 没有设置处理函数"

    
    async def execute_tool(self, name: str, params: Dict[str, Any]) -> str:
        """执行工具的主入口，增加强类型校验"""
        tool = self.get_tool(name)
        if not tool:
            return f"错误: 未找到工具 '{name}'"

        if not tool.handler:
            return f"错误: 工具 '{name}' 未绑定 handler"

        # 1. 核心优化：利用 types.py 里的 Pydantic 模型进行二次校验
        try:
            action_enum = ActionType(name)
            schema_class = ACTION_SCHEMA_MAP.get(action_enum)
            if schema_class:
                # 这一步确保了传入 handler 的参数绝对符合定义
                validated_data = schema_class.model_validate(params)
                params = validated_data.model_dump()
        except (ValueError, ValidationError) as e:
            return f"错误: 参数校验失败 - {str(e)}"

        # 2. 异步/同步兼容执行
        try:
            if callable(tool.handler):
                import inspect
                if inspect.iscoroutinefunction(tool.handler):
                    result = await tool.handler(**params)
                else:
                    result = tool.handler(**params)
                return str(result)
        except Exception as e:
            return f"错误: 执行异常 - {str(e)}"

        return "错误: 未知的执行路径"
