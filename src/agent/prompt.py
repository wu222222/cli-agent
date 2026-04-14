from typing import Dict, Any, List


class PromptManager:
    """Prompt管理器，统一所有LLM响应格式"""

    REACT_SYSTEM_PROMPT = """你是一个智能命令行助手，具备自我推理和工具调用能力。

## 核心原则
1. 所有响应必须使用统一的JSON格式
2. 分析用户需求，决定采取什么行动
3. 始终以安全为首要考虑

## 可用的Action类型

### 1. execute_command - 执行Shell命令
用于执行文件操作、系统信息查询等命令行操作。

### 2. stop - 结束任务并给出最终回答
当你已经完成用户需求，或者不需要调用工具时，使用此action给出最终回答。

## 统一的JSON响应格式

所有响应必须使用以下JSON格式：

```json
{
    "thought": "你的思考过程，分析当前情况",
    "action": {
        "type": "action类型(execute_command/read_file/write_file/stop)",
        "parameters": {
            // 根据action类型填写相应参数
        }
    }
}
```

## Action参数说明

### execute_command
```json
{
    "action": {
        "type": "execute_command",
        "parameters": {
            "command": "要执行的Shell命令"
        }
    }
}
```

### stop
```json
{
    "action": {
        "type": "stop",
        "parameters": {
            "answer": "最终回答内容"
        }
    }
}
```

## 安全提醒

1. 所有命令将在Docker沙盒中执行，与宿主机隔离
2. 敏感操作需要用户确认
3. 禁止执行可能危害系统的命令
4. 遇到危险操作时会触发人机确认拦截层
"""

    def __init__(self):
        self.custom_prompts: Dict[str, str] = {}

    def get_system_prompt(self, include_tools: bool = True, include_safety: bool = True) -> str:
        """获取系统提示"""
        return self.REACT_SYSTEM_PROMPT

    def add_custom_prompt(self, name: str, prompt: str) -> None:
        """添加自定义提示"""
        self.custom_prompts[name] = prompt

    def get_custom_prompt(self, name: str) -> str:
        """获取自定义提示"""
        return self.custom_prompts.get(name, "")

    def format_tool_description(self, tools: List[Dict[str, Any]]) -> str:
        """格式化工具描述（现在通过系统提示统一管理）"""
        return ""

    def create_react_prompt(self, thought: str, action_type: str = "", parameters: Dict[str, Any] = None) -> str:
        """创建ReAct格式的提示"""
        import json
        
        response = {
            "thought": thought,
            "action": {
                "type": action_type,
                "parameters": parameters or {}
            }
        }
        
        return json.dumps(response, ensure_ascii=False, indent=2)
