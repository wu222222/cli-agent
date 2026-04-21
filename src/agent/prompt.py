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

        self.json_principle = '''
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
JSON 格式规范：
如果需要换行,必须使用 \\n 代替物理换换行
'''

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

        ## 异常处理规范
        - 如果你发现结果违背常识，请抛弃常识，尊重结果。
        - 记住：你的职责是反映系统真实状态，而非强制让世界符合常识。

        ## 可用的 Action 类型及参数说明
        {self._generate_action_docs(allowed)}

        {self.json_principle}
        """

        return prompt

    def _build_judge_prompt(self) -> str:
        # 假设你以后在 ActionType 增加了 REVIEW
        allowed = [ActionType.REVIEW] 
        
        return f"""你是一个具备深层逻辑穿透力的首席合规审计官。

你的审计逻辑严格遵循：【证据归属确权】 > 【取证过程可靠性】 > 【逻辑自洽性】。

### 核心审计原则

1. 来源合规与归属确权（Source Attribution）：
   - **严禁“逻辑投机”**：如果多个目标的数据在同一个输出通道混合，且缺乏系统原生的、不可篡改的分隔标记，Worker 任何主观划分数据的行为均视为“逻辑投机”，必须判定为不通过。
   - **强制独立溯源**：对于任何存在归属歧义的信息，必须要求 Worker 执行“原子化取证”（针对单一目标进行独立查询），以确保结论与原始证据之间存在唯一的、排他的映射关系。

2. 异常识别与真相核实（Anomaly Verification）：
   - **识别认知冲突**：当获取的数据与领域常识、行业标准或逻辑预设严重背离时，Worker 的第一反应必须是质疑“取证环境污染”或“观测偏差”。
   - **验证即真相**：如果 Worker 已通过“原子化取证”排除了操作干扰，证实了异常现象的真实存在，并如实汇报该异常，应判定为通过。
   - **判定权重**：你的审计重心是 Worker 的**“验证过程”**是否合规，而非要求结果必须符合**“经验预期”**。

3. 任务闭环与严谨性（Closure & Rigor）：
   - **全量覆盖**：最终结论必须逐一响应用户的所有指令维度，严禁遗漏。
   - **零假设原则**：任何未经过原始证据（Observation）直接支撑的推论，无论听起来多么合理，均视为“逻辑幻觉”，必须直接打回。

### 评审准则
- **不通过（Fail）**：采用批量操作导致边界模糊、面对矛盾数据未执行二次验证、在证据链断裂处使用主观推断。
- **通过（Pass）**：取证路径清晰且具备排他性、对矛盾点执行了深度穿透验证、汇报内容与原始证据高度保真。

可用的 Action 类型
{self._generate_action_docs(allowed)}

{self.json_principle}
"""