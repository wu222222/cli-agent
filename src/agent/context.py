from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field

from src.agent.types import *

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

    def get_system_format_prompt(self, agent_name: str) -> Dict[str, str]:
        """获取特定的 Agent 的系统格式化提示词，规范化格式，返回字典"""
        return {"role": "system", "content": self.system_prompts.get(agent_name, "")}

    def add_message(self, role: str, content: str, sender: str, receivers: List[str] = ["*"], tool_call_id: Optional[str] = None, tool_name: Optional[str] = None) -> None:
        """统一的消息添加方法"""
        msg = Message(
            role=role,
            content=content,
            sender=sender,
            receivers=receivers,
        )
        if role == "tool":
            msg.tool_call_id = tool_call_id
            msg.tool_name = tool_name
        self.messages.append(msg)

    @staticmethod
    def create_assistant_message(sender: str,content: str, receivers: List[str] = ["*"]) -> Message:
        """创建助手消息"""
        return Message(role="assistant", sender=sender, content=content, receivers=receivers)

    def add_user_message(self,agent_name: str, content: str, receivers: List[str] = ["*"]) -> None:
        """添加用户消息"""
        self.add_message(role="user", content=content, sender=agent_name, receivers=receivers)

    def add_assistant_message(self,agent_name: str, content: str, receivers: List[str] = ["*"]) -> None:
        """添加助手消息"""
        self.add_message(role="assistant", content=content, sender=agent_name, receivers=receivers)

    def add_tool_result(self,agent_name: str, result: str, tool_name: str, tool_call_id: Optional[str] = None, receivers: List[str] = ["*"]) -> None:
        # 对tool_name进行类型检测，确保是字符串，目前不需要
        """添加工具执行结果"""
        self.add_message(role="tool",
            sender=agent_name,
            content=result,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            receivers=receivers
        )

    # 这只是个临时的降低token消耗的方法，后续需要根据实际情况调整
    def get_recent_messages(self, agent_name: str, limit: int = 5, include_system_prompt: bool = True) -> List[Dict[str, Any]]:
        """只获取最近 N 条该 Agent 可见的消息"""
        all_messages = self.get_agent_messages(agent_name, include_system_prompt)
        if len(all_messages) <= limit + 1: # +1 是为了保留 System Prompt
            return all_messages
        
        # 保留 System Prompt (index 0)，加上最后 limit 条
        if include_system_prompt:
            return [all_messages[0]] + all_messages[-limit:]
        else:
            return all_messages[-limit:]

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

        # 2. 遍历消息池
        for msg in self.messages:
            # 判断可见性
            is_broadcast = "*" in msg.receivers
            is_recipient = agent_name in msg.receivers
            is_self = msg.sender == agent_name
            
            if is_broadcast or is_recipient or is_self:
                # 转换逻辑
                item = {"role": msg.role, "content": msg.content}
                # 如果是 tool 结果，必须带上 ID
                if msg.role == "tool":
                    item["tool_call_id"] = msg.tool_call_id
                    item["name"] = msg.tool_name
                # 核心优化：如果消息是别人发的，在 content 里注入 [From: XXX] 
                # 这样模型能清晰感知到这是谁在对它说话
                elif msg.sender != agent_name and msg.role != "system":
                    item["name"] = msg.sender
                    
                formatted_messages.append(item)
                
        return formatted_messages

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
                lines.append(f"\n{i}. 角色: {msg.role} 发送者: {msg.sender} 接收者: {msg.receivers}")
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
                msg_dict = {"role": msg.role, "sender": msg.sender, "receivers": msg.receivers, "content": msg.content}
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
