from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field

from src.agent.types import StateData


class Message(BaseModel):
    role: str  # user, assistant, system, tool
    content: str
    sender: str  # 发送方标识：如 "user", "system", "WorkerAgent", "JudgeAgent"
    # 接收方列表：如果是 ["*"] 表示广播给所有人，或者指定具体 Agent 列表 ["JudgeAgent"] 暂时不需要使用
    # receivers: List[str] = Field(default_factory=lambda: ["*"])
    
    # 扩展字段：用于工具调用
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


class StateTrace(BaseModel):
    agent_name: str
    from_state: str
    to_state: str
    data: Optional[StateData] = None

class ContextManager:
    def __init__(self):
        self.messages: List[Message] = []
        self.state_trace: List[StateTrace] = []
        self.system_prompts: dict[str,str] = {}
        self.final_answer: Optional[str] = None

    def set_system_prompt(self, agent_name: str, prompt: str) -> None:
        """为特定的 Agent 设置系统提示词"""
        self.system_prompts[agent_name] = prompt

    def get_system_prompt(self, agent_name: str) -> str:
        """获取特定的 Agent 的系统提示词"""
        return self.system_prompts.get(agent_name, "")

    def add_message(self, role: str, content: str, sender: str, tool_call_id: Optional[str] = None, tool_name: Optional[str] = None) -> None:
        """统一的消息添加方法"""
        msg = Message(
            role=role,
            content=content,
            sender=sender,
        )
        if role == "tool":
            msg.tool_call_id = tool_call_id
            msg.tool_name = tool_name
        self.messages.append(msg)

    def add_user_message(self,agent_name: str, content: str) -> None:
        """添加用户消息"""
        self.add_message(role="user", content=content, sender=agent_name)

    def add_assistant_message(self,agent_name: str, content: str) -> None:
        """添加助手消息"""
        self.add_message(role="assistant", content=content, sender=agent_name)

    def add_tool_result(self,agent_name: str, tool_name: str, result: str, tool_call_id: Optional[str] = None) -> None:
        """添加工具执行结果"""
        self.add_message(role="tool",
            sender=agent_name,
            content=result,
            tool_call_id=tool_call_id,
            tool_name=tool_name
        )

    def get_agent_messages(self, agent_name: str, include_system_prompt: bool = True) -> List[Dict[str, Any]]:
        """
        为特定的 Agent 提取它"有权看到"的消息列表
        逻辑：
        1. 获取该 Agent 的 System Prompt。
        2. 过滤消息：sender 是自己。
        """
        formatted_messages = []
        
        # 1. 插入该 Agent 专属的系统消息
        if include_system_prompt and agent_name in self.system_prompts:
            formatted_messages.append({
                "role": "system",
                "content": self.system_prompts[agent_name]
            })

        # 2. 过滤并格式化对话历史
        for msg in self.messages:
            # 权限检查：是否是发给我的
            if msg.sender == agent_name:
                item = {"role": msg.role, "content": msg.content}
                # 如果是工具结果，通常需要带上 ID
                if msg.role == "tool":
                    item["tool_call_id"] = msg.tool_call_id
                    item["name"] = msg.tool_name
                # 如果是 assistant 且不是自己发的，可以带上 name 辅助 LLM 辨别对方身份
                elif msg.role == "assistant" and msg.sender != agent_name:
                    item["name"] = msg.sender
                
                formatted_messages.append(item)
                
        return formatted_messages


    # def get_context_summary(self) -> str:
    #     """获取上下文摘要"""
    #     summary = f"消息数量: {len(self.messages)}\n"
    #     summary += f"系统提示: {self.system_prompt[:100]}..." if self.system_prompt else "无系统提示\n"
        
    #     # 显示最近的几条消息
    #     recent_messages = self.messages[-5:]
    #     summary += "最近消息:\n"
    #     for msg in recent_messages:
    #         content_preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
    #         summary += f"[{msg.role}] {content_preview}\n"
        
    #     return summary

    def clear(self) -> None:
        """清空上下文"""
        self.messages = []
        self.final_answer = None
        # 保留系统提示
        if self.system_prompts:
            self.messages.append(Message(role="system", content=self.system_prompts[agent_name], sender=agent_name))

    def format_history(self, format_type: str = "simple") -> str:
        """格式化历史消息
        
        Args:
            format_type: 格式化类型，可选值: simple, detailed, json
            
        Returns:
            str: 格式化后的历史消息
        """
        if format_type == "simple":
            lines = [f"历史消息（共 {len(self.messages)} 条）:"]
            for i, msg in enumerate(self.messages, 1):
                content_preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
                lines.append(f"{i}. [{msg.role}] {content_preview}")
            return "\n".join(lines)
        
        elif format_type == "detailed":
            lines = [f"历史消息详情（共 {len(self.messages)} 条）:"]
            for i, msg in enumerate(self.messages, 1):
                lines.append(f"\n{i}. 角色: {msg.role} 发送者: {msg.sender}")
                if msg.tool_name:
                    lines.append(f"   工具: {msg.tool_name}")
                if msg.tool_call_id:
                    lines.append(f"   工具调用ID: {msg.tool_call_id}")
                lines.append(f"   内容: {msg.content}")
            return "\n".join(lines)
        
        elif format_type == "json":
            import json
            messages_data = []
            for msg in self.messages:
                msg_dict = {"role": msg.role, "sender": msg.sender, "content": msg.content}
                if msg.tool_name:
                    msg_dict["tool_name"] = msg.tool_name
                if msg.tool_call_id:
                    msg_dict["tool_call_id"] = msg.tool_call_id
                messages_data.append(msg_dict)
            return json.dumps(messages_data, ensure_ascii=False, indent=2)
        
        else:
            return self.get_context_summary()

    def add_state_trace(self, agent_name: str, from_state: str, to_state: str, data: Optional[StateData] = None) -> None:
        """添加状态转换记录"""
        self.state_trace.append(StateTrace(agent_name=agent_name, from_state=from_state, to_state=to_state, data=data))

    def get_state_trace(self) -> str:
        """格式化状态转换记录"""
        lines = [f"--- 状态转换追踪 (Total: {len(self.state_trace)}) ---"]
        
        for i, trace in enumerate(self.state_trace, 1):
            # 基础路线信息
            line = f"{i:02d}. [{trace.agent_name}] [{trace.from_state}] -> [{trace.to_state}]"
            lines.append(line)
            
            # 如果有数据，调用我们自定义的格式化方法
            if trace.data:
                # 关键点：这里会自动根据具体的子类调用对应的 format_for_log
                lines.append(f"    └─ {trace.data.format_for_log()}")
                
        return "\n".join(lines)

    def set_final_answer(self, answer: str) -> None:
        """设置最终回答"""
        self.final_answer = answer

    def get_final_answer(self) -> str:
        """获取最终回答"""
        return self.final_answer or "操作已完成"
