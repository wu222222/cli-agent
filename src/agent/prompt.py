from typing import Dict, Any, List, Type
from pydantic import BaseModel
from .types import ActionType, ACTION_SCHEMA_MAP

class PromptManager:
    """Prompt管理器，支持动态 Schema 生成和多角色切换"""

    def __init__(self):
        # 基础原则（所有 Agent 通用）
        self.base_principles = [
            "1. 所有响应必须使用统一的 JSON 格式。",
            "2. 分析用户需求，决定采取什么行动。",
            "3. 始终以安全为首要考虑。"
        ]

    def _generate_action_docs(self, allowed_actions: List[ActionType]) -> str:
        """从 Pydantic 模型动态生成 Action 说明文档"""
        docs = []
        for action_type in allowed_actions:
            schema_class = ACTION_SCHEMA_MAP.get(action_type)
            if not schema_class:
                continue
            
            # 提取 Pydantic 定义的 JSON Schema
            schema_json = schema_class.model_json_schema()
            properties = schema_json.get("properties", {})
            required = schema_json.get("required", [])
            
            doc = f"### {action_type.value}\n"
            doc += f"参数要求: {properties}\n"
            doc += f"必填项: {required}\n"
            docs.append(doc)
        
        return "\n".join(docs)

    # def get_system_prompt(self, agent_name: str) -> str:
    #     """根据 Agent 名称生成完整的 System Prompt"""
        
    #     if agent_name == "worker":
    #         return self._build_worker_prompt()
    #     elif agent_name == "judge":
    #         return self._build_judge_prompt()
        
    #     return "你是一个通用的 AI 助手。"

    def _build_worker_prompt(self) -> str:
        # 定义 Worker 允许使用的动作
        allowed = [ActionType.EXECUTE_COMMAND, ActionType.STOP]
        
        prompt = f"""你是一个智能命令行助手，具备自我推理和工具调用能力。

        ## 核心原则
        {chr(10).join(self.base_principles)}

        ## 可用的 Action 类型及参数说明
        {self._generate_action_docs(allowed)}

        ## 响应格式要求
        请严格按照以下 JSON 结构输出，不要包含任何额外的解释文字：
        ```json
        {{
            "thought": "你的思考过程",
            "action": {{
                "type": "Action 类型名称",
                "parameters": {{ ...参数内容... }}
            }}
        }}
        ```
        """

        return prompt

    def _build_judge_prompt(self) -> str:
        # 假设你以后在 ActionType 增加了 REVIEW
        allowed = [ActionType.REVIEW] 
        
        return f"""你是一个严谨的质检员（Judge Agent）。
        
你的职责是审查 Worker Agent 的执行迹象，判断其是否真正完成了用户的目标。

评审准则
完整性：是否处理了所有要求的文件/任务？

真实性：最终答案是否基于执行记录（Observation），而非幻觉？

可用的 Action 类型
{self._generate_action_docs(allowed)}

响应格式要求
请严格按照以下 JSON 结构输出，不要包含任何额外的解释文字：
```json
{{
    "thought": "你的思考过程",
    "action": {{
        "type": "Action 类型名称",
        "parameters": {{ ...参数内容... }}
    }}
}}
```
"""