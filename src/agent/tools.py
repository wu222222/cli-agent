from typing import Dict, Any, Callable, Optional, List

from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
import json


class Tool(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    required_params: List[str] = field(default_factory=list)

    handler: Optional[Callable] = None

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
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        # 注册默认工具
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """注册默认工具"""
        # execute_command 工具
        execute_command_tool = Tool(
            name="execute_command",
            description="在 Docker 容器中执行 Shell 命令",
            parameters={
                "command": {
                    "type": "string",
                    "description": "要执行的 Shell 命令"
                }
            },
            required_params=["command"]
        )
        self.register(execute_command_tool)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def get_all_tools(self) -> List[Dict[str, Any]]:
        return [tool.to_dict() for tool in self._tools.values()]

    def execute_tool(self, name: str, params: Dict[str, Any]) -> str:
        tool = self.get_tool(name)
        if not tool:
            return f"错误: 未找到工具 '{name}'"

        if not tool.validate_params(params):
            return f"错误: 工具 '{name}' 参数验证失败，缺少必需参数"

        if tool.handler:
            try:
                result = tool.handler(**params)
                return str(result)
            except Exception as e:
                return f"错误: 工具执行失败 - {str(e)}"
        else:
            return f"错误: 工具 '{name}' 没有设置处理函数"

    def parse_tool_call(self, response: str) -> Optional[Dict[str, Any]]:
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)
            if "action" in data:
                return data
            return None
        except (json.JSONDecodeError, IndexError):
            return None
