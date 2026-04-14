from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Message:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextManager:
    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        self.messages: List[Message] = []
        self.system_prompt: Optional[str] = None

    def set_system_prompt(self, prompt: str) -> None:
        self.system_prompt = prompt

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)
        self._trim_history()

    def add_user_message(self, content: str) -> None:
        self.add_message("user", content)

    def add_assistant_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.add_message("assistant", content, metadata)

    def add_tool_result(self, tool_name: str, result: str) -> None:
        content = f"工具 {tool_name} 的执行结果:\n{result}"
        self.add_message("system", content, {"type": "tool_result", "tool_name": tool_name})

    def get_messages(self) -> List[Dict[str, str]]:
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        for msg in self.messages:
            messages.append({"role": msg.role, "content": msg.content})
        return messages

    def get_recent_messages(self, n: int) -> List[Dict[str, str]]:
        all_messages = self.get_messages()
        return all_messages[-n:] if n < len(all_messages) else all_messages

    def clear(self) -> None:
        self.messages.clear()

    def _trim_history(self) -> None:
        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]

    def get_context_summary(self) -> str:
        return f"上下文包含 {len(self.messages)} 条消息，最大保留 {self.max_history} 条"
