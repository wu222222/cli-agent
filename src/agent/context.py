from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .base import Message, StateTrace



class ContextManager:
    def __init__(self):
        self.messages: List[Message] = []
        self.state_trace: List[StateTrace] = []
        self.system_prompt: Optional[str] = None
        self.final_answer: Optional[str] = None

    def set_system_prompt(self, prompt: str) -> None:
        """设置系统提示"""
        self.system_prompt = prompt
        # 移除旧的系统消息
        self.messages = [msg for msg in self.messages if msg.role != "system"]
        # 添加新的系统消息
        self.messages.insert(0, Message(role="system", content=prompt))

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.messages.append(Message(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        """添加助手消息"""
        self.messages.append(Message(role="assistant", content=content))

    def add_tool_result(self, tool_name: str, result: str, tool_call_id: Optional[str] = None) -> None:
        """添加工具执行结果"""
        self.messages.append(Message(
            role="tool",
            content=result,
            tool_call_id=tool_call_id,
            tool_name=tool_name
        ))

    def get_messages(self) -> List[Dict[str, Any]]:
        """获取消息列表，格式化为LLM API需要的格式"""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]

    def get_context_summary(self) -> str:
        """获取上下文摘要"""
        summary = f"消息数量: {len(self.messages)}\n"
        summary += f"系统提示: {self.system_prompt[:100]}..." if self.system_prompt else "无系统提示\n"
        
        # 显示最近的几条消息
        recent_messages = self.messages[-5:]
        summary += "最近消息:\n"
        for msg in recent_messages:
            content_preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            summary += f"[{msg.role}] {content_preview}\n"
        
        return summary

    def clear(self) -> None:
        """清空上下文"""
        self.messages = []
        self.final_answer = None
        # 保留系统提示
        if self.system_prompt:
            self.messages.append(Message(role="system", content=self.system_prompt))

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
                lines.append(f"\n{i}. 角色: {msg.role}")
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
                msg_dict = {"role": msg.role, "content": msg.content}
                if msg.tool_name:
                    msg_dict["tool_name"] = msg.tool_name
                if msg.tool_call_id:
                    msg_dict["tool_call_id"] = msg.tool_call_id
                messages_data.append(msg_dict)
            return json.dumps(messages_data, ensure_ascii=False, indent=2)
        
        else:
            return self.get_context_summary()

    def add_state_trace(self, from_state: str, to_state: str, params: Optional[Dict[str, Any]] = None) -> None:
        """添加状态转换记录"""
        self.state_trace.append(StateTrace(from_state=from_state, to_state=to_state, params=params))

    def get_state_trace(self) -> str:
        """格式化状态转换记录
        
        Returns:
            str: 格式化后的状态转换记录   
        """
        lines = [f"状态转换记录（共 {len(self.state_trace)} 条）:"]
        for i, trace in enumerate(self.state_trace, 1):
            lines.append(f"{i}. 从 {trace.from_state} 到 {trace.to_state}")
            if trace.params:
                lines.append(f"   参数: {trace.params}")
        return "\n".join(lines)

    def set_final_answer(self, answer: str) -> None:
        """设置最终回答"""
        self.final_answer = answer

    def get_final_answer(self) -> str:
        """获取最终回答"""
        return self.final_answer or "操作已完成"
