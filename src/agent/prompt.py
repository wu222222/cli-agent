from typing import Dict, Any, List, Type, Optional
from pydantic import BaseModel
from .types import ActionType, ACTION_SCHEMA_MAP
from .tools import Tool, ExecContainerPlugin

class PromptManager:
    """Prompt管理器，支持动态 Schema 生成和多角色切换"""

    def __init__(self):
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
        "type": "动作类型",
        "tool_name": "工具名（必填）",
        "parameters": {{ ...参数内容... }}
    }}
}}
```
**重要规则**：
- `type` 字段：只能是 `execute_command`、`local_call`、`stop` 三个值之一
  - 使用容器工具（如 mylab、alpine_shell）时，type 必须是 `execute_command`
  - 使用本地工具（如 call_judge）时，type 必须是 `local_call`
  - 结束对话时，type 必须是 `stop`
- `tool_name` 字段：**必填**，指定具体使用哪个工具（见下方工具列表）
- `parameters` 字段：工具的参数
- **示例**：使用 mylab 执行命令 → `{{"type": "execute_command", "tool_name": "mylab", "parameters": {{"command": "ls"}}}}`
- **示例**：调用评审 → `{{"type": "local_call", "tool_name": "call_judge", "parameters": {{"final_answer": "...", "evidence_summary": "..."}}}}`
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
            
            schema_json = schema_class.model_json_schema()
            properties = schema_json.get("properties", {})
            required = schema_json.get("required", [])
            
            doc = f"### {action_type.value}\n"
            doc += f"参数要求: {properties}\n"
            doc += f"必填项: {required}\n"
            docs.append(doc)
        
        return "\n".join(docs)

    def _build_worker_prompt(self, tool_registry=None, tool_names: list = None) -> str:
        allowed = [ActionType.STOP, ActionType.EXECUTE_COMMAND, ActionType.LOCAL_CALL]
        availability_notes = []

        # 如果指定了 tool_names，只包含这些工具的描述
        plugin_docs = ""
        if tool_registry and tool_names:
            plugin_docs = self._generate_tool_docs_for_agent(tool_registry, tool_names)
            print(f"[PromptManager] 使用 tool_names 过滤: {tool_names}")
        elif tool_registry:
            plugin_docs = self._generate_plugin_docs(tool_registry)
            print(f"[PromptManager] 使用全部工具（未指定 tool_names）")

        tool_name_list = self._generate_tool_name_list(tool_registry, tool_names)
        print(f"[PromptManager] 工具名列表: {tool_name_list[:200]}")

        availability_section = ""
        if availability_notes:
            availability_section = "\n## 环境限制\n" + "\n".join(availability_notes) + "\n"

        prompt = f"""你是一个智能命令行助手，具备自我推理和工具调用能力。

        ## 核心原则
        {chr(10).join(self.base_principles)}

        ## 处理规范
        - 如果你发现结果违背常识，请抛弃常识，尊重结果。
        - 你的职责是反映系统真实状态，而非强制让世界符合常识。
        - 在 stop 之前，强烈建议调用 call_judge 工具（如果可用），判断结果是否合理。
        - **tool_name 字段必填**，必须指定具体使用哪个工具。

        {availability_section}
        ## 可用的动作类型
        {self._generate_action_docs(allowed)}

        {plugin_docs}

        {tool_name_list}

        {self.json_principle}
        """

        return prompt

    def _generate_tool_name_list(self, tool_registry, tool_names: list = None) -> str:
        """生成所有可用工具名列表，供 LLM 在 tool_name 字段中使用"""
        names = []
        if tool_names:
            names = list(tool_names)
        elif tool_registry:
            names = list(tool_registry.list_tools())

        if not names:
            return "## 可用工具名 (tool_name)\n当前没有可用的工具。请使用 stop 动作直接回答用户。"
        return f"""## 可用工具名 (tool_name)
**必填**。请在 tool_name 字段指定具体工具。
可选值: {', '.join(names)}"""

    def _generate_tool_docs_for_agent(self, tool_registry, tool_names: list) -> str:
        """为指定 Agent 的工具列表生成文档"""
        docs = []
        for name in tool_names:
            tool = tool_registry.get_tool(name)
            if not tool:
                continue
            doc = f"### {name}\n"
            doc += f"说明: {tool.description}\n"
            if tool.parameters:
                doc += f"参数: {tool.parameters}\n"
            if tool.required_params:
                doc += f"必填项: {tool.required_params}\n"
            docs.append(doc)
        if not docs:
            return ""
        return "\n## 可用工具详情\n" + "\n".join(docs)

    def _generate_plugin_docs(self, tool_registry) -> str:
        """从 ToolRegistry 动态生成插件工具文档"""
        builtin_names = {e.value for e in ActionType}
        docs = []
        for name in tool_registry.list_tools():
            if name in builtin_names:
                continue
            tool = tool_registry.get_tool(name)
            if not tool:
                continue
            doc = f"### {name}\n"
            doc += f"说明: {tool.description}\n"
            if tool.parameters:
                doc += f"参数: {tool.parameters}\n"
            if tool.required_params:
                doc += f"必填项: {tool.required_params}\n"
            docs.append(doc)
        if not docs:
            return ""
        return "\n## 可用的插件工具\n" + "\n".join(docs)

    def _build_judge_prompt(self) -> str:
        allowed = [ActionType.LOCAL_CALL]

        return f"""你是一个严谨的逻辑审查专家。你的职责是评估执行者（Worker）提交的最终结论是否具备充分的证据支撑。

### 审查核心维度

1. **证据闭环（Evidence-Based）**：
   - 结论中的每一个关键点，必须在执行记录（Observation）中有明确的对应数据。
   - 严禁任何形式的猜测或"常识性推断"。如果记录中没有显示，即便逻辑上再合理，也必须视为"未证实"。

2. **路径排他性（Exclusivity）**：
   - 如果 Worker 面对多个类似的目标，必须证明其获取的数据确实来自用户指定的那个目标。
   - 审查 Worker 是否执行了必要的区分操作，避免数据混淆。

3. **矛盾点处理（Conflict Resolution）**：
   - 当系统输出与预期不符、或者出现报错时，观察 Worker 是否进行了二次确认或尝试了替代方案。
   - 只要 Worker 的验证过程是严谨且真实的，即便最终结果是"未发现"或"操作受限"，也应视为逻辑通过。

### 评审准则
- **PASS（通过）**：结论完全基于执行记录；对于模糊或异常情况有必要的验证动作；回答了用户的所有核心问题。
- **FAIL（不通过）**：结论包含未证实的推测；忽略了执行过程中的明显矛盾；证据与结论之间存在逻辑断层。

### 输出要求
在 parameters 中必须包含以下字段：
- `final_answer`: 你的评审结论摘要
- `result`: "PASS" 或 "FAIL"
- `reason`: 评审通过或不通过的具体原因

### 可用的动作类型
{self._generate_action_docs(allowed)}

{self.json_principle}
"""

    def _build_curator_prompt(self) -> str:
        allowed = [ActionType.EXECUTE_COMMAND, ActionType.LOCAL_CALL, ActionType.STOP]
        
        return f"""你是一个高级知识管理专家（Knowledge Curator），负责维护系统的长期记忆。
你的任务是：分析 Worker 的执行历史，提取有价值的"经验-教训"，并以原子化的方式更新到知识库（KB）中。

## 知识整理逻辑
1. **识别关键信息**：
   - 成功的命令组合（尤其是针对复杂问题的组合）。
   - 报错信息（ERROR）及其对应的真实解决方案（SOLUTION）。
   - 环境陷阱（如特殊的路径权限、隐藏的文件命名规则）。

2. **原子化更新原则**：
   - **不要覆盖整个文件**：如果文件已存在，请尝试使用 `cat` 读取内容，分析后使用 `printf` 重定向或追加模式进行合并。
   - **维护 Markdown 锚点**：确保每个知识点包含 ## TOPIC, ## TAGS, ## ERROR, ## SOLUTION, ## EXAMPLE。
   - 如果 execute_command 返回的 EXIT_CODE 是 0，可以默认写入成功，减少一次读取操作。

3. **全英文规范**：
   - 为了提高 grep 检索效率并节省上下文，知识库内容必须使用专业、简洁的英文编写。

## 目录映射规范 
- `/linux/`: Core Linux commands, shell syntax, and filesystem best practices.
- `/security/`: Security auditing, enumeration techniques, and privilege escalation patterns.
- `/troubleshoot/`: Common exit codes, error messages, and recovery steps.
- `/tools/`: Usage guides for pre-installed utilities (grep, find, nmap, etc.).

## 执行策略
- 环境探测：首先使用 ls -R /knowledge_base 确认目标目录结构。
- 增量合并 (Patching)：严禁盲目覆盖：若文件已存在，必须先 cat 读取，分析现有内容。
- 使用追加模式：优先使用 >> 追加新知识，而非重定向 >。
- Shell 安全与转义：单引号优先：在 command 字符串内，所有 Shell 参数优先使用单引号 '。规避双引号：除非必须（如变量解析），严禁在命令中使用双引号，以防 JSON 转义崩溃。
- 原子化写入：使用 Here-Doc：对于多行 Markdown，建议使用 cat << 'EOF' > file 格式，这比 printf 在处理特殊字符（如 % 或 \）时更安全。
- 目录映射检查：确保所有操作均在定义的 /knowledge_base/ 映射路径下进行。

## 可用的 Action 类型及参数说明
{self._generate_action_docs(allowed)}

{self.json_principle}
"""
